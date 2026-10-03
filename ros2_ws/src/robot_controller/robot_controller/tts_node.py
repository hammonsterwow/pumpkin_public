from __future__ import annotations

import hashlib
import json
import os
import queue
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import edge_tts
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


def build_tts_cache_key(
    text: str,
    *,
    voice: str,
    rate: str,
    volume: str,
    pitch: str,
) -> str:
    """Return a stable key for one synthesized waveform and voice profile."""

    payload = json.dumps(
        {
            'text': str(text),
            'voice': str(voice),
            'rate': str(rate),
            'volume': str(volume),
            'pitch': str(pitch),
        },
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    ).encode('utf-8')
    return hashlib.sha256(payload).hexdigest()


def cached_audio_is_usable(path: Path) -> bool:
    """Reject missing or interrupted WAV writes before attempting playback."""

    try:
        return path.is_file() and path.stat().st_size > 44
    except OSError:
        return False


class TTSNode(Node):
    """Speak robot responses through the dedicated playback device."""

    def __init__(self) -> None:
        super().__init__('tts_node')

        self.declare_parameter('action_topic', '/robot_action')
        self.declare_parameter('text_topic', '/tts/text')
        self.declare_parameter('status_topic', '/tts/status')
        self.declare_parameter('voice', 'ko-KR-SunHiNeural')
        self.declare_parameter('rate', '+5%')
        self.declare_parameter('volume', '+0%')
        self.declare_parameter('pitch', '+3Hz')
        self.declare_parameter('player', 'auto')
        self.declare_parameter('alsa_device', 'auto')
        self.declare_parameter('duplicate_suppression_sec', 1.0)
        self.declare_parameter('cache_enabled', True)
        self.declare_parameter(
            'cache_dir',
            os.getenv('PUMPKIN_TTS_CACHE_DIR', '~/.cache/pumpkin/tts'),
        )

        self.voice = str(self.get_parameter('voice').value)
        self.rate = str(self.get_parameter('rate').value)
        self.volume = str(self.get_parameter('volume').value)
        self.pitch = str(self.get_parameter('pitch').value)
        self.player = str(self.get_parameter('player').value).strip().lower()
        self.requested_alsa_device = str(
            self.get_parameter('alsa_device').value
        ).strip()
        self.alsa_device = self.resolve_alsa_device(self.requested_alsa_device)
        self.duplicate_suppression_sec = max(
            0.0,
            float(self.get_parameter('duplicate_suppression_sec').value),
        )
        self.cache_enabled = bool(self.get_parameter('cache_enabled').value)
        self.cache_dir = Path(
            str(self.get_parameter('cache_dir').value)
        ).expanduser()
        if self.cache_enabled:
            try:
                self.cache_dir.mkdir(parents=True, exist_ok=True)
            except OSError as error:
                self.cache_enabled = False
                self.get_logger().warning(
                    f'TTS cache disabled because its directory is unavailable: {error}'
                )

        self.audio_player = self.resolve_audio_player(self.player)
        if self.audio_player is None:
            raise RuntimeError(
                'paplay 또는 aplay가 없습니다. '
                'sudo apt install -y pulseaudio-utils alsa-utils 로 설치하세요.'
            )

        self.status_publisher = self.create_publisher(
            String,
            str(self.get_parameter('status_topic').value),
            10,
        )
        self.action_subscription = self.create_subscription(
            String,
            str(self.get_parameter('action_topic').value),
            self.action_callback,
            10,
        )
        self.text_subscription = self.create_subscription(
            String,
            str(self.get_parameter('text_topic').value),
            self.text_callback,
            10,
        )

        self._speech_queue: queue.Queue[str | None] = queue.Queue()
        self._enqueue_lock = threading.Lock()
        self._last_enqueued_text = ''
        self._last_enqueued_at = 0.0
        self._shutdown_requested = False
        self._worker = threading.Thread(
            target=self.speech_worker,
            daemon=True,
            name='pumpkin-tts-worker',
        )
        self._worker.start()

        requested_suffix = ''
        if self.requested_alsa_device != self.alsa_device:
            requested_suffix = f', requested_alsa_device={self.requested_alsa_device}'
        self.get_logger().info(
            f'TTS node started: voice={self.voice}, rate={self.rate}, '
            f'player={Path(self.audio_player).name}, alsa_device={self.alsa_device}'
            f'{requested_suffix}, '
            f'duplicate_suppression={self.duplicate_suppression_sec:.2f}s, '
            f'cache={"on" if self.cache_enabled else "off"}, '
            f'cache_dir={self.cache_dir}'
        )
        self.publish_status('ready')

    @staticmethod
    def resolve_audio_player(requested_player: str) -> str | None:
        if requested_player == 'paplay':
            return shutil.which('paplay')
        if requested_player == 'aplay':
            return shutil.which('aplay')
        return shutil.which('paplay') or shutil.which('aplay')

    @staticmethod
    def _alsa_playback_devices() -> list[tuple[str, str]]:
        """Return ALSA hardware playback devices as (plughw, description)."""
        aplay = shutil.which('aplay')
        if aplay is None:
            return []

        env = os.environ.copy()
        env['LC_ALL'] = 'C'
        try:
            result = subprocess.run(
                [aplay, '-l'],
                check=False,
                capture_output=True,
                text=True,
                env=env,
                timeout=3.0,
            )
        except (OSError, subprocess.SubprocessError):
            return []

        devices: list[tuple[str, str]] = []
        pattern = re.compile(r'^card\s+(\d+):.*?device\s+(\d+):', re.IGNORECASE)
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            match = pattern.search(line)
            if match is None:
                continue
            card, device = match.groups()
            devices.append((f'plughw:{card},{device}', line))
        return devices

    @classmethod
    def resolve_alsa_device(cls, requested_device: str) -> str:
        """Resolve the ALSA device used for robot TTS playback.

        An explicit device must always be preserved. In the physical Pumpkin
        setup ReSpeaker Lite is intentionally used for both capture and playback
        so its hardware AEC receives the robot playback reference. Re-routing
        an explicit ``plughw:0,0`` request to another ALSA device breaks that
        path and can make TTS inaudible on the robot.

        Automatic device discovery is used only when the caller passes ``auto``
        or an empty value.
        """
        requested = str(requested_device or '').strip()
        normalized = requested.lower()

        if normalized not in {'', 'auto'}:
            return requested
        devices = cls._alsa_playback_devices()
        if not devices:
            return 'default' if normalized in {'', 'auto'} else requested

        non_respeaker = [
            (device, description)
            for device, description in devices
            if 'respeaker' not in description.lower()
        ]

        # First choice: a device whose ALSA description explicitly says speaker.
        for device, description in non_respeaker:
            text = description.lower()
            if 'speaker' in text:
                return device

        # Second choice: another USB playback device.  The project BOM records
        # the TTS hardware as a separate USB Speaker, but its exact product name
        # is not fixed and may appear simply as "USB Audio".
        for device, description in non_respeaker:
            if 'usb' in description.lower():
                return device

        # Avoid sending TTS to ReSpeaker when there is any other playback device.
        if non_respeaker:
            return non_respeaker[0][0]

        # No separate playback hardware was detected. Keep the legacy device so
        # an explicit ALSA error is visible instead of silently using ReSpeaker.
        return requested or 'default'

    @staticmethod
    def build_play_command(
        audio_player: str,
        wav_path: str,
        *,
        alsa_device: str = '',
    ) -> list[str]:
        """Build a player command that actually matches the resolved backend."""
        player_name = Path(audio_player).name
        if player_name == 'paplay':
            return [audio_player, wav_path]

        command = [audio_player, '-q']
        if alsa_device:
            command.extend(['-D', alsa_device])
        command.append(wav_path)
        return command

    def action_callback(self, msg: String) -> None:
        try:
            action = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warning('Invalid JSON received on /robot_action.')
            return

        text = str(action.get('tts') or '').strip()
        if text:
            self.enqueue(text)

    def text_callback(self, msg: String) -> None:
        text = msg.data.strip()
        if text:
            self.enqueue(text)

    def enqueue(self, text: str) -> None:
        if self._shutdown_requested:
            return
        now = time.monotonic()
        with self._enqueue_lock:
            duplicate = (
                text == self._last_enqueued_text
                and now - self._last_enqueued_at <= self.duplicate_suppression_sec
            )
            if duplicate:
                self.get_logger().warning(
                    f'Ignored near-simultaneous duplicate TTS text: {text}'
                )
                return
            self._last_enqueued_text = text
            self._last_enqueued_at = now
            self._speech_queue.put(text)

        self.get_logger().info(f'Queued TTS text: {text}')

    def speech_worker(self) -> None:
        while not self._shutdown_requested:
            text = self._speech_queue.get()
            if text is None:
                self._speech_queue.task_done()
                return

            try:
                if self._shutdown_requested:
                    return
                self.publish_status('speaking')
                self.speak(text)
                if self._shutdown_requested:
                    return
                self.publish_status('done')
                self.get_logger().info(f'Spoke: {text}')
            except Exception as error:
                if not self._shutdown_requested:
                    self.get_logger().error(f'TTS failed: {error}')
                    self.publish_status(f'error:{error}')
            finally:
                self._speech_queue.task_done()

    def cache_path_for_text(self, text: str) -> Path | None:
        if not self.cache_enabled:
            return None
        cache_key = build_tts_cache_key(
            text,
            voice=self.voice,
            rate=self.rate,
            volume=self.volume,
            pitch=self.pitch,
        )
        return self.cache_dir / f'{cache_key}.wav'

    def speak(self, text: str) -> None:
        total_started = time.monotonic()
        cache_path = self.cache_path_for_text(text)
        cache_hit = (
            cache_path is not None
            and cached_audio_is_usable(cache_path)
        )
        synthesis_elapsed = 0.0

        with tempfile.TemporaryDirectory() as temp_dir:
            if cache_hit:
                wav = str(cache_path)
                self.get_logger().info(f'TTS cache hit: {cache_path.name}')
            else:
                mp3 = str(Path(temp_dir) / 'speech.mp3')
                wav = str(Path(temp_dir) / 'speech.wav')
                synthesis_started = time.monotonic()

                edge_tts.Communicate(
                    text,
                    self.voice,
                    rate=self.rate,
                    volume=self.volume,
                    pitch=self.pitch,
                ).save_sync(mp3)

                if self._shutdown_requested:
                    return

                subprocess.run(
                    [
                        'ffmpeg',
                        '-y',
                        '-loglevel',
                        'error',
                        '-i',
                        mp3,
                        '-ar',
                        '48000',
                        '-ac',
                        '2',
                        wav,
                    ],
                    check=True,
                )
                synthesis_elapsed = time.monotonic() - synthesis_started

                if cache_path is not None:
                    temporary_cache_path = cache_path.with_name(
                        f'.{cache_path.name}.{os.getpid()}.tmp'
                    )
                    try:
                        shutil.copyfile(wav, temporary_cache_path)
                        os.replace(temporary_cache_path, cache_path)
                        wav = str(cache_path)
                    finally:
                        temporary_cache_path.unlink(missing_ok=True)

                self.get_logger().info(
                    f'TTS cache miss synthesized in {synthesis_elapsed:.3f}s'
                )

            if self._shutdown_requested:
                return

            play_command = self.build_play_command(
                self.audio_player,
                wav,
                alsa_device=self.alsa_device,
            )
            self.get_logger().info(
                f'Playing TTS through {Path(self.audio_player).name} '
                f'on {self.alsa_device}'
            )
            playback_started = time.monotonic()
            subprocess.run(play_command, check=True)
            playback_elapsed = time.monotonic() - playback_started
            total_elapsed = time.monotonic() - total_started
            self.get_logger().info(
                f'TTS timing: cache={"hit" if cache_hit else "miss"}, '
                f'synthesis={synthesis_elapsed:.3f}s, '
                f'playback={playback_elapsed:.3f}s, total={total_elapsed:.3f}s'
            )

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

    def destroy_node(self):
        self._shutdown_requested = True
        self._speech_queue.put(None)
        if self._worker.is_alive():
            self._worker.join(timeout=1.0)
        return super().destroy_node()


def main(args=None) -> None:
    rclpy.init(args=args)
    node = TTSNode()
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
