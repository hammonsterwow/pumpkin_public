from __future__ import annotations

import math
import queue
import threading
import time
from collections import deque

import numpy as np
import rclpy
import sounddevice as sd
from rclpy.executors import ExternalShutdownException
from scipy.io.wavfile import write
from std_msgs.msg import String

from .stt_node import STTNode


class SafeSTTNode(STTNode):
    """STT runtime with per-turn cancellation and audio-stream stall recovery.

    The original STT node used one shared cancellation Event and one shared busy
    flag for every capture/transcription thread. A visual gesture can cancel an
    active turn while Whisper is still transcribing it, and a newer listen turn
    may begin later. If an old thread then clears shared state or publishes late,
    it can corrupt the new turn.

    This subclass gives every capture its own token and Event. Only the thread
    that owns the active token may publish text or release the busy flag. Audio
    capture also uses a callback queue with a watchdog, so a PortAudio/ALSA stream
    that stops delivering blocks cannot leave the robot listening forever.
    """

    STREAM_STALL_TIMEOUT_SEC = 1.5
    AUDIO_QUEUE_BLOCKS = 64

    def __init__(self) -> None:
        super().__init__()
        self._active_capture_token: int | None = None
        self._active_cancel_event: threading.Event | None = None
        self.get_logger().info(
            'Safe STT turn isolation enabled: stale-result guard + audio-stream watchdog'
        )

    def _cancel_active_capture(self) -> None:
        with self._lock:
            cancel_event = self._active_cancel_event
        if cancel_event is not None:
            cancel_event.set()

    def trigger_callback(self, msg: String) -> None:
        command = msg.data.strip().lower()

        if command in {'cancel', 'stop'}:
            with self._lock:
                self._start_token += 1
                cancel_event = self._active_cancel_event
            if cancel_event is not None:
                cancel_event.set()
            self.get_logger().info('STT cancel requested for the active capture turn.')
            return

        if command not in {'start', 'record', 'listen', 'confirm', ''}:
            self.get_logger().warning(f'Unknown STT command: {msg.data}')
            return

        confirmation_mode = command == 'confirm'
        listen_mode = 'confirmation' if confirmation_mode else 'normal'
        speech_start_blocks = (
            self.confirmation_speech_start_blocks
            if confirmation_mode
            else self.speech_start_blocks
        )

        with self._lock:
            self._start_token += 1
            token = self._start_token
            self._active_listen_mode = listen_mode
            self._active_speech_start_blocks = speech_start_blocks

        threading.Thread(
            target=self._start_when_tts_safe,
            args=(token, listen_mode, speech_start_blocks),
            daemon=True,
            name=f'pumpkin-stt-start-guard-{token}',
        ).start()

    def tts_status_callback(self, msg: String) -> None:
        status = str(msg.data or '').strip().lower()
        now = time.monotonic()

        if status == 'speaking':
            with self._lock:
                self._tts_speaking = True
                self._start_token += 1
                was_busy = self._busy
                cancel_event = self._active_cancel_event
            if cancel_event is not None:
                cancel_event.set()
            if was_busy:
                self.get_logger().warning(
                    'Robot TTS started while STT was active; cancelling only the owning capture turn.'
                )
            return

        if status == 'done' or status.startswith('error'):
            with self._lock:
                self._tts_speaking = False
                self._tts_guard_until = max(
                    self._tts_guard_until,
                    now + self.post_tts_guard_sec,
                )
            self.get_logger().info(
                f'TTS finished; microphone guarded for {self.post_tts_guard_sec:.2f}s.'
            )

    def _start_when_tts_safe(
        self,
        token: int,
        listen_mode: str,
        speech_start_blocks: int,
    ) -> None:
        waiting_logged = False
        while not self._shutdown_requested:
            with self._lock:
                if token != self._start_token:
                    return
                tts_speaking = self._tts_speaking
                guard_until = self._tts_guard_until
                busy = self._busy

            now = time.monotonic()
            guard_remaining = max(0.0, guard_until - now)
            if tts_speaking or guard_remaining > 0.0 or busy:
                if not waiting_logged and (tts_speaking or guard_remaining > 0.0):
                    self.get_logger().info(
                        'Delaying STT start until robot speech and acoustic tail are clear.'
                    )
                    waiting_logged = True
                time.sleep(
                    min(0.05, guard_remaining)
                    if guard_remaining > 0.0
                    else 0.05
                )
                continue

            with self._lock:
                if token != self._start_token or self._busy:
                    continue
                if self._tts_speaking or time.monotonic() < self._tts_guard_until:
                    continue

                cancel_event = threading.Event()
                self._busy = True
                self._active_capture_token = token
                self._active_cancel_event = cancel_event

            threading.Thread(
                target=self.record_and_transcribe_turn,
                args=(token, cancel_event, listen_mode, speech_start_blocks),
                daemon=True,
                name=f'pumpkin-stt-record-{token}',
            ).start()
            return

    def _capture_is_current(
        self,
        token: int,
        cancel_event: threading.Event,
    ) -> bool:
        with self._lock:
            return (
                not self._shutdown_requested
                and token == self._start_token
                and token == self._active_capture_token
                and cancel_event is self._active_cancel_event
                and not cancel_event.is_set()
            )

    def _release_capture_owner(self, token: int) -> bool:
        """Release busy state only when the finishing thread still owns it."""
        with self._lock:
            if token != self._active_capture_token:
                return False
            self._active_capture_token = None
            self._active_cancel_event = None
            self._busy = False
            return True

    def record_until_silence_turn(
        self,
        cancel_event: threading.Event,
        listen_mode: str,
        speech_start_blocks: int,
    ) -> tuple[np.ndarray | None, str | None]:
        block_size = max(1, int(self.sample_rate * self.block_duration))
        pre_roll_blocks = max(1, int(self.pre_roll_duration / self.block_duration))
        silence_blocks_required = max(
            1, math.ceil(self.silence_duration / self.block_duration)
        )

        pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_blocks)
        noise_levels: deque[float] = deque(maxlen=pre_roll_blocks)
        recorded_blocks: list[np.ndarray] = []
        audio_queue: queue.Queue[np.ndarray] = queue.Queue(
            maxsize=self.AUDIO_QUEUE_BLOCKS
        )

        speech_started = False
        speech_started_at: float | None = None
        loud_block_count = 0
        silence_block_count = 0
        adaptive_end_threshold = self.end_threshold
        active_max_duration = self.select_max_speech_duration(
            listen_mode,
            self.max_duration,
            self.confirmation_max_duration,
        )
        listen_started_at = time.monotonic()
        last_audio_block_at = listen_started_at
        device = None if self.audio_device < 0 else self.audio_device

        callback_statuses: deque[str] = deque(maxlen=4)
        listening_published = False

        def audio_callback(indata, frames, time_info, status) -> None:
            del frames, time_info
            if status:
                callback_statuses.append(str(status))
            block = indata.copy()
            try:
                audio_queue.put_nowait(block)
            except queue.Full:
                try:
                    audio_queue.get_nowait()
                except queue.Empty:
                    pass
                try:
                    audio_queue.put_nowait(block)
                except queue.Full:
                    pass

        self.get_logger().info(
            'Opening microphone stream. '
            f'mode={listen_mode}, start_blocks={speech_start_blocks}'
        )

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                dtype='int16',
                device=device,
                blocksize=block_size,
                callback=audio_callback,
            ):
                while not self._shutdown_requested and not cancel_event.is_set():
                    now = time.monotonic()

                    if not speech_started:
                        if now - listen_started_at >= self.start_timeout:
                            self.get_logger().warning(
                                'No speech detected before timeout.'
                            )
                            return None, 'no_speech'
                    elif (
                        speech_started_at is not None
                        and now - speech_started_at >= active_max_duration
                    ):
                        self.get_logger().info(
                            'Maximum speech duration reached; transcribing captured audio. '
                            f'mode={listen_mode}, limit={active_max_duration:.1f}s'
                        )
                        break

                    try:
                        block = audio_queue.get(
                            timeout=max(0.10, self.block_duration * 3.0)
                        )
                    except queue.Empty:
                        if time.monotonic() - last_audio_block_at >= self.STREAM_STALL_TIMEOUT_SEC:
                            status_text = (
                                callback_statuses[-1]
                                if callback_statuses
                                else 'no callback blocks'
                            )
                            self.get_logger().error(
                                'Microphone audio stream stalled: '
                                f'{status_text}. Reopening on retry.'
                            )
                            return None, 'error:audio_stream_stalled'
                        continue

                    last_audio_block_at = time.monotonic()
                    if not listening_published:
                        # Customer-facing `listening` means the audio device is not
                        # merely opening: at least one real callback block has
                        # arrived, so speech started after this status cannot be
                        # lost before PortAudio capture is active.
                        self.publish_status('listening')
                        self.get_logger().info(
                            'Microphone stream ready; first audio block received. '
                            f'mode={listen_mode}'
                        )
                        listening_published = True

                    block_rms, block_peak = self.get_audio_level(block)

                    if not speech_started:
                        pre_roll.append(block)
                        if block_rms < self.speech_threshold:
                            noise_levels.append(block_rms)

                        if block_rms >= self.speech_threshold:
                            loud_block_count += 1
                        else:
                            loud_block_count = 0

                        if loud_block_count >= speech_start_blocks:
                            noise_floor = (
                                float(np.median(noise_levels))
                                if noise_levels
                                else self.adaptive_end_floor
                            )
                            adaptive_end_threshold = self.compute_adaptive_end_threshold(
                                noise_floor
                            )
                            speech_started = True
                            speech_started_at = time.monotonic()
                            recorded_blocks.extend(list(pre_roll))
                            self.publish_status('speech_detected')
                            self.get_logger().info(
                                'Speech detected. Recording started. '
                                f'mode={listen_mode}, '
                                f'rms={block_rms:.1f}, peak={block_peak}, '
                                f'noise_floor={noise_floor:.1f}, '
                                f'adaptive_end_threshold={adaptive_end_threshold:.1f}'
                            )
                    else:
                        recorded_blocks.append(block)

                        if block_rms < adaptive_end_threshold:
                            silence_block_count += 1
                        else:
                            silence_block_count = 0

                        if silence_block_count >= silence_blocks_required:
                            self.get_logger().info(
                                'End of speech detected. '
                                f'last_rms={block_rms:.1f}, '
                                f'threshold={adaptive_end_threshold:.1f}'
                            )
                            break
        except Exception as error:
            self.get_logger().error(f'Microphone stream failed: {error}')
            return None, f'error:audio_stream:{error}'

        if self._shutdown_requested or cancel_event.is_set():
            return None, 'cancelled'
        if not recorded_blocks:
            return None, 'no_speech'

        audio = np.concatenate(recorded_blocks, axis=0)
        minimum_samples = int(self.min_record_duration * self.sample_rate)
        if len(audio) < minimum_samples:
            self.get_logger().warning('Detected speech was too short.')
            return None, 'too_quiet'
        return audio, None

    def record_and_transcribe_turn(
        self,
        token: int,
        cancel_event: threading.Event,
        listen_mode: str,
        speech_start_blocks: int,
    ) -> None:
        try:
            start_time = time.monotonic()
            audio, capture_status = self.record_until_silence_turn(
                cancel_event,
                listen_mode,
                speech_start_blocks,
            )

            if capture_status is not None:
                if capture_status == 'cancelled':
                    self.get_logger().info(
                        f'STT turn {token} cancelled before transcription.'
                    )
                self.publish_status(capture_status)
                return

            if audio is None or not self._capture_is_current(token, cancel_event):
                self.get_logger().info(
                    f'Discarded stale STT capture before transcription: token={token}'
                )
                self.publish_status('cancelled')
                return

            recording_duration = len(audio) / self.sample_rate
            rms, peak = self.get_audio_level(audio)
            self.get_logger().info(
                f'Recording complete: duration={recording_duration:.2f}s, '
                f'rms={rms:.1f}, peak={peak}'
            )

            write(str(self.audio_file), self.sample_rate, audio)
            if rms < self.min_rms:
                self.get_logger().warning(
                    f'Audio input is too quiet. rms={rms:.1f}, min_rms={self.min_rms:.1f}.'
                )
                self.publish_status('too_quiet')
                return

            if not self._capture_is_current(token, cancel_event):
                self.publish_status('cancelled')
                return

            active_initial_prompt = self.select_initial_prompt(
                listen_mode,
                self.initial_prompt,
                self.confirmation_initial_prompt,
            )

            self.publish_status('transcribing')
            segments, _ = self.model.transcribe(
                str(self.audio_file),
                language=self.language,
                beam_size=self.beam_size,
                vad_filter=self.vad_filter,
                condition_on_previous_text=False,
                initial_prompt=active_initial_prompt,
                temperature=0.0,
            )

            if not self._capture_is_current(token, cancel_event):
                self.get_logger().info(
                    f'Discarded stale STT transcription after cancellation: token={token}'
                )
                self.publish_status('cancelled')
                return

            text = ' '.join(segment.text for segment in segments).strip()
            text = self.clean_text(text)

            if not text and self.vad_filter:
                self.get_logger().info(
                    'Whisper internal VAD returned empty text; retrying once without it.'
                )
                retry_segments, _ = self.model.transcribe(
                    str(self.audio_file),
                    language=self.language,
                    beam_size=self.beam_size,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    initial_prompt=active_initial_prompt,
                    temperature=0.0,
                )
                text = ' '.join(segment.text for segment in retry_segments).strip()
                text = self.clean_text(text)

            if not self._capture_is_current(token, cancel_event):
                self.get_logger().info(
                    f'Discarded stale STT retry result: token={token}'
                )
                self.publish_status('cancelled')
                return

            if not text:
                self.get_logger().warning('No speech was recognized.')
                self.publish_status('empty')
                return

            normalized_text = self.normalize_short_confirmation(text)
            if normalized_text != text:
                self.get_logger().info(
                    'Normalized repeated/elongated short confirmation: '
                    f'{text} -> {normalized_text}'
                )
                text = normalized_text

            if self.should_reject_text(text):
                self.get_logger().warning(f'Rejected unreliable STT text: {text}')
                self.publish_status('rejected')
                return

            message = String()
            message.data = text
            with self._lock:
                if (
                    self._shutdown_requested
                    or token != self._start_token
                    or token != self._active_capture_token
                    or cancel_event is not self._active_cancel_event
                    or cancel_event.is_set()
                ):
                    self.get_logger().info(
                        f'Blocked stale /voice_text publication: token={token}'
                    )
                    self.publish_status('cancelled')
                    return
                self.text_publisher.publish(message)

            elapsed = time.monotonic() - start_time
            self.get_logger().info(f'Published voice text: {text}')
            self.get_logger().info(
                f'Total STT processing time: {elapsed:.2f}s, token={token}'
            )
            self.publish_status('done')
        except Exception as error:
            if not self._shutdown_requested:
                self.get_logger().error(f'STT failed: {error}')
                self.publish_status(f'error:{error}')
        finally:
            released = self._release_capture_owner(token)
            if not released:
                self.get_logger().info(
                    f'STT turn {token} finished after ownership moved; busy state preserved.'
                )

    def destroy_node(self):
        self._cancel_active_capture()
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = SafeSTTNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
