#!/usr/bin/env python3
"""Guided safe ON/OFF sequence for Pumpkin PCA9685 servos.

This script does NOT switch the 220 V inlet. The current robot has no Jetson-
controlled DC power switch between LRS-150F-5 and the servo fuse box, so the
operator still flips the inlet manually.

What this script controls:
- PCA9685 OE (Output Enable) from Jetson GPIO.
- PCA9685 initialization while outputs are disabled.
- Preloading the confirmed HOME targets before servo 5 V is enabled.

Required wiring before use:
- Jetson 40-pin header BOARD pin 12 -> PCA9685 OE
- Jetson GND -> PCA9685 GND / common signal GND

IMPORTANT:
- OE HIGH = PWM outputs disabled.
- OE LOW  = PWM outputs enabled.
- The arm must be mechanically supported whenever servo torque can disappear.
- Do not use this script until the abnormal-voltage fault has been isolated.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Mapping


OE_BOARD_PIN = int(os.environ.get("PUMPKIN_PCA_OE_BOARD_PIN", "12"))
SERVO_POWER_SETTLE_SEC = float(os.environ.get("PUMPKIN_SERVO_POWER_SETTLE_SEC", "1.0"))
POWER_DOWN_WAIT_SEC = float(os.environ.get("PUMPKIN_SERVO_POWER_DOWN_WAIT_SEC", "2.0"))

# Confirmed physical neutral/attention values already used by the repository.
HOME: dict[int, float] = {
    0: 60.0,   # head tilt center
    1: 90.0,   # head pan center
    4: 90.0,
    5: 90.0,
    6: 90.0,
    7: 1.0,
    8: 1.0,
    9: 140.0,
    10: 179.0,
}
ARM_CHANNELS = tuple(range(4, 11))


def _gpio():
    try:
        import Jetson.GPIO as GPIO
    except Exception as exc:  # pragma: no cover - hardware only
        raise RuntimeError(f"Jetson.GPIO import failed: {exc}") from exc

    GPIO.setwarnings(False)
    GPIO.setmode(GPIO.BOARD)
    return GPIO


def _set_oe_disabled(disabled: bool) -> None:
    """Drive PCA9685 OE without calling GPIO.cleanup().

    The pin is deliberately left in its last output state after this short
    command exits. A future hardware fail-safe must still make OE default HIGH
    when the Jetson is unpowered or rebooting.
    """

    GPIO = _gpio()
    level = GPIO.HIGH if disabled else GPIO.LOW
    GPIO.setup(OE_BOARD_PIN, GPIO.OUT, initial=level)
    GPIO.output(OE_BOARD_PIN, level)
    print(
        f"[OE] BOARD pin {OE_BOARD_PIN} -> "
        f"{'HIGH / PWM DISABLED' if disabled else 'LOW / PWM ENABLED'}"
    )


def _make_kit_and_preload_home():
    try:
        from adafruit_servokit import ServoKit
    except Exception as exc:  # pragma: no cover - hardware only
        raise RuntimeError(f"adafruit_servokit import failed: {exc}") from exc

    kit = ServoKit(channels=16)

    # Keep the arm calibration identical to the existing physical arm scripts.
    for channel in ARM_CHANNELS:
        kit.servo[channel].set_pulse_width_range(1000, 2000)

    # OE is HIGH while these registers are written, so the servo pins do not
    # produce active PWM yet. Enabling OE later applies the already-known HOME.
    for channel, angle in HOME.items():
        kit.servo[channel].angle = angle

    print("[PCA9685] I2C communication OK; HOME PWM registers preloaded.")
    return kit


def _require_exact(prompt: str, expected: str) -> None:
    value = input(prompt).strip().upper()
    if value != expected:
        raise RuntimeError(
            f"Cancelled: expected '{expected}', received '{value or '<empty>'}'."
        )


def power_on() -> None:
    print("\n=== Pumpkin servo SAFE POWER-ON ===")
    print("1) Keep the LRS/servo inlet switch OFF.")
    print("2) Support the arm so gravity cannot make a joint drop.")
    print("3) Keep people/objects outside the arm sweep area.")

    # First action must be disabling PCA outputs before touching its PWM state.
    _set_oe_disabled(True)

    try:
        _make_kit_and_preload_home()
    except Exception:
        # Leave OE disabled if PCA initialization fails.
        _set_oe_disabled(True)
        raise

    print("\nThe PCA9685 is ready while PWM remains disabled.")
    print("The stored target is the repository's confirmed HOME/attention pose:")
    print("  " + ", ".join(f"CH{ch}={angle:g}" for ch, angle in HOME.items()))
    print("Do not force a geared servo by hand. Support the arm instead.")
    _require_exact("If the arm is supported and the inlet is still OFF, type READY: ", "READY")

    print("\nNow turn the servo/LRS inlet switch ON.")
    print("Keep supporting the arm; PWM is still disabled at this point.")
    _require_exact("After the inlet is ON, type ON: ", "ON")

    time.sleep(max(0.0, SERVO_POWER_SETTLE_SEC))
    print("[WAIT] Servo 5 V rail settle time completed.")

    print("Enabling PWM now. The servos may move toward HOME.")
    _set_oe_disabled(False)
    print("[OK] Servo PWM enabled. You can now start the robot runtime.")


def power_off() -> None:
    print("\n=== Pumpkin servo SAFE POWER-OFF ===")
    print("Before continuing:")
    print("1) Finish the current robot action and confirm the arm is at HOME/attention.")
    print("2) Stop the robot runtime so no new motor command can arrive.")
    print("3) Physically support the arm before torque disappears.")
    print("4) Keep Jetson/PCA9685 logic power ON during the servo power-down.")
    print()
    print("Do NOT disable OE first during normal shutdown.")
    print("The existing PWM is intentionally kept stable until servo 5 V is removed;")
    print("otherwise the powered arm could lose holding torque before the inlet is OFF.")

    _require_exact("If all four conditions are satisfied, type READY: ", "READY")

    print("\nNow turn the servo/LRS inlet switch OFF while continuing to support the arm.")
    _require_exact("After the inlet is OFF, type OFF: ", "OFF")

    time.sleep(max(0.0, POWER_DOWN_WAIT_SEC))
    _set_oe_disabled(True)
    print("[OK] Servo power is OFF and PCA9685 PWM outputs are disabled.")
    print("The Jetson may now be shut down if needed.")


def emergency_disable() -> None:
    print("\n=== EMERGENCY PWM DISABLE ===")
    print("WARNING: disabling PWM can immediately remove servo holding torque.")
    print("Support the arm first if doing so does not expose you to moving hardware.")
    _require_exact("Type DISABLE to force PCA9685 OE HIGH: ", "DISABLE")
    _set_oe_disabled(True)
    print("[OK] PCA9685 PWM outputs forced disabled.")


def show_home() -> None:
    print("Confirmed HOME/attention targets:")
    for channel, angle in HOME.items():
        print(f"  CH{channel}: {angle:g} deg")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Guided PCA9685/servo power ON-OFF safety sequence."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("on", help="Prepare PCA safely, then guide manual inlet ON.")
    sub.add_parser("off", help="Guide manual inlet OFF, then disable PCA outputs.")
    sub.add_parser(
        "emergency-disable",
        help="Immediately force OE HIGH after an explicit confirmation.",
    )
    sub.add_parser("show-home", help="Print the current confirmed HOME targets.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "on":
            power_on()
        elif args.command == "off":
            power_off()
        elif args.command == "emergency-disable":
            emergency_disable()
        elif args.command == "show-home":
            show_home()
        else:  # pragma: no cover
            raise RuntimeError(f"unknown command: {args.command}")
        return 0
    except (RuntimeError, KeyboardInterrupt) as exc:
        print(f"\n[STOP] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
