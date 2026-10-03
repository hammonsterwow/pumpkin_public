from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from api.face_embedding_service import MODEL_NAME, _extract_single_face_embedding, _normalize

router = APIRouter(tags=["firebase-face-enrollment"])
REQUIRED_POSES = ("front", "left", "right", "up", "down")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _firebase_storage_bucket() -> str:
    value = os.getenv("PUMPKIN_FIREBASE_STORAGE_BUCKET")
    if not value:
        raise RuntimeError("PUMPKIN_FIREBASE_STORAGE_BUCKET가 설정되지 않았습니다.")
    return value


def _firebase_services() -> tuple[Any, Any, Any]:
    import firebase_admin
    from firebase_admin import auth, firestore, storage

    if not firebase_admin._apps:
        firebase_admin.initialize_app(
            options={"storageBucket": _firebase_storage_bucket()}
        )
    return auth, firestore.client(), storage.bucket(_firebase_storage_bucket())


def _bearer_token(authorization: str | None) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Firebase 인증 토큰이 필요합니다.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(status_code=401, detail="Bearer 인증 토큰 형식이 올바르지 않습니다.")
    return token.strip()


def _verify_uid(uid: str, authorization: str | None) -> tuple[Any, Any]:
    token = _bearer_token(authorization)
    auth, firestore_client, bucket = _firebase_services()
    try:
        decoded = auth.verify_id_token(token, check_revoked=True)
    except Exception as error:
        raise HTTPException(status_code=401, detail="Firebase 인증 토큰이 유효하지 않습니다.") from error
    if decoded.get("uid") != uid:
        raise HTTPException(status_code=403, detail="다른 사용자의 얼굴 등록은 처리할 수 없습니다.")
    return firestore_client, bucket


class GenerateRequest(BaseModel):
    uid: str = Field(min_length=1, max_length=128)


@router.get("/api/face-enrollment/health")
def firebase_face_enrollment_health() -> dict[str, object]:
    return {
        "status": "ok",
        "model": MODEL_NAME,
        "storage_bucket_configured": bool(os.getenv("PUMPKIN_FIREBASE_STORAGE_BUCKET")),
    }


@router.post("/api/face-enrollment/{uid}/generate")
def generate_firebase_face_embedding(
    uid: str,
    payload: GenerateRequest,
    authorization: str | None = Header(default=None),
) -> dict[str, object]:
    if payload.uid != uid:
        raise HTTPException(status_code=400, detail="uid가 일치하지 않습니다.")

    firestore_client, bucket = _verify_uid(uid, authorization)

    try:
        import cv2
        import numpy as np

        pose_embeddings: dict[str, list[float]] = {}
        quality: dict[str, dict[str, object]] = {}
        blobs: list[Any] = []

        for pose in REQUIRED_POSES:
            object_name = f"face-enrollment-temp/{uid}/{pose}.jpg"
            blob = bucket.blob(object_name)
            try:
                raw = blob.download_as_bytes(timeout=30)
            except Exception as error:
                raise ValueError(f"{pose} 사진을 Firebase Storage에서 읽지 못했습니다.") from error
            image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError(f"{pose} 사진을 읽지 못했습니다.")

            normalized, detection_score, bbox = _extract_single_face_embedding(
                image,
                context=f"{pose} 사진",
            )
            pose_embeddings[pose] = normalized.astype(float).tolist()
            quality[pose] = {
                "detection_score": round(detection_score, 6),
                "dimension": int(normalized.shape[0]),
                "bbox": bbox,
            }
            blobs.append(blob)

        matrix = np.asarray(
            [pose_embeddings[pose] for pose in REQUIRED_POSES],
            dtype=np.float32,
        )
        centroid = _normalize(matrix.mean(axis=0), np)
        generated_at = _now_iso()
        centroid_list = centroid.astype(float).tolist()

        firestore_client.collection("users").document(uid).set(
            {
                "faceRegistered": True,
                "faceEnrollmentStatus": "registered",
                "faceEmbedding": {
                    "model": MODEL_NAME,
                    "dimension": int(centroid.shape[0]),
                    "centroid": centroid_list,
                    "updatedAt": generated_at,
                },
                "updatedAt": generated_at,
            },
            merge=True,
        )

        cleanup_errors: list[str] = []
        for blob in blobs:
            try:
                blob.delete()
            except Exception:
                cleanup_errors.append(blob.name)

        return {
            "uid": uid,
            "embedding_ready": True,
            "model": MODEL_NAME,
            "embedding_dimension": int(centroid.shape[0]),
            "centroid": centroid_list,
            "quality": quality,
            "generated_at": generated_at,
            "temporary_frames_deleted": not cleanup_errors,
            "cleanup_errors": cleanup_errors,
        }
    except HTTPException:
        raise
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=500, detail=str(error)) from error
