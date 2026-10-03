#!/usr/bin/env python3
"""Jetson-side USB serial controller for the Pumpkin ESP32 LCD face."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import time
from enum import Enum
from typing import Iterable, Optional, Union

try:
    import serial
    from serial import SerialException
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover - handled at runtime on Jetson
    raise SystemExit(
        "pyserial is required. Install it with: "
        "pip install -r robot_face/jetson/requirements.txt"
    ) from exc


DEFAULT_BAUDRATE = 115200
DEFAULT_RESET_WAIT = 2.0


class Face(str, Enum):
    """Face names understood by the ESP32 firmware."""

    NEUTRAL = "NEUTRAL"
    SMILE = "SMILE"
    HAPPY = "HAPPY"
    QUESTION = "QUESTION"
    ERROR = "ERROR"

    @classmethod
    def parse(cls, value: Union["Face", str]) -> "Face":
        if isinstance(value, cls):
            return value

        normalized = str(value).strip().upper()
        try:
            return cls(normalized)
        except ValueError as exc:
            allowed = ", ".join(face.value for face in cls)
            raise ValueError(
                f"Unknown face {value!r}. Choose one of: {allowed}"
            ) from exc


DEMO_SEQUENCE = (
    Face.NEUTRAL,
    Face.SMILE,
    Face.HAPPY,
    Face.QUESTION,
    Face.ERROR,
    Face.NEUTRAL,
)


class FaceConnectionError(RuntimeError):
    """Raised when the ESP32 serial device cannot be found or opened."""


def describe_ports() -> list[str]:
    """Return human-readable descriptions of currently visible serial ports."""

    descriptions: list[str] = []
    for info in list_ports.comports():
        description = info.description or "no description"
        vid_pid = ""
        if info.vid is not None and info.pid is not None:
            vid_pid = f" VID:PID={info.vid:04X}:{info.pid:04X}"
        descriptions.append(f"{info.device} - {description}{vid_pid}")
    return descriptions


def _score_port(info: object) -> int:
    device = str(getattr(info, "device", "")).lower()
    description = str(getattr(info, "description", "") or "").lower()
    manufacturer = str(getattr(info, "manufacturer", "") or "").lower()
    product = str(getattr(info, "product", "") or "").lower()
    text = " ".join((description, manufacturer, product))

    score = 0

    if device.startswith("/dev/ttyusb"):
        score += 60
    elif device.startswith("/dev/ttyacm"):
        score += 50
    elif device.startswith("com"):
        score += 10

    keywords = (
        "ch340",
        "ch341",
        "wch",
        "cp210",
        "silicon labs",
        "usb serial",
        "usb-serial",
        "uart",
    )
    if any(keyword in text for keyword in keywords):
        score += 80

    vid = getattr(info, "vid", None)
    pid = getattr(info, "pid", None)
    known_usb_uart_ids = {
        (0x1A86, 0x7523),  # WCH CH340
        (0x1A86, 0x5523),  # WCH CH341
        (0x1A86, 0x55D4),  # WCH CH9102
        (0x10C4, 0xEA60),  # Silicon Labs CP210x
        (0x0403, 0x6001),  # FTDI FT232
    }
    if (vid, pid) in known_usb_uart_ids:
        score += 120

    return score


def find_esp32_port() -> str:
    """Find one likely ESP32 USB serial port."""

    ports = list(list_ports.comports())
    if not ports:
        raise FaceConnectionError(
            "No serial ports were found. Check the USB cable and ESP32 power."
        )

    scored = sorted(
        ((_score_port(info), info) for info in ports),
        key=lambda item: (-item[0], str(item[1].device)),
    )
    best_score = scored[0][0]

    if best_score <= 0:
        visible = "\n".join(describe_ports())
        raise FaceConnectionError(
            "Serial ports exist, but none looks like the ESP32.\n"
            f"Visible ports:\n{visible}"
        )

    best = [info for score, info in scored if score == best_score]
    if len(best) > 1:
        choices = "\n".join(
            f"- {info.device}: {info.description}" for info in best
        )
        raise FaceConnectionError(
            "More than one likely ESP32 port was found. "
            "Pass --port explicitly.\n"
            f"{choices}"
        )

    return str(best[0].device)


class FaceController:
    """Keep a long-lived serial connection to the ESP32 face display."""

    def __init__(
        self,
        port: Optional[str] = None,
        *,
        baudrate: int = DEFAULT_BAUDRATE,
        reset_wait: float = DEFAULT_RESET_WAIT,
        write_timeout: float = 1.0,
        auto_connect: bool = True,
    ) -> None:
        self.requested_port = port or os.getenv("PUMPKIN_ESP32_PORT", "auto")
        self.baudrate = baudrate
        self.reset_wait = reset_wait
        self.write_timeout = write_timeout

        self._serial: Optional[serial.Serial] = None
        self._resolved_port: Optional[str] = None
        self._last_face: Optional[Face] = None
        self._lock = threading.RLock()

        if auto_connect:
            self.connect()

    @property
    def port(self) -> Optional[str]:
        return self._resolved_port

    @property
    def is_connected(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def _resolve_port(self) -> str:
        if self.requested_port.lower() == "auto":
            return find_esp32_port()
        return self.requested_port

    def connect(self) -> None:
        with self._lock:
            if self.is_connected:
                return

            port = self._resolve_port()
            try:
                connection = serial.Serial(
                    port=port,
                    baudrate=self.baudrate,
                    timeout=0.2,
                    write_timeout=self.write_timeout,
                    rtscts=False,
                    dsrdtr=False,
                )
                connection.dtr = False
                connection.rts = False
                time.sleep(self.reset_wait)
                connection.reset_input_buffer()
            except (SerialException, OSError) as exc:
                raise FaceConnectionError(
                    f"Could not open ESP32 serial port {port}: {exc}"
                ) from exc

            self._serial = connection
            self._resolved_port = port
            self._last_face = None

    def close(self) -> None:
        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                finally:
                    self._serial = None
                    self._last_face = None

    def _write_face(self, face: Face) -> None:
        if not self.is_connected:
            self.connect()

        assert self._serial is not None
        payload = f"{face.value}\n".encode("ascii")
        self._serial.write(payload)
        self._serial.flush()

    def set_face(
        self,
        face: Union[Face, str],
        *,
        force: bool = False,
        reconnect_once: bool = True,
    ) -> Face:
        """Display one face and return the normalized Face value."""

        normalized = Face.parse(face)

        with self._lock:
            if not force and normalized == self._last_face:
                return normalized

            try:
                self._write_face(normalized)
            except (SerialException, OSError, FaceConnectionError):
                if not reconnect_once:
                    raise

                self.close()
                self.connect()
                self._write_face(normalized)

            self._last_face = normalized
            return normalized

    def demo(
        self,
        *,
        delay: float = 1.5,
        repeat: int = 1,
        sequence: Iterable[Union[Face, str]] = DEMO_SEQUENCE,
    ) -> None:
        if delay < 0:
            raise ValueError("delay must be 0 or greater")
        if repeat < 1:
            raise ValueError("repeat must be at least 1")

        normalized_sequence = tuple(Face.parse(face) for face in sequence)

        for _ in range(repeat):
            for face in normalized_sequence:
                self.set_face(face, force=True)
                print(f"FACE -> {face.value}")
                time.sleep(delay)

    def __enter__(self) -> "FaceController":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.close()


def _run_interactive(controller: FaceController) -> None:
    print("Interactive mode")
    print("Enter: NEUTRAL, SMILE, HAPPY, QUESTION, ERROR, DEMO, or QUIT")

    while True:
        try:
            command = input("face> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return

        if not command:
            continue

        upper = command.upper()
        if upper in {"QUIT", "EXIT", "Q"}:
            return

        try:
            if upper == "DEMO":
                controller.demo()
            else:
                face = controller.set_face(upper, force=True)
                print(f"FACE -> {face.value}")
        except (ValueError, FaceConnectionError, SerialException) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Send LCD face commands from Jetson to the Pumpkin ESP32 "
            "over USB Serial."
        )
    )
    parser.add_argument(
        "--port",
        default=os.getenv("PUMPKIN_ESP32_PORT", "auto"),
        help=(
            "Serial device such as /dev/ttyUSB0. "
            "Default: auto-detect or PUMPKIN_ESP32_PORT."
        ),
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=DEFAULT_BAUDRATE,
        help=f"Serial baud rate. Default: {DEFAULT_BAUDRATE}.",
    )
    parser.add_argument(
        "--reset-wait",
        type=float,
        default=DEFAULT_RESET_WAIT,
        help=(
            "Seconds to wait after opening the port because ESP32 may reset. "
            f"Default: {DEFAULT_RESET_WAIT}."
        ),
    )

    action = parser.add_mutually_exclusive_group()
    action.add_argument(
        "--face",
        choices=[face.value for face in Face],
        type=str.upper,
        help="Display one face.",
    )
    action.add_argument(
        "--demo",
        action="store_true",
        help="Play all five faces and return to NEUTRAL.",
    )
    action.add_argument(
        "--interactive",
        action="store_true",
        help="Keep the serial connection open and accept typed commands.",
    )
    action.add_argument(
        "--list-ports",
        action="store_true",
        help="List visible serial ports without opening one.",
    )

    parser.add_argument(
        "--delay",
        type=float,
        default=1.5,
        help="Seconds between faces in demo mode. Default: 1.5.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Number of demo repetitions. Default: 1.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    if args.list_ports:
        ports = describe_ports()
        if not ports:
            print("No serial ports found.")
            return 1

        print("\n".join(ports))
        return 0

    try:
        with FaceController(
            port=args.port,
            baudrate=args.baudrate,
            reset_wait=args.reset_wait,
        ) as controller:
            print(f"Connected to ESP32 on {controller.port}")

            if args.face:
                face = controller.set_face(args.face, force=True)
                print(f"FACE -> {face.value}")
            elif args.demo:
                controller.demo(delay=args.delay, repeat=args.repeat)
            else:
                _run_interactive(controller)

    except (FaceConnectionError, SerialException, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
