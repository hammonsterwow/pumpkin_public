from __future__ import annotations

import math

import os
import queue
import re
import threading
import time
from collections import deque
from pathlib import Path

import numpy as np
import rclpy
import sounddevice as sd
from faster_whisper import WhisperModel
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from scipy.io.wavfile import write
from std_msgs.msg import String


READY_FILE = Path('/tmp/pumpkin_stt_ready')

DEFAULT_INITIAL_PROMPT = (
    '한국어 카페 주문 음성을 그대로 받아씁니다. '
    '메뉴는 아메리카노, 카페라떼, 바닐라라떼, 딸기스무디, 레몬에이드입니다. '
    '온도 표현은 아이스, 핫, 차갑게, 따뜻하게입니다. '
    '수량 표현은 한 잔, 두 잔, 세 잔, 네 잔, 다섯 잔, 열 잔, 스무 잔입니다. '
    '딸기스무디는 메뉴 이름이고 스무 잔은 수량 표현입니다. '
    '주문 확인 답변은 네, 예, 응, 아니요, 아뇨입니다.'
)

DEFAULT_CONFIRMATION_INITIAL_PROMPT = (
    '한국어 카페 주문 확인 대화입니다. '
    '짧은 확인 답변은 네, 예, 응, 아니요, 아뇨입니다. '
    '온도 답변은 아이스, 핫, 차갑게, 따뜻하게입니다. '
    '수량 답변은 한 잔, 두 잔, 세 잔, 네 잔, 다섯 잔, 열 잔, 스무 잔입니다. '
    '메뉴를 고치면 아메리카노, 카페라떼, 바닐라라떼, 딸기스무디, 레몬에이드 중 하나를 말합니다.'
)


class _CoreSTTNode(Node):
    """Automatically stop recording when the speaker finishes talking.

    The microphone is hard-gated around robot TTS playback. A listen trigger is
    accepted only after TTS has finished and a short acoustic settle interval has
    elapsed. If robot speech starts while STT is recording/transcribing, that turn
    is cancelled so the robot can never publish its own speech as /voice_text.

    Normal order speech keeps the conservative VAD start policy used on the
    physical robot. Yes/no confirmation turns can use a shorter consecutive-block
    requirement through the ``confirm`` trigger so one-syllable answers such as
    ``네`` are not dropped before Whisper sees them.
    """

    def __init__(self) -> None:
        READY_FILE.unlink(missing_ok=True)
        super().__init__('stt_node')

        self.declare_parameter('trigger_topic', '/stt/trigger')
        self.declare_parameter('text_topic', '/voice_text')
        self.declare_parameter('status_topic', '/stt/status')
        self.declare_parameter('tts_status_topic', '/tts/status')

        self.declare_parameter('sample_rate', 44100)
        self.declare_parameter('channels', 1)
        self.declare_parameter('audio_device', 0)
        self.declare_parameter('audio_file', '/tmp/pumpkin_stt.wav')

        self.declare_parameter('block_duration', 0.05)
        self.declare_parameter('pre_roll_duration', 0.4)
        self.declare_parameter('speech_threshold', 700.0)
        self.declare_parameter('end_threshold', 350.0)
        self.declare_parameter('adaptive_end_floor', 180.0)
        self.declare_parameter('adaptive_end_multiplier', 1.8)
        self.declare_parameter('adaptive_end_ceiling_ratio', 0.85)
        self.declare_parameter('speech_start_blocks', 2)
        self.declare_parameter('confirmation_speech_start_blocks', 4)
        self.declare_parameter('silence_duration', 0.25)
        self.declare_parameter('start_timeout', 15.0)
        self.declare_parameter('max_duration', 10.0)
        self.declare_parameter('confirmation_max_duration', 3.5)
        self.declare_parameter('min_record_duration', 0.5)
        self.declare_parameter('post_tts_guard_sec', 0.8)

        self.declare_parameter('model_size', 'small')
        self.declare_parameter('model_device', 'cpu')
        self.declare_parameter('compute_type', 'float32')
        self.declare_parameter('language', 'ko')
        self.declare_parameter('beam_size', 5)
        self.declare_parameter('vad_filter', True)
        self.declare_parameter('min_rms', 120.0)
        self.declare_parameter('initial_prompt', DEFAULT_INITIAL_PROMPT)
        self.declare_parameter(
            'confirmation_initial_prompt',
            DEFAULT_CONFIRMATION_INITIAL_PROMPT,
        )

        self.sample_rate = int(self.get_parameter('sample_rate').value)
        self.channels = int(self.get_parameter('channels').value)
        self.audio_device = int(self.get_parameter('audio_device').value)
        self.audio_file = Path(str(self.get_parameter('audio_file').value))

        self.block_duration = float(self.get_parameter('block_duration').value)
        self.pre_roll_duration = float(self.get_parameter('pre_roll_duration').value)
        self.speech_threshold = float(self.get_parameter('speech_threshold').value)
        self.end_threshold = float(self.get_parameter('end_threshold').value)
        self.adaptive_end_floor = float(self.get_parameter('adaptive_end_floor').value)
        self.adaptive_end_multiplier = float(self.get_parameter('adaptive_end_multiplier').value)
        self.adaptive_end_ceiling_ratio = float(self.get_parameter('adaptive_end_ceiling_ratio').value)
        self.speech_start_blocks = max(
            1,
            int(self.get_parameter('speech_start_blocks').value),
        )
        self.confirmation_speech_start_blocks = max(
            1,
            int(self.get_parameter('confirmation_speech_start_blocks').value),
        )
        self.silence_duration = float(self.get_parameter('silence_duration').value)
        self.start_timeout = float(self.get_parameter('start_timeout').value)
        self.max_duration = float(self.get_parameter('max_duration').value)
        self.confirmation_max_duration = max(
            1.0,
            float(self.get_parameter('confirmation_max_duration').value),
        )
        self.min_record_duration = float(self.get_parameter('min_record_duration').value)
        self.post_tts_guard_sec = max(
            0.0,
            float(self.get_parameter('post_tts_guard_sec').value),
        )

        if self.end_threshold >= self.speech_threshold:
            self.get_logger().warning(
                'end_threshold must be lower than speech_threshold; using 50% of speech_threshold.'
            )
            self.end_threshold = self.speech_threshold * 0.5
        if not 0.5 <= self.adaptive_end_ceiling_ratio < 1.0:
            self.get_logger().warning(
                'adaptive_end_ceiling_ratio must be in [0.5, 1.0); using 0.85.'
            )
            self.adaptive_end_ceiling_ratio = 0.85

        self.language = str(self.get_parameter('language').value)
        self.beam_size = int(self.get_parameter('beam_size').value)
        self.vad_filter = bool(self.get_parameter('vad_filter').value)
        self.min_rms = float(self.get_parameter('min_rms').value)
        self.initial_prompt = str(self.get_parameter('initial_prompt').value)
        self.confirmation_initial_prompt = str(
            self.get_parameter('confirmation_initial_prompt').value
        )

        model_size = str(self.get_parameter('model_size').value)
        model_device = str(self.get_parameter('model_device').value)
        compute_type = str(self.get_parameter('compute_type').value)

        self.text_publisher = self.create_publisher(
            String, str(self.get_parameter('text_topic').value), 10
        )
        self.status_publisher = self.create_publisher(
            String, str(self.get_parameter('status_topic').value), 10
        )
        self.trigger_subscription = self.create_subscription(
            String,
            str(self.get_parameter('trigger_topic').value),
            self.trigger_callback,
            10,
        )
        self.tts_status_subscription = self.create_subscription(
            String,
            str(self.get_parameter('tts_status_topic').value),
            self.tts_status_callback,
            10,
        )

        self._lock = threading.Lock()
        self._busy = False
        self._shutdown_requested = False
        self._cancel_requested = threading.Event()
        self._tts_speaking = False
        self._tts_guard_until = 0.0
        self._start_token = 0
        self._active_speech_start_blocks = self.speech_start_blocks
        self._active_listen_mode = 'normal'

        self.get_logger().info(
            f'Loading faster-whisper model: size={model_size}, '
            f'device={model_device}, compute_type={compute_type}'
        )
        self.model = WhisperModel(
            model_size, device=model_device, compute_type=compute_type
        )

        self.get_logger().info('STT node started with adaptive end-of-speech detection.')
        self.get_logger().info(
            f'sample_rate={self.sample_rate}, '
            f'block_duration={self.block_duration:.2f}s, '
            f'speech_threshold={self.speech_threshold:.1f}, '
            f'start_blocks={self.speech_start_blocks}, '
            f'confirmation_start_blocks={self.confirmation_speech_start_blocks}, '
            f'end_threshold_floor={self.end_threshold:.1f}, '
            f'silence_duration={self.silence_duration:.2f}s, '
            f'max_duration={self.max_duration:.1f}s, '
            f'confirmation_max_duration={self.confirmation_max_duration:.1f}s, '
            f'post_tts_guard={self.post_tts_guard_sec:.2f}s'
        )
        self.get_logger().info('Publish "start" or "confirm" to /stt/trigger.')

        READY_FILE.write_text(
            f'model={model_size}\n'
            f'device={model_device}\n'
            f'compute_type={compute_type}\n',
            encoding='utf-8',
        )
        self.publish_status('ready')

    def trigger_callback(self, msg: String) -> None:
        command = msg.data.strip().lower()

        if command in {'cancel', 'stop'}:
            with self._lock:
                self._start_token += 1
            self._cancel_requested.set()
            self.get_logger().info('STT cancel requested.')
            return

        if command not in {'start', 'record', 'listen', 'confirm', ''}:
            self.get_logger().warning(f'Unknown STT command: {msg.data}')
            return

        confirmation_mode = command == 'confirm'
        with self._lock:
            self._start_token += 1
            token = self._start_token
            self._active_listen_mode = (
                'confirmation' if confirmation_mode else 'normal'
            )
            self._active_speech_start_blocks = (
                self.confirmation_speech_start_blocks
                if confirmation_mode
                else self.speech_start_blocks
            )

        threading.Thread(
            target=self._start_when_tts_safe,
            args=(token,),
            daemon=True,
            name='pumpkin-stt-start-guard',
        ).start()

    def tts_status_callback(self, msg: String) -> None:
        status = str(msg.data or '').strip().lower()
        now = time.monotonic()

        if status == 'speaking':
            with self._lock:
                self._tts_speaking = True
                self._start_token += 1
                was_busy = self._busy
            self._cancel_requested.set()
            if was_busy:
                self.get_logger().warning(
                    'Robot TTS started while STT was active; cancelling microphone capture.'
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

    def _start_when_tts_safe(self, token: int) -> None:
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
                time.sleep(min(0.05, guard_remaining) if guard_remaining > 0.0 else 0.05)
                continue

            with self._lock:
                if token != self._start_token or self._busy:
                    continue
                if self._tts_speaking or time.monotonic() < self._tts_guard_until:
                    continue
                self._busy = True
                self._cancel_requested.clear()

            threading.Thread(
                target=self.record_and_transcribe,
                daemon=True,
                name='pumpkin-stt-record',
            ).start()
            return

    def compute_adaptive_end_threshold(self, noise_floor: float) -> float:
        ceiling = self.speech_threshold * self.adaptive_end_ceiling_ratio
        adaptive = max(
            self.adaptive_end_floor,
            float(noise_floor) * self.adaptive_end_multiplier,
        )
        return min(ceiling, max(self.end_threshold, adaptive))

    def record_until_silence(self) -> np.ndarray | None:
        block_size = max(1, int(self.sample_rate * self.block_duration))
        pre_roll_blocks = max(1, int(self.pre_roll_duration / self.block_duration))
        silence_blocks_required = max(
            1, math.ceil(self.silence_duration / self.block_duration)
        )
        max_blocks = max(1, int(self.max_duration / self.block_duration))
        start_timeout_blocks = max(1, int(self.start_timeout / self.block_duration))

        with self._lock:
            active_speech_start_blocks = self._active_speech_start_blocks
            active_listen_mode = self._active_listen_mode

        pre_roll: deque[np.ndarray] = deque(maxlen=pre_roll_blocks)
        noise_levels: deque[float] = deque(maxlen=pre_roll_blocks)
        recorded_blocks: list[np.ndarray] = []
        speech_started = False
        loud_block_count = 0
        silence_block_count = 0
        total_blocks = 0
        adaptive_end_threshold = self.end_threshold
        device = None if self.audio_device < 0 else self.audio_device

        self.get_logger().info(
            'Listening... Speak after the trigger. '
            f'mode={active_listen_mode}, start_blocks={active_speech_start_blocks}'
        )

        with sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            device=device,
            blocksize=block_size,
        ) as stream:
            while (
                total_blocks < max_blocks
                and not self._shutdown_requested
                and not self._cancel_requested.is_set()
            ):
                block, overflowed = stream.read(block_size)
                total_blocks += 1

                if overflowed:
                    self.get_logger().warning('Microphone input overflow detected.')

                block = block.copy()
                block_rms, block_peak = self.get_audio_level(block)

                if not speech_started:
                    pre_roll.append(block)
                    if block_rms < self.speech_threshold:
                        noise_levels.append(block_rms)

                    if block_rms >= self.speech_threshold:
                        loud_block_count += 1
                    else:
                        loud_block_count = 0

                    if loud_block_count >= active_speech_start_blocks:
                        noise_floor = (
                            float(np.median(noise_levels))
                            if noise_levels
                            else self.adaptive_end_floor
                        )
                        adaptive_end_threshold = self.compute_adaptive_end_threshold(
                            noise_floor
                        )
                        speech_started = True
                        recorded_blocks.extend(list(pre_roll))
                        self.publish_status('speech_detected')
                        self.get_logger().info(
                            'Speech detected. Recording started. '
                            f'mode={active_listen_mode}, '
                            f'rms={block_rms:.1f}, peak={block_peak}, '
                            f'noise_floor={noise_floor:.1f}, '
                            f'adaptive_end_threshold={adaptive_end_threshold:.1f}'
                        )
                    elif total_blocks >= start_timeout_blocks:
                        self.get_logger().warning('No speech detected before timeout.')
                        return None
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

        if (
            self._shutdown_requested
            or self._cancel_requested.is_set()
            or not recorded_blocks
        ):
            return None

        audio = np.concatenate(recorded_blocks, axis=0)
        minimum_samples = int(self.min_record_duration * self.sample_rate)
        if len(audio) < minimum_samples:
            self.get_logger().warning('Detected speech was too short.')
            return None
        return audio

    @staticmethod
    def select_max_speech_duration(
        listen_mode: str,
        normal_max_duration: float,
        confirmation_max_duration: float,
    ) -> float:
        normal = max(1.0, float(normal_max_duration))
        if str(listen_mode).strip().lower() == 'confirmation':
            return min(normal, max(1.0, float(confirmation_max_duration)))
        return normal

    @staticmethod
    def select_initial_prompt(
        listen_mode: str,
        normal_prompt: str,
        confirmation_prompt: str,
    ) -> str:
        if str(listen_mode).strip().lower() == 'confirmation':
            return str(confirmation_prompt)
        return str(normal_prompt)

    def record_and_transcribe(self) -> None:
        try:
            self.publish_status('listening')
            start_time = time.monotonic()
            audio = self.record_until_silence()

            if self._shutdown_requested:
                return
            if self._cancel_requested.is_set():
                self.get_logger().info('STT capture cancelled before transcription.')
                self.publish_status('cancelled')
                return
            if audio is None:
                self.publish_status('no_speech')
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

            if self._cancel_requested.is_set():
                self.publish_status('cancelled')
                return

            with self._lock:
                active_listen_mode = self._active_listen_mode
            active_initial_prompt = self.select_initial_prompt(
                active_listen_mode,
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

            if self._shutdown_requested:
                return
            if self._cancel_requested.is_set():
                self.get_logger().info('Discarded STT result because the turn was cancelled.')
                self.publish_status('cancelled')
                return

            text = ' '.join(segment.text for segment in segments).strip()
            text = self.clean_text(text)

            # The ROS microphone VAD already proved that this clip contains a
            # sustained loud utterance. Faster-Whisper's second internal VAD can
            # still remove short Korean replies such as "네 잔이요" entirely.
            # Retry only that empty-result case without the inner VAD; normal
            # successful turns keep the existing filtering and cost unchanged.
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
            self.text_publisher.publish(message)

            elapsed = time.monotonic() - start_time
            self.get_logger().info(f'Published voice text: {text}')
            self.get_logger().info(f'Total STT processing time: {elapsed:.2f}s')
            self.publish_status('done')
        except Exception as error:
            if not self._shutdown_requested:
                self.get_logger().error(f'STT failed: {error}')
                self.publish_status(f'error:{error}')
        finally:
            with self._lock:
                self._busy = False

    @staticmethod
    def clean_text(text: str) -> str:
        text = str(text).strip()
        return re.sub(r'\s+', ' ', text)

    @staticmethod
    def normalize_short_confirmation(text: str) -> str:
        """Recover repeated or elongated Whisper output for short yes/no answers.

        Very short Korean confirmations can be decoded as repeated tokens
        (``네네네...``) or as a stretched vowel (``네에에에...``). Keep the
        generic repetition filter for real noise, but recover only full-string
        forms that unambiguously correspond to a supported confirmation token.
        """

        compact = re.sub(r'[^0-9A-Za-z가-힣]', '', str(text)).lower()
        repetitions = (
            ('네', '네'),
            ('예', '예'),
            ('응', '응'),
            ('아니요', '아니요'),
            ('아뇨', '아뇨'),
            ('아니', '아니요'),
        )
        for token, normalized in repetitions:
            if re.fullmatch(rf'(?:{re.escape(token)}){{2,}}', compact):
                return normalized

        elongated_patterns = (
            (r'네[에예]+', '네'),
            (r'예[에예]+', '예'),
            (r'응[으응]+', '응'),
            (r'아니[이]+요', '아니요'),
            (r'아니요[오요]+', '아니요'),
            (r'아뇨[오요]+', '아뇨'),
        )
        for pattern, normalized in elongated_patterns:
            if re.fullmatch(pattern, compact):
                return normalized
        return str(text).strip()

    def should_reject_text(self, text: str) -> bool:
        compact = re.sub(r'[^0-9A-Za-z가-힣]', '', text)
        allowed_short_orders = {
            '아아', '뜨아', '라떼', '아메',
            '네', '예', '응', '아니', '아니요', '아뇨',
        }
        if compact in allowed_short_orders:
            return False

        rejected_phrases = {'아', '어', '음', '나이쁘다'}
        if compact in rejected_phrases:
            return True
        # A duplicated bare "스무디" token is not a supported menu. This exact
        # artifact appeared in live audio when Whisper mixed up 딸기스무디 and
        # the quantity phrase 스무 잔. Retry STT instead of confirming a phantom
        # 아메리카노 order from the malformed transcript.
        if '스무디스무디' in compact:
            return True
        if len(compact) >= 4 and len(set(compact)) <= 2:
            return True
        return False

    @staticmethod
    def get_audio_level(audio: np.ndarray) -> tuple[float, int]:
        if audio.size == 0:
            return 0.0, 0
        values = audio.astype('float32')
        rms = math.sqrt(float((values * values).mean()))
        peak = int(np.abs(audio.astype('int32')).max())
        return rms, peak

    def publish_status(self, status: str) -> None:
        if self._shutdown_requested or not rclpy.ok():
            return
        message = String()
        message.data = status
        try:
            self.status_publisher.publish(message)
        except Exception:
            if not self._shutdown_requested:
                raise
            return
        Path('/tmp/pumpkin_stt_status').write_text(status, encoding='utf-8')

    def destroy_node(self):
        self._shutdown_requested = True
        with self._lock:
            self._start_token += 1
        self._cancel_requested.set()
        READY_FILE.unlink(missing_ok=True)
        return super().destroy_node()


class _SafeSTTMixin:
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


class _UnbiasedSTTMixin:
    """Production STT without lexical initial-prompt bias.

    The previous confirmation prompt contained menu names and instructional text
    such as ``메뉴를 고치면 ... 중 하나를 말합니다``. During a noisy/weak
    confirmation turn Faster-Whisper can emit prompt-like text that the customer
    never said. This runtime deliberately supplies no initial prompt at all.

    Korean decoding is still constrained with ``language='ko'`` by the parent
    runtime, while menu/temperature/quantity interpretation remains the NLU's job.
    """

    LEGACY_PROMPT_MENU_WORDS = (
        "아메리카노",
        "카페라떼",
        "바닐라라떼",
        "딸기스무디",
        "레몬에이드",
    )
    LEGACY_PROMPT_MARKERS = (
        "메뉴를고치면",
        "중하나를말합니다",
        "한국어카페주문",
        "짧은확인답변은",
        "온도표현은",
        "수량표현은",
        "메뉴는아메리카노",
    )
    CONFIRMATION_START_BLOCKS_ENV = "PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS"

    def __init__(self) -> None:
        super().__init__()
        # Keep these empty for observability as well as decoding. select_initial_prompt
        # below returns None, so Faster-Whisper receives no prompt tokens.
        self.initial_prompt = ""
        self.confirmation_initial_prompt = ""

        # The parent node already separates normal and confirmation start-block
        # counts. The physical launcher can therefore make short yes/no replies
        # easier to trigger without weakening normal-order VAD equally.
        self.confirmation_speech_start_blocks = self._configured_confirmation_start_blocks(
            self.confirmation_speech_start_blocks
        )

        self.get_logger().info(
            "Whisper lexical initial prompts disabled; decoding uses audio + language only"
        )
        self.get_logger().info(
            "Physical VAD profile: "
            f"threshold={self.speech_threshold:.1f}, "
            f"normal_start_blocks={self.speech_start_blocks}, "
            f"confirmation_start_blocks={self.confirmation_speech_start_blocks}, "
            f"end_threshold={self.end_threshold:.1f}, "
            f"silence={self.silence_duration:.2f}s"
        )

    @classmethod
    def _configured_confirmation_start_blocks(cls, fallback: int) -> int:
        raw = os.getenv(cls.CONFIRMATION_START_BLOCKS_ENV, "").strip()
        if not raw:
            return max(1, int(fallback))
        try:
            return max(1, int(raw))
        except ValueError:
            return max(1, int(fallback))

    @staticmethod
    def select_initial_prompt(
        listen_mode: str,
        normal_prompt: str,
        confirmation_prompt: str,
    ) -> None:
        del listen_mode, normal_prompt, confirmation_prompt
        return None

    @classmethod
    def looks_like_legacy_prompt_leak(cls, text: str) -> bool:
        compact = re.sub(r"[^0-9A-Za-z가-힣]", "", str(text)).lower()
        if not compact:
            return False

        marker_hits = sum(marker in compact for marker in cls.LEGACY_PROMPT_MARKERS)
        menu_hits = sum(menu in compact for menu in cls.LEGACY_PROMPT_MENU_WORDS)

        # The exact live hallucination contained instructional prompt prose plus
        # several menu names. Require strong prompt-like evidence so ordinary
        # multi-menu orders are never rejected merely for naming several drinks.
        if marker_hits >= 2:
            return True
        if "중하나를말합니다" in compact and menu_hits >= 2:
            return True
        if "메뉴를고치면" in compact and menu_hits >= 2:
            return True
        return False

    def should_reject_text(self, text: str) -> bool:
        if super().should_reject_text(text):
            return True
        return self.looks_like_legacy_prompt_leak(text)


class STTNode(_UnbiasedSTTMixin, _SafeSTTMixin, _CoreSTTNode):
    """Production STT node with safe per-turn capture and unbiased decoding."""


def main(args=None) -> None:
    rclpy.init(args=args)
    node = STTNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
