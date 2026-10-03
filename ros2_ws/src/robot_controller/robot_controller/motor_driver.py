from __future__ import annotations

from dataclasses import dataclass
import threading
from typing import Mapping, Protocol


@dataclass(frozen=True)
class MotorCommand:
    pan: float
    tilt: float


class MotorDriver(Protocol):
    def set_angles(self, command: MotorCommand) -> None:
        """Apply pan/tilt target angles."""

    def set_servo_angles(self, angles: Mapping[int, float]) -> None:
        """Apply arbitrary PCA9685 servo-channel targets."""

    def close(self) -> None:
        """Release hardware resources."""


class MockMotorDriver:
    """Hardware-free driver used for development and tests."""

    def __init__(self) -> None:
        self.last_command: MotorCommand | None = None
        self.last_servo_angles: dict[int, float] = {}
        self.servo_history: list[dict[int, float]] = []

    def set_angles(self, command: MotorCommand) -> None:
        self.last_command = command
        print(f'[MOCK MOTOR] pan={command.pan:.1f}, tilt={command.tilt:.1f}')

    def set_servo_angles(self, angles: Mapping[int, float]) -> None:
        applied = {int(channel): float(angle) for channel, angle in angles.items()}
        self.last_servo_angles = applied
        self.servo_history.append(applied)

    def close(self) -> None:
        pass


class PCA9685MotorDriver:
    """Jetson I2C -> PCA9685 -> pan/tilt servo backend.

    Channel mapping confirmed on hardware:
      - channel 0: tilt (nod)
      - channel 1: pan (shake / turn left / turn right)
    """

    def __init__(
        self,
        *,
        channels: int = 16,
        tilt_channel: int = 0,
        pan_channel: int = 1,
        release_on_close: bool = True,
    ) -> None:
        try:
            from adafruit_servokit import ServoKit
        except ImportError as exc:
            raise RuntimeError(
                'adafruit-circuitpython-servokit is required for the PCA9685 backend.'
            ) from exc

        self._channels = int(channels)
        self._kit = ServoKit(channels=self._channels)
        self._tilt_channel = int(tilt_channel)
        self._pan_channel = int(pan_channel)
        self._release_on_close = bool(release_on_close)
        self._io_lock = threading.Lock()

        # Physical arm calibration used 1000..2000 us on CH4..CH10. Setting the
        # range does not move a servo; positions are sent only after an action.
        for channel in range(4, 11):
            if channel < self._channels:
                self._kit.servo[channel].set_pulse_width_range(1000, 2000)

    def set_angles(self, command: MotorCommand) -> None:
        with self._io_lock:
            self._kit.servo[self._pan_channel].angle = float(command.pan)
            self._kit.servo[self._tilt_channel].angle = float(command.tilt)

    def set_servo_angles(self, angles: Mapping[int, float]) -> None:
        validated: dict[int, float] = {}
        for channel, angle in angles.items():
            channel_i = int(channel)
            angle_f = float(angle)
            if not 0 <= channel_i < self._channels:
                raise ValueError(f'PCA9685 channel {channel_i} is outside range')
            if not 0.0 <= angle_f <= 180.0:
                raise ValueError(f'CH{channel_i} angle {angle_f} is outside 0..180')
            validated[channel_i] = angle_f

        with self._io_lock:
            for channel, angle in validated.items():
                self._kit.servo[channel].angle = angle

    def close(self) -> None:
        """Release PWM unless an enabled arm must keep holding HOME.

        Head-only runs release channels to avoid post-exit buzzing. When the
        physical arm is enabled, shutdown must keep holding torque until the
        operator supports the arm and removes servo power.
        """
        if not self._release_on_close:
            return

        with self._io_lock:
            # This driver exclusively owns the PCA9685, so release every channel
            # rather than only pan/tilt. This also guarantees that arm servos from
            # an earlier enabled run do not remain energized after shutdown.
            for channel in range(self._channels):
                try:
                    self._kit.servo[channel].angle = None
                except Exception:
                    # Continue releasing the remaining channels even if one
                    # channel object cannot be configured as a positional servo.
                    pass

            # ServoKit does not currently expose a public close/deinit method,
            # but its PCA9685 instance provides deinit(). Keep this defensive so
            # a future ServoKit implementation change cannot break shutdown.
            pca = getattr(self._kit, "_pca", None)
            deinit = getattr(pca, "deinit", None)
            if callable(deinit):
                deinit()
