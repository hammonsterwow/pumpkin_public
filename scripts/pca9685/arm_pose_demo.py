#!/usr/bin/env python3
"""Run the confirmed Pumpkin arm demonstration poses through PCA9685.

Temporary direct-control path:
    Jetson -> I2C -> PCA9685 -> servos

The final architecture may route commands through ESP32, but this script
captures the physical pose values validated on the assembled arm.
Run only when the arm is already in the HOME (attention) pose.
"""

from __future__ import annotations

import argparse
import sys
import time
from typing import Mapping

HOME = {
    4: 90,
    5: 90,
    6: 90,
    7: 1,
    8: 1,
    9: 140,
    10: 179,
}

POSES = {
    # The physical arm directions were confirmed after the first naming pass.
    # Keep these angle values intact; only the right/left names are swapped.
    "right": {
        4: 179,
        5: 1,
        6: 90,
        7: 179,
        8: 179,
        9: 140,
        10: 179,
    },
    "left": {
        4: 90,
        5: 90,
        6: 90,
        7: 179,
        8: 1,
        9: 140,
        10: 179,
    },
    "unsure": {
        4: 179,
        5: 1,
        6: 90,
        7: 179,
        8: 1,
        9: 140,
        10: 179,
    },
    "greeting": {
        4: 179,
        5: 1,
        6: 90,
        7: 179,
        8: 75,
        9: 1,
        10: 179,
    },
}

PULSE_MIN_US = 1000
PULSE_MAX_US = 2000
POSE_STEPS = 140
POSE_STEP_DELAY = 0.01
HOME_STEPS = 220
HOME_STEP_DELAY = 0.01
POSE_HOLD_SECONDS = 1.2
WAVE_DWELL_SECONDS = 0.35


def smoothstep(value: float) -> float:
    """Cubic ease-in/ease-out position interpolation."""
    return value * value * (3.0 - 2.0 * value)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a confirmed arm pose from HOME, then return to HOME."
    )
    parser.add_argument("pose", choices=tuple(POSES))
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip the RUN confirmation after checking that the arm is at HOME.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the pose data without energising any servo.",
    )
    return parser.parse_args()


def validate_pose(pose: Mapping[int, int]) -> None:
    if set(pose) != set(HOME):
        raise ValueError("every pose must define exactly CH4 through CH10")
    for channel, angle in pose.items():
        if not 0 <= angle <= 180:
            raise ValueError(f"CH{channel} angle {angle} is outside 0..180")


def move_smooth(kit, start: Mapping[int, int], end: Mapping[int, int], steps: int, delay: float) -> None:
    for index in range(1, steps + 1):
        ratio = smoothstep(index / steps)
        for channel in HOME:
            kit.servo[channel].angle = start[channel] + (
                end[channel] - start[channel]
            ) * ratio
        time.sleep(delay)


def set_servo_now(kit, channel: int, angle: int) -> None:
    """Command one position immediately; the servo moves at its own max speed."""
    kit.servo[channel].angle = angle
    time.sleep(WAVE_DWELL_SECONDS)


def run_greeting_wave(kit) -> dict[int, int]:
    """CH8: 75 -> 1 -> 105 -> 1 -> 105 -> 1 -> 105."""
    current = dict(POSES["greeting"])
    for angle in (1, 105, 1, 105, 1, 105):
        set_servo_now(kit, 8, angle)
        current[8] = angle
    return current


def confirm(args: argparse.Namespace) -> None:
    if args.yes or args.dry_run:
        return
    print("Before continuing:")
    print("- The arm is physically at the HOME pose.")
    print("- Servo power can be cut immediately.")
    print("- No person or object is in the arm sweep area.")
    if input("Type RUN to start the pose sequence: ").strip() != "RUN":
        raise RuntimeError("cancelled; no servo command was sent")


def main() -> int:
    args = parse_args()
    target = POSES[args.pose]
    validate_pose(HOME)
    validate_pose(target)

    print(f"HOME: {HOME}")
    print(f"{args.pose}: {target}")
    if args.dry_run:
        return 0

    confirm(args)

    from adafruit_servokit import ServoKit

    kit = ServoKit(channels=16)
    for channel in HOME:
        kit.servo[channel].set_pulse_width_range(PULSE_MIN_US, PULSE_MAX_US)

    # This script deliberately assumes the real arm starts at HOME. It does not
    # first command HOME, because an unknown heavy-arm position may fall/jump.
    move_smooth(kit, HOME, target, POSE_STEPS, POSE_STEP_DELAY)
    print(f"{args.pose} pose reached.")
    time.sleep(POSE_HOLD_SECONDS)

    final_position = target
    if args.pose == "greeting":
        final_position = run_greeting_wave(kit)
        print("Greeting wave completed.")

    move_smooth(kit, final_position, HOME, HOME_STEPS, HOME_STEP_DELAY)
    print("Returned to HOME.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
