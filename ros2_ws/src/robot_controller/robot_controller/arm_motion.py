from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping


HOME = {
    4: 90.0,
    5: 90.0,
    6: 90.0,
    7: 1.0,
    8: 1.0,
    9: 140.0,
    10: 179.0,
}

POSES = {
    "right": {
        4: 179.0,
        5: 1.0,
        6: 90.0,
        7: 179.0,
        8: 179.0,
        9: 140.0,
        10: 179.0,
    },
    "left": {
        4: 90.0,
        5: 90.0,
        6: 90.0,
        7: 179.0,
        8: 1.0,
        9: 140.0,
        10: 179.0,
    },
    "unsure": {
        4: 179.0,
        5: 1.0,
        6: 90.0,
        7: 179.0,
        8: 1.0,
        9: 140.0,
        10: 179.0,
    },
    "greeting": {
        4: 179.0,
        5: 1.0,
        6: 90.0,
        7: 179.0,
        8: 75.0,
        9: 1.0,
        10: 179.0,
    },
}

ARM_ACTION_TO_POSE = {
    "POINT_RIGHT": "right",
    "POINT_LEFT": "left",
    "UNSURE": "unsure",
    "GOODBYE_WAVE": "greeting",
    # Backward-compatible alias for direct/manual publishers. START_ORDER does
    # not emit this action; the production wave is reserved for customer exit.
    "GREETING": "greeting",
}


def normalize_arm_action(value: object) -> str | None:
    action = str(value or "").strip().upper()
    return action if action in ARM_ACTION_TO_POSE else None


def smoothstep(value: float) -> float:
    return value * value * (3.0 - 2.0 * value)


def _validated_pose(pose: Mapping[int, float]) -> dict[int, float]:
    if set(pose) != set(HOME):
        raise ValueError("every arm pose must define exactly CH4 through CH10")
    result = {int(channel): float(angle) for channel, angle in pose.items()}
    for channel, angle in result.items():
        if not 0.0 <= angle <= 180.0:
            raise ValueError(f"CH{channel} angle {angle} is outside 0..180")
    return result


for _pose in POSES.values():
    _validated_pose(_pose)


@dataclass(frozen=True)
class ArmMotionConfig:
    pose_steps: int = 140
    pose_step_delay: float = 0.01
    home_steps: int = 220
    home_step_delay: float = 0.01
    pose_hold_seconds: float = 1.2
    wave_dwell_seconds: float = 0.35


class ArmMotionController:
    """Execute one validated arm gesture and always return to HOME.

    ``apply_angles`` is injected so the sequence can be tested without ROS or
    physical hardware. The runtime supplies the single PCA9685 driver's
    multi-channel writer, allowing head and arm writes to share one board.
    """

    def __init__(
        self,
        apply_angles: Callable[[Mapping[int, float]], None],
        *,
        sleep: Callable[[float], None] = time.sleep,
        config: ArmMotionConfig | None = None,
    ) -> None:
        self._apply_angles = apply_angles
        self._sleep = sleep
        self.config = config or ArmMotionConfig()
        self.current = dict(HOME)

    def run_action(self, action: object) -> bool:
        normalized = normalize_arm_action(action)
        if normalized is None:
            return False
        self.run_pose(ARM_ACTION_TO_POSE[normalized])
        return True

    def run_pose(self, pose_name: str) -> None:
        if pose_name not in POSES:
            raise ValueError(f"unsupported arm pose: {pose_name}")

        target = _validated_pose(POSES[pose_name])
        try:
            self._move(target, self.config.pose_steps, self.config.pose_step_delay)
            self._sleep(max(0.0, self.config.pose_hold_seconds))
            if pose_name == "greeting":
                self._run_wave()
        finally:
            # Normal guide, unsure and goodbye paths all end at the same stable
            # attention pose, including when a wave step raises an exception.
            self._move(HOME, self.config.home_steps, self.config.home_step_delay)

    def _move(self, target: Mapping[int, float], steps: int, delay: float) -> None:
        validated_target = _validated_pose(target)
        start = dict(self.current)
        step_count = max(1, int(steps))
        step_delay = max(0.0, float(delay))

        for index in range(1, step_count + 1):
            ratio = smoothstep(index / step_count)
            position = {
                channel: start[channel]
                + (validated_target[channel] - start[channel]) * ratio
                for channel in HOME
            }
            self._apply_angles(position)
            self.current = position
            self._sleep(step_delay)

        self.current = dict(validated_target)

    def _run_wave(self) -> None:
        for angle in (1.0, 105.0, 1.0, 105.0, 1.0, 105.0):
            position = dict(self.current)
            position[8] = angle
            self._apply_angles(position)
            self.current = position
            self._sleep(max(0.0, self.config.wave_dwell_seconds))
