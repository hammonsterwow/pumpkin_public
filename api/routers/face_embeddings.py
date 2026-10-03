from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.face_embedding_service import (
    dependency_status,
    generate_customer_embeddings,
    recognize_customer,
)

router = APIRouter(prefix="/api/faces", tags=["face-embeddings"])


class GenerateEmbeddingRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)


class RecognizeFaceRequest(BaseModel):
    image_data: str = Field(min_length=32)
    threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    top_k: int = Field(default=3, ge=1, le=10)


@router.get("/embedding-status")
def face_embedding_status() -> dict[str, object]:
    return dependency_status()


@router.post("/generate-embedding")
def face_generate_embedding(payload: GenerateEmbeddingRequest) -> dict[str, object]:
    try:
        return generate_customer_embeddings(payload.customer_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.post("/recognize")
def face_recognize(payload: RecognizeFaceRequest) -> dict[str, object]:
    """Compare one camera image with every registered customer embedding."""
    try:
        return recognize_customer(
            payload.image_data,
            threshold=payload.threshold,
            top_k=payload.top_k,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
