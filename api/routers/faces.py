from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.face_embedding_service import dependency_status, generate_customer_embeddings

router = APIRouter(prefix="/api/faces", tags=["faces"])


class FaceEmbeddingRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)


@router.get("/embedding-status")
def face_embedding_status() -> dict[str, object]:
    return dependency_status()


@router.post("/generate-embedding")
def face_generate_embedding(payload: FaceEmbeddingRequest) -> dict[str, object]:
    try:
        return generate_customer_embeddings(payload.customer_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
