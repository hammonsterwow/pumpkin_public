from __future__ import annotations

import base64
import binascii
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from api.customer_store import get_customer, update_customer

ROOT_DIR = Path(__file__).resolve().parents[1]
FACE_DATA_DIR = ROOT_DIR / "data" / "face_enrollment"
REQUIRED_POSES = ("front", "left", "right", "up", "down")
POSE_LABELS = {
    "front": "정면",
    "left": "왼쪽",
    "right": "오른쪽",
    "up": "위쪽",
    "down": "아래쪽",
}
_DATA_URL_PATTERN = re.compile(
    r"^data:image/(?P<format>jpeg|jpg|png);base64,(?P<data>.+)$",
    re.IGNORECASE,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _customer_dir(customer_id: str) -> Path:
    safe_id = re.sub(r"[^a-zA-Z0-9_.-]", "_", customer_id)
    return FACE_DATA_DIR / safe_id


def _metadata_path(customer_id: str) -> Path:
    return _customer_dir(customer_id) / "enrollment.json"


def _empty_metadata(customer_id: str) -> dict[str, Any]:
    return {
        "customer_id": customer_id,
        "session_id": None,
        "status": "not_started",
        "required_poses": list(REQUIRED_POSES),
        "samples": {},
        "embedding_ready": False,
        "model": None,
        "started_at": None,
        "completed_at": None,
        "updated_at": None,
    }


def _load_metadata(customer_id: str) -> dict[str, Any]:
    path = _metadata_path(customer_id)
    if not path.exists():
        return _empty_metadata(customer_id)
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
        metadata = _empty_metadata(customer_id)
        metadata.update(loaded)
        return metadata
    except (OSError, json.JSONDecodeError):
        return _empty_metadata(customer_id)


def _save_metadata(customer_id: str, metadata: dict[str, Any]) -> None:
    directory = _customer_dir(customer_id)
    directory.mkdir(parents=True, exist_ok=True)
    _metadata_path(customer_id).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _validate_session(metadata: dict[str, Any], session_id: str) -> None:
    current_session_id = metadata.get("session_id")
    if not current_session_id:
        raise ValueError("진행 중인 얼굴 등록 세션이 없습니다.")
    if current_session_id != session_id:
        raise ValueError("얼굴 등록 세션이 만료되었거나 일치하지 않습니다.")


def get_enrollment_status(customer_id: str) -> dict[str, Any] | None:
    if get_customer(customer_id) is None:
        return None

    metadata = _load_metadata(customer_id)
    samples = metadata.get("samples") or {}
    completed = [pose for pose in REQUIRED_POSES if pose in samples]
    complete = len(completed) == len(REQUIRED_POSES)

    return {
        "customer_id": customer_id,
        "session_id": metadata.get("session_id"),
        "status": metadata.get("status") or "not_started",
        "required_count": len(REQUIRED_POSES),
        "sample_count": len(completed),
        "complete": complete,
        "embedding_ready": bool(metadata.get("embedding_ready")),
        "model": metadata.get("model"),
        "started_at": metadata.get("started_at"),
        "completed_at": metadata.get("completed_at"),
        "updated_at": metadata.get("updated_at"),
        "next_pose": next((pose for pose in REQUIRED_POSES if pose not in samples), None),
        "poses": [
            {
                "pose": pose,
                "label": POSE_LABELS[pose],
                "registered": pose in samples,
                "captured_at": samples.get(pose, {}).get("captured_at"),
                "sequence": samples.get(pose, {}).get("sequence"),
                "size_bytes": samples.get(pose, {}).get("size_bytes"),
            }
            for pose in REQUIRED_POSES
        ],
    }


def start_face_enrollment_session(
    customer_id: str,
    *,
    reset_existing: bool = True,
) -> dict[str, Any]:
    if get_customer(customer_id) is None:
        raise KeyError(customer_id)

    directory = _customer_dir(customer_id)
    if reset_existing and directory.exists():
        shutil.rmtree(directory)

    now = _now_iso()
    metadata = _empty_metadata(customer_id)
    metadata.update(
        {
            "session_id": uuid4().hex,
            "status": "collecting",
            "started_at": now,
            "updated_at": now,
        }
    )
    _save_metadata(customer_id, metadata)
    update_customer(customer_id, {"face_registered": False})

    status = get_enrollment_status(customer_id)
    return status or {}


def save_face_sample(
    customer_id: str,
    pose: str,
    image_data: str,
    *,
    session_id: str | None = None,
    captured_at: str | None = None,
    sequence: int | None = None,
) -> dict[str, Any]:
    if get_customer(customer_id) is None:
        raise KeyError(customer_id)
    if pose not in REQUIRED_POSES:
        raise ValueError(f"지원하지 않는 촬영 방향입니다: {pose}")

    metadata = _load_metadata(customer_id)
    if session_id is not None:
        _validate_session(metadata, session_id)
    elif not metadata.get("session_id"):
        now = _now_iso()
        metadata.update(
            {
                "session_id": uuid4().hex,
                "status": "collecting",
                "started_at": now,
                "updated_at": now,
            }
        )

    match = _DATA_URL_PATTERN.match(image_data.strip())
    if not match:
        raise ValueError("JPEG 또는 PNG 이미지 데이터가 필요합니다.")

    try:
        raw = base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("이미지 데이터를 해석하지 못했습니다.") from error

    if not raw:
        raise ValueError("빈 이미지입니다.")
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError("이미지는 장당 8MB 이하여야 합니다.")

    extension = "jpg" if match.group("format").lower() in {"jpg", "jpeg"} else "png"
    directory = _customer_dir(customer_id)
    directory.mkdir(parents=True, exist_ok=True)
    for old_extension in ("jpg", "png"):
        old_path = directory / f"{pose}.{old_extension}"
        if old_path.exists():
            old_path.unlink()

    filename = f"{pose}.{extension}"
    (directory / filename).write_bytes(raw)

    samples = metadata.setdefault("samples", {})
    saved_at = captured_at or _now_iso()
    samples[pose] = {
        "filename": filename,
        "captured_at": saved_at,
        "sequence": sequence,
        "size_bytes": len(raw),
    }
    metadata["embedding_ready"] = False
    metadata["model"] = None
    metadata["completed_at"] = None
    metadata["status"] = "samples_complete" if all(
        required_pose in samples for required_pose in REQUIRED_POSES
    ) else "collecting"
    metadata["updated_at"] = _now_iso()
    _save_metadata(customer_id, metadata)

    update_customer(customer_id, {"face_registered": False})
    status = get_enrollment_status(customer_id)
    return status or {}


def finalize_face_enrollment(customer_id: str, session_id: str) -> dict[str, Any]:
    if get_customer(customer_id) is None:
        raise KeyError(customer_id)

    metadata = _load_metadata(customer_id)
    _validate_session(metadata, session_id)
    samples = metadata.get("samples") or {}
    missing_poses = [pose for pose in REQUIRED_POSES if pose not in samples]
    if missing_poses:
        labels = ", ".join(POSE_LABELS[pose] for pose in missing_poses)
        raise ValueError(f"아직 촬영하지 않은 방향이 있습니다: {labels}")

    now = _now_iso()
    metadata["status"] = "samples_complete"
    metadata["completed_at"] = now
    metadata["updated_at"] = now
    metadata["embedding_ready"] = False
    metadata["model"] = None
    _save_metadata(customer_id, metadata)

    # 현재 단계에서는 사진 수집 완료 상태만 저장한다.
    # 실제 얼굴 임베딩 생성이 연결되면 그때 face_registered를 True로 변경한다.
    update_customer(customer_id, {"face_registered": False})

    status = get_enrollment_status(customer_id) or {}
    status["message"] = "얼굴 사진 수집이 완료되었습니다. 임베딩 생성은 아직 연결되지 않았습니다."
    return status


def reset_face_enrollment(customer_id: str) -> bool:
    if get_customer(customer_id) is None:
        return False
    directory = _customer_dir(customer_id)
    if directory.exists():
        shutil.rmtree(directory)
    update_customer(customer_id, {"face_registered": False})
    return True
