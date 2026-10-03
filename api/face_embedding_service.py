from __future__ import annotations

import base64
import binascii
import importlib.util
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from api.customer_store import get_customer, update_customer
from api.face_enrollment_store import FACE_DATA_DIR, REQUIRED_POSES

MODEL_NAME = os.getenv("PUMPKIN_FACE_MODEL", "buffalo_l")
MODEL_ROOT = Path(
    os.getenv(
        "PUMPKIN_FACE_MODEL_ROOT",
        str(Path.home() / ".insightface"),
    )
).expanduser()
DETECTION_THRESHOLD = float(os.getenv("PUMPKIN_FACE_DETECTION_THRESHOLD", "0.55"))
RECOGNITION_THRESHOLD = float(os.getenv("PUMPKIN_FACE_RECOGNITION_THRESHOLD", "0.45"))
MAX_RECOGNITION_IMAGE_BYTES = int(
    os.getenv("PUMPKIN_FACE_MAX_IMAGE_BYTES", str(8 * 1024 * 1024))
)
_DATA_URL_PATTERN = re.compile(
    r"^data:image/(?P<format>jpeg|jpg|png);base64,(?P<data>.+)$",
    re.IGNORECASE,
)

_face_app: Any | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_customer_id(customer_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_.-]", "_", customer_id)


def _customer_dir(customer_id: str) -> Path:
    return FACE_DATA_DIR / _safe_customer_id(customer_id)


def _metadata_path(customer_id: str) -> Path:
    return _customer_dir(customer_id) / "enrollment.json"


def _embedding_path(customer_id: str) -> Path:
    return _customer_dir(customer_id) / "embedding.json"


def dependency_status() -> dict[str, object]:
    modules = {
        "insightface": importlib.util.find_spec("insightface") is not None,
        "cv2": importlib.util.find_spec("cv2") is not None,
        "onnxruntime": importlib.util.find_spec("onnxruntime") is not None,
        "numpy": importlib.util.find_spec("numpy") is not None,
    }
    return {
        "ready": all(modules.values()),
        "modules": modules,
        "model": MODEL_NAME,
        "model_root": str(MODEL_ROOT),
        "recognition_threshold": RECOGNITION_THRESHOLD,
        "message": (
            "얼굴 임베딩 실행 준비가 완료되었습니다."
            if all(modules.values())
            else "필수 얼굴 임베딩 패키지가 일부 설치되지 않았습니다."
        ),
    }


def _load_face_app() -> Any:
    global _face_app
    if _face_app is not None:
        return _face_app

    missing = [
        name
        for name in ("insightface", "cv2", "onnxruntime", "numpy")
        if importlib.util.find_spec(name) is None
    ]
    if missing:
        raise RuntimeError(
            "얼굴 임베딩 패키지가 설치되지 않았습니다: " + ", ".join(missing)
        )

    from insightface.app import FaceAnalysis

    providers_env = os.getenv(
        "PUMPKIN_FACE_PROVIDERS",
        "CUDAExecutionProvider,CPUExecutionProvider",
    )
    providers = [item.strip() for item in providers_env.split(",") if item.strip()]
    app = FaceAnalysis(name=MODEL_NAME, root=str(MODEL_ROOT), providers=providers)
    ctx_id = 0 if "CUDAExecutionProvider" in providers else -1
    app.prepare(ctx_id=ctx_id, det_size=(640, 640))
    _face_app = app
    return app


def _load_enrollment(customer_id: str) -> dict[str, Any]:
    path = _metadata_path(customer_id)
    if not path.exists():
        raise ValueError("얼굴 등록 사진이 없습니다.")
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("얼굴 등록 메타데이터를 읽지 못했습니다.") from error


def _load_embedding_file(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    centroid = payload.get("centroid")
    if not isinstance(centroid, list) or not centroid:
        return None
    return payload


def _normalize(vector: Any, np: Any) -> Any:
    norm = float(np.linalg.norm(vector))
    if norm <= 1e-12:
        raise ValueError("0 벡터 임베딩이 생성되었습니다.")
    return vector / norm


def _extract_single_face_embedding(image: Any, *, context: str) -> tuple[Any, float, list[float]]:
    app = _load_face_app()
    import numpy as np

    faces = app.get(image)
    if len(faces) == 0:
        raise ValueError(f"{context}에서 얼굴을 찾지 못했습니다.")
    if len(faces) > 1:
        raise ValueError(f"{context}에 얼굴이 여러 명 있습니다.")

    face = faces[0]
    detection_score = float(getattr(face, "det_score", 0.0))
    if detection_score < DETECTION_THRESHOLD:
        raise ValueError(
            f"{context}의 얼굴 검출 품질이 낮습니다: {detection_score:.3f}"
        )

    raw_embedding = getattr(face, "normed_embedding", None)
    if raw_embedding is None:
        raw_embedding = getattr(face, "embedding", None)
    if raw_embedding is None:
        raise ValueError(f"{context}의 임베딩을 생성하지 못했습니다.")

    normalized = _normalize(np.asarray(raw_embedding, dtype=np.float32), np)
    bbox = getattr(face, "bbox", None)
    bbox_list = (
        [round(float(value), 2) for value in bbox.tolist()]
        if bbox is not None
        else []
    )
    return normalized, detection_score, bbox_list


def _decode_image_data(image_data: str) -> Any:
    match = _DATA_URL_PATTERN.match(image_data.strip())
    if not match:
        raise ValueError("JPEG 또는 PNG 이미지 데이터가 필요합니다.")
    try:
        raw = base64.b64decode(match.group("data"), validate=True)
    except (binascii.Error, ValueError) as error:
        raise ValueError("이미지 데이터를 해석하지 못했습니다.") from error
    if not raw:
        raise ValueError("빈 이미지입니다.")
    if len(raw) > MAX_RECOGNITION_IMAGE_BYTES:
        raise ValueError(
            f"이미지는 장당 {MAX_RECOGNITION_IMAGE_BYTES // (1024 * 1024)}MB 이하여야 합니다."
        )

    import cv2
    import numpy as np

    encoded = np.frombuffer(raw, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError("JPEG 또는 PNG 이미지를 읽지 못했습니다.")
    return image


def generate_customer_embeddings(customer_id: str) -> dict[str, object]:
    if get_customer(customer_id) is None:
        raise KeyError(customer_id)

    metadata = _load_enrollment(customer_id)
    samples = metadata.get("samples") or {}
    missing = [pose for pose in REQUIRED_POSES if pose not in samples]
    if missing:
        raise ValueError("모든 방향의 얼굴 사진이 필요합니다: " + ", ".join(missing))

    import cv2
    import numpy as np

    pose_embeddings: dict[str, list[float]] = {}
    quality: dict[str, dict[str, object]] = {}

    for pose in REQUIRED_POSES:
        filename = samples[pose].get("filename")
        if not filename:
            raise ValueError(f"{pose} 사진 파일명이 없습니다.")
        image_path = _customer_dir(customer_id) / str(filename)
        image = cv2.imread(str(image_path))
        if image is None:
            raise ValueError(f"{pose} 사진을 읽지 못했습니다: {image_path.name}")

        normalized, detection_score, bbox = _extract_single_face_embedding(
            image,
            context=f"{pose} 사진",
        )
        pose_embeddings[pose] = normalized.astype(float).tolist()
        quality[pose] = {
            "filename": image_path.name,
            "detection_score": round(detection_score, 6),
            "dimension": int(normalized.shape[0]),
            "bbox": bbox,
        }

    matrix = np.asarray(
        [pose_embeddings[pose] for pose in REQUIRED_POSES],
        dtype=np.float32,
    )
    centroid = _normalize(matrix.mean(axis=0), np)
    generated_at = _now_iso()
    payload = {
        "customer_id": customer_id,
        "model": MODEL_NAME,
        "generated_at": generated_at,
        "embedding_dimension": int(centroid.shape[0]),
        "poses": pose_embeddings,
        "centroid": centroid.astype(float).tolist(),
        "quality": quality,
    }

    directory = _customer_dir(customer_id)
    directory.mkdir(parents=True, exist_ok=True)
    _embedding_path(customer_id).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    metadata["embedding_ready"] = True
    metadata["model"] = MODEL_NAME
    metadata["embedding_generated_at"] = generated_at
    metadata["updated_at"] = generated_at
    _metadata_path(customer_id).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    update_customer(customer_id, {"face_registered": True})

    return {
        "customer_id": customer_id,
        "embedding_ready": True,
        "model": MODEL_NAME,
        "embedding_dimension": int(centroid.shape[0]),
        "sample_count": len(pose_embeddings),
        "quality": quality,
        "generated_at": generated_at,
        "embedding_file": str(
            _embedding_path(customer_id).relative_to(FACE_DATA_DIR.parent.parent)
        ),
    }


def recognize_customer(
    image_data: str,
    *,
    threshold: float | None = None,
    top_k: int = 3,
) -> dict[str, object]:
    import numpy as np

    active_threshold = RECOGNITION_THRESHOLD if threshold is None else float(threshold)
    if not 0.0 <= active_threshold <= 1.0:
        raise ValueError("인식 임계값은 0과 1 사이여야 합니다.")

    image = _decode_image_data(image_data)
    probe, detection_score, bbox = _extract_single_face_embedding(
        image,
        context="인식 이미지",
    )

    candidates: list[dict[str, object]] = []
    for embedding_path in sorted(FACE_DATA_DIR.glob("*/embedding.json")):
        payload = _load_embedding_file(embedding_path)
        if payload is None:
            continue
        customer_id = str(payload.get("customer_id") or embedding_path.parent.name)
        customer = get_customer(customer_id)
        if customer is None or not bool(customer.get("face_registered")):
            continue

        centroid = _normalize(
            np.asarray(payload["centroid"], dtype=np.float32),
            np,
        )
        if centroid.shape != probe.shape:
            continue
        similarity = float(np.dot(probe, centroid))

        pose_scores: dict[str, float] = {}
        poses = payload.get("poses") or {}
        if isinstance(poses, dict):
            for pose, vector in poses.items():
                try:
                    pose_vector = _normalize(np.asarray(vector, dtype=np.float32), np)
                    if pose_vector.shape == probe.shape:
                        pose_scores[str(pose)] = float(np.dot(probe, pose_vector))
                except (TypeError, ValueError):
                    continue

        candidates.append(
            {
                "customer_id": customer_id,
                "name": customer.get("name"),
                "similarity": round(similarity, 6),
                "best_pose_similarity": (
                    round(max(pose_scores.values()), 6) if pose_scores else None
                ),
                "model": payload.get("model"),
            }
        )

    candidates.sort(key=lambda item: float(item["similarity"]), reverse=True)
    best = candidates[0] if candidates else None
    matched = bool(best and float(best["similarity"]) >= active_threshold)

    return {
        "matched": matched,
        "customer_id": best.get("customer_id") if matched and best else None,
        "name": best.get("name") if matched and best else None,
        "similarity": best.get("similarity") if best else None,
        "threshold": active_threshold,
        "reason": (
            "matched"
            if matched
            else "below_threshold"
            if best
            else "no_registered_embeddings"
        ),
        "probe": {
            "detection_score": round(detection_score, 6),
            "bbox": bbox,
            "embedding_dimension": int(probe.shape[0]),
        },
        "candidate_count": len(candidates),
        "candidates": candidates[: max(1, min(int(top_k), 10))],
        "recognized_at": _now_iso(),
    }
