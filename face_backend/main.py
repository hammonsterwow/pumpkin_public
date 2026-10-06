from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from typing import Annotated

import cv2
import firebase_admin
import numpy as np
from fastapi import FastAPI, Header, HTTPException
from firebase_admin import auth, firestore, storage
from pydantic import BaseModel, Field

POSES = ("front", "left", "right", "up", "down")
MODEL_NAME = os.getenv("PUMPKIN_FACE_MODEL", "buffalo_l")
MODEL_ROOT = os.getenv("PUMPKIN_FACE_MODEL_ROOT", "/opt/insightface")
MIN_DETECTION_SCORE = float(os.getenv("PUMPKIN_FACE_MIN_DETECTION_SCORE", "0.55"))
MAX_IMAGE_BYTES = int(os.getenv("PUMPKIN_FACE_MAX_IMAGE_BYTES", str(5 * 1024 * 1024)))
STORAGE_BUCKET = os.getenv("FIREBASE_STORAGE_BUCKET", "").strip()

if not firebase_admin._apps:
    options = {"storageBucket": STORAGE_BUCKET} if STORAGE_BUCKET else None
    firebase_admin.initialize_app(options=options)

app = FastAPI(title="Pumpkin Face Embedding Backend", version="1.0.0")
_face_app = None
_face_app_lock = threading.Lock()


class GenerateRequest(BaseModel):
    uid: str = Field(min_length=1, max_length=128)


class GenerateResponse(BaseModel):
    uid: str
    embedding_ready: bool
    model: str
    embedding_dimension: int
    generated_at: str
    temporary_frames_deleted: bool
    quality: dict[str, dict[str, object]]


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Firebase 로그인 토큰이 필요합니다.")
    scheme, separator, token = authorization.partition(" ")
    if separator != " " or scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="올바른 Bearer 토큰이 필요합니다.")
    return token.strip()


def _authenticated_uid(authorization: str | None) -> str:
    try:
        decoded = auth.verify_id_token(_bearer_token(authorization))
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            status_code=401,
            detail="Firebase 로그인 토큰이 만료되었거나 유효하지 않습니다.",
        ) from error
    uid = str(decoded.get("uid") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="로그인 사용자 UID를 확인하지 못했습니다.")
    return uid


def _model():
    global _face_app
    if _face_app is not None:
        return _face_app
    with _face_app_lock:
        if _face_app is None:
            try:
                from insightface.app import FaceAnalysis

                instance = FaceAnalysis(
                    name=MODEL_NAME,
                    root=MODEL_ROOT,
                    providers=["CPUExecutionProvider"],
                )
                instance.prepare(ctx_id=-1, det_size=(640, 640))
                _face_app = instance
            except Exception as error:
                raise HTTPException(
                    status_code=503,
                    detail=f"얼굴 임베딩 모델을 시작하지 못했습니다: {error}",
                ) from error
    return _face_app


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise HTTPException(status_code=422, detail="유효한 얼굴 임베딩을 만들지 못했습니다.")
    return vector / norm


def _download_pose(uid: str, pose: str) -> np.ndarray:
    if not STORAGE_BUCKET:
        raise HTTPException(
            status_code=503,
            detail="FIREBASE_STORAGE_BUCKET 환경 변수가 설정되지 않았습니다.",
        )

    object_name = f"face-enrollment-temp/{uid}/{pose}.jpg"
    blob = storage.bucket().blob(object_name)
    try:
        blob.reload()
    except Exception as error:
        raise HTTPException(
            status_code=400,
            detail=f"{pose} 얼굴 사진을 Firebase Storage에서 찾지 못했습니다.",
        ) from error

    if blob.size is not None and int(blob.size) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"{pose} 사진이 허용된 크기 제한을 초과했습니다.")
    if blob.content_type and blob.content_type != "image/jpeg":
        raise HTTPException(status_code=415, detail=f"{pose} 사진은 JPEG 형식이어야 합니다.")

    try:
        raw = blob.download_as_bytes()
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"{pose} 사진 다운로드에 실패했습니다.") from error
    if not raw or len(raw) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=f"{pose} 사진 크기가 올바르지 않습니다.")

    image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=422, detail=f"{pose} 사진을 JPEG 이미지로 읽지 못했습니다.")
    return image


def _embedding_for_pose(image: np.ndarray, pose: str) -> tuple[np.ndarray, dict[str, object]]:
    try:
        faces = _model().get(image)
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(status_code=503, detail=f"{pose} 사진 분석에 실패했습니다.") from error

    if len(faces) != 1:
        raise HTTPException(
            status_code=422,
            detail=f"{pose} 사진에는 얼굴이 정확히 1개 있어야 합니다. 감지된 얼굴: {len(faces)}개",
        )

    face = faces[0]
    score = float(getattr(face, "det_score", 0.0))
    if score < MIN_DETECTION_SCORE:
        raise HTTPException(
            status_code=422,
            detail=f"{pose} 사진의 얼굴 인식 품질이 낮습니다. 다시 촬영해주세요.",
        )

    vector = getattr(face, "normed_embedding", None)
    if vector is None:
        vector = _normalize(np.asarray(face.embedding, dtype=np.float32))
    vector = _normalize(np.asarray(vector, dtype=np.float32))
    bbox = [round(float(value), 2) for value in np.asarray(face.bbox).tolist()]
    return vector, {
        "detection_score": round(score, 6),
        "bbox": bbox,
        "dimension": int(vector.shape[0]),
    }


def _save_result(
    uid: str,
    centroid: np.ndarray,
    quality: dict[str, dict[str, object]],
) -> None:
    client = firestore.client()
    user_ref = client.collection("users").document(uid)
    batch = client.batch()
    batch.set(
        user_ref,
        {
            "faceRegistered": True,
            "faceEnrollmentStatus": "registered",
            "faceEmbedding": {
                "model": MODEL_NAME,
                "dimension": int(centroid.shape[0]),
                "centroid": centroid.astype(float).tolist(),
                "quality": quality,
                "updatedAt": firestore.SERVER_TIMESTAMP,
            },
            "updatedAt": firestore.SERVER_TIMESTAMP,
        },
        merge=True,
    )
    for pose in POSES:
        batch.delete(user_ref.collection("faceEnrollment").document(pose))
    batch.commit()


def _delete_temporary_frames(uid: str) -> bool:
    deleted_all = True
    bucket = storage.bucket()
    for pose in POSES:
        try:
            bucket.blob(f"face-enrollment-temp/{uid}/{pose}.jpg").delete()
        except Exception:
            deleted_all = False
    return deleted_all


@app.get("/")
def root() -> dict[str, str]:
    return {"service": "pumpkin-face-backend", "status": "ok"}


@app.get("/health")
def health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "storage_bucket_configured": bool(STORAGE_BUCKET),
    }


@app.post(
    "/api/face-enrollment/{uid}/generate",
    response_model=GenerateResponse,
)
def generate_embedding(
    uid: str,
    payload: GenerateRequest,
    authorization: Annotated[str | None, Header()] = None,
) -> GenerateResponse:
    authenticated_uid = _authenticated_uid(authorization)
    if authenticated_uid != uid or payload.uid != uid:
        raise HTTPException(status_code=403, detail="본인의 얼굴 등록만 최종화할 수 있습니다.")

    pose_vectors: list[np.ndarray] = []
    quality: dict[str, dict[str, object]] = {}
    for pose in POSES:
        vector, pose_quality = _embedding_for_pose(_download_pose(uid, pose), pose)
        pose_vectors.append(vector)
        quality[pose] = pose_quality

    centroid = _normalize(np.mean(np.stack(pose_vectors), axis=0))
    generated_at = datetime.now(timezone.utc).isoformat()
    try:
        _save_result(uid, centroid, quality)
    except Exception as error:
        raise HTTPException(status_code=502, detail="얼굴 임베딩을 Firestore에 저장하지 못했습니다.") from error

    deleted = _delete_temporary_frames(uid)
    return GenerateResponse(
        uid=uid,
        embedding_ready=True,
        model=MODEL_NAME,
        embedding_dimension=int(centroid.shape[0]),
        generated_at=generated_at,
        temporary_frames_deleted=deleted,
        quality=quality,
    )
