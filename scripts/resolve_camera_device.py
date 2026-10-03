#!/usr/bin/env python3
"""Resolve a working V4L2 camera index before the ROS vision node starts.

Selection order when no explicit override is supplied:
1. Stable /dev/v4l/by-id/*-video-index0 links.
2. Other /dev/v4l/by-id links.
3. Remaining /dev/videoN devices.

A candidate is accepted only after OpenCV opens it and returns a real frame.
Only the selected numeric index is written to stdout so shell callers can use
command substitution safely; diagnostics go to stderr.
"""

from __future__ import annotations

import glob
import os
import re
import sys
import time
from dataclasses import dataclass

import cv2


_VIDEO_DEVICE_RE = re.compile(r"(?:^|/)video(\d+)$")


@dataclass(frozen=True)
class CameraCandidate:
    index: int
    source: str


def _index_from_device(value: str) -> int:
    value = str(value or "").strip()
    if not value:
        raise ValueError("empty camera device")
    if value.isdigit():
        return int(value)

    resolved = os.path.realpath(value)
    match = _VIDEO_DEVICE_RE.search(resolved)
    if match is None:
        raise ValueError(
            f"camera device does not resolve to /dev/videoN: {value} -> {resolved}"
        )
    return int(match.group(1))


def _append_candidate(candidates: list[CameraCandidate], index: int, source: str) -> None:
    if index < 0 or any(candidate.index == index for candidate in candidates):
        return
    candidates.append(CameraCandidate(index=index, source=source))


def build_candidates() -> tuple[list[CameraCandidate], bool]:
    """Return camera candidates and whether the list is an explicit override."""

    explicit_device = str(os.getenv("PUMPKIN_CAMERA_DEVICE", "")).strip()
    if explicit_device:
        return [
            CameraCandidate(
                index=_index_from_device(explicit_device),
                source=f"PUMPKIN_CAMERA_DEVICE={explicit_device}",
            )
        ], True

    explicit_index = str(os.getenv("PUMPKIN_CAMERA_INDEX", "")).strip()
    if explicit_index:
        try:
            index = int(explicit_index)
        except ValueError as exc:
            raise ValueError(
                f"PUMPKIN_CAMERA_INDEX must be an integer: {explicit_index!r}"
            ) from exc
        return [
            CameraCandidate(
                index=index,
                source=f"PUMPKIN_CAMERA_INDEX={explicit_index}",
            )
        ], True

    candidates: list[CameraCandidate] = []
    preferred_by_id = sorted(glob.glob("/dev/v4l/by-id/*-video-index0"))
    all_by_id = sorted(glob.glob("/dev/v4l/by-id/*"))

    for path in preferred_by_id:
        try:
            _append_candidate(candidates, _index_from_device(path), path)
        except ValueError:
            continue

    for path in all_by_id:
        if path in preferred_by_id:
            continue
        try:
            _append_candidate(candidates, _index_from_device(path), path)
        except ValueError:
            continue

    def video_sort_key(path: str) -> tuple[int, str]:
        try:
            return (_index_from_device(path), path)
        except ValueError:
            return (10_000, path)

    for path in sorted(glob.glob("/dev/video*"), key=video_sort_key):
        try:
            _append_candidate(candidates, _index_from_device(path), path)
        except ValueError:
            continue

    return candidates, False


def probe_camera(candidate: CameraCandidate, *, attempts: int, delay: float) -> bool:
    """Accept a candidate only after a non-empty frame is actually captured."""

    print(
        f"[CAMERA] probing index={candidate.index} source={candidate.source}",
        file=sys.stderr,
        flush=True,
    )
    capture = cv2.VideoCapture(candidate.index)
    try:
        if not capture.isOpened():
            print(
                f"[CAMERA] open failed: index={candidate.index}",
                file=sys.stderr,
                flush=True,
            )
            return False

        for _ in range(attempts):
            ok, frame = capture.read()
            if ok and frame is not None and getattr(frame, "size", 0) > 0:
                height, width = frame.shape[:2]
                print(
                    "[CAMERA] selected "
                    f"index={candidate.index} source={candidate.source} "
                    f"frame={width}x{height}",
                    file=sys.stderr,
                    flush=True,
                )
                return True
            time.sleep(delay)

        print(
            f"[CAMERA] opened but no usable frame: index={candidate.index}",
            file=sys.stderr,
            flush=True,
        )
        return False
    finally:
        capture.release()


def main() -> int:
    try:
        candidates, explicit = build_candidates()
    except ValueError as exc:
        print(f"[CAMERA][FAIL] {exc}", file=sys.stderr)
        return 2

    if not candidates:
        print(
            "[CAMERA][FAIL] no V4L2 camera candidates found under /dev/v4l/by-id or /dev/video*",
            file=sys.stderr,
        )
        return 2

    try:
        attempts = max(1, int(os.getenv("PUMPKIN_CAMERA_PROBE_ATTEMPTS", "8")))
    except ValueError:
        attempts = 8
    try:
        delay = max(0.0, float(os.getenv("PUMPKIN_CAMERA_PROBE_DELAY", "0.08")))
    except ValueError:
        delay = 0.08

    for candidate in candidates:
        if probe_camera(candidate, attempts=attempts, delay=delay):
            print(candidate.index)
            return 0

    mode = "explicit camera override" if explicit else "auto-discovered camera candidates"
    checked = ", ".join(str(candidate.index) for candidate in candidates)
    print(
        f"[CAMERA][FAIL] {mode} produced no readable camera frame; checked indexes: {checked}",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
