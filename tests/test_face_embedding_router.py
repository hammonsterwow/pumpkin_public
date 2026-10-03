from __future__ import annotations

import pytest
from fastapi import HTTPException

from api.routers import face_embeddings


def test_face_generate_embedding_returns_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = {
        "customer_id": "customer_001",
        "embedding_ready": True,
    }

    monkeypatch.setattr(
        face_embeddings,
        "generate_customer_embeddings",
        lambda customer_id: {
            **expected,
            "requested_customer_id": customer_id,
        },
    )

    payload = face_embeddings.GenerateEmbeddingRequest(
        customer_id="customer_001",
    )

    result = face_embeddings.face_generate_embedding(payload)

    assert result == {
        **expected,
        "requested_customer_id": "customer_001",
    }


def test_face_generate_embedding_maps_unknown_customer_to_404(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_unknown_customer(customer_id: str) -> dict[str, object]:
        raise KeyError(customer_id)

    monkeypatch.setattr(
        face_embeddings,
        "generate_customer_embeddings",
        raise_unknown_customer,
    )

    payload = face_embeddings.GenerateEmbeddingRequest(
        customer_id="missing_customer",
    )

    with pytest.raises(HTTPException) as error:
        face_embeddings.face_generate_embedding(payload)

    assert error.value.status_code == 404
    assert error.value.detail == "고객을 찾을 수 없습니다."


def test_face_generate_embedding_maps_validation_error_to_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_validation_error(customer_id: str) -> dict[str, object]:
        raise ValueError("필수 얼굴 사진이 누락되었습니다.")

    monkeypatch.setattr(
        face_embeddings,
        "generate_customer_embeddings",
        raise_validation_error,
    )

    payload = face_embeddings.GenerateEmbeddingRequest(
        customer_id="customer_001",
    )

    with pytest.raises(HTTPException) as error:
        face_embeddings.face_generate_embedding(payload)

    assert error.value.status_code == 400
    assert error.value.detail == "필수 얼굴 사진이 누락되었습니다."


def test_face_generate_embedding_maps_dependency_error_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_dependency_error(customer_id: str) -> dict[str, object]:
        raise RuntimeError("InsightFace를 사용할 수 없습니다.")

    monkeypatch.setattr(
        face_embeddings,
        "generate_customer_embeddings",
        raise_dependency_error,
    )

    payload = face_embeddings.GenerateEmbeddingRequest(
        customer_id="customer_001",
    )

    with pytest.raises(HTTPException) as error:
        face_embeddings.face_generate_embedding(payload)

    assert error.value.status_code == 503
    assert error.value.detail == "InsightFace를 사용할 수 없습니다."


def test_face_recognize_returns_result_and_forwards_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}
    expected = {
        "matched": True,
        "customer_id": "customer_001",
        "score": 0.92,
    }

    def recognize(
        image_data: str,
        *,
        threshold: float | None,
        top_k: int,
    ) -> dict[str, object]:
        captured.update(
            image_data=image_data,
            threshold=threshold,
            top_k=top_k,
        )
        return expected

    monkeypatch.setattr(face_embeddings, "recognize_customer", recognize)

    payload = face_embeddings.RecognizeFaceRequest(
        image_data="data:image/jpeg;base64," + "a" * 32,
        threshold=0.75,
        top_k=5,
    )

    result = face_embeddings.face_recognize(payload)

    assert result == expected
    assert captured == {
        "image_data": payload.image_data,
        "threshold": 0.75,
        "top_k": 5,
    }


def test_face_recognize_maps_validation_error_to_400(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_validation_error(
        image_data: str,
        *,
        threshold: float | None,
        top_k: int,
    ) -> dict[str, object]:
        raise ValueError("유효한 이미지 데이터가 아닙니다.")

    monkeypatch.setattr(
        face_embeddings,
        "recognize_customer",
        raise_validation_error,
    )

    payload = face_embeddings.RecognizeFaceRequest(
        image_data="data:image/jpeg;base64," + "a" * 32,
    )

    with pytest.raises(HTTPException) as error:
        face_embeddings.face_recognize(payload)

    assert error.value.status_code == 400
    assert error.value.detail == "유효한 이미지 데이터가 아닙니다."


def test_face_recognize_maps_dependency_error_to_503(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_dependency_error(
        image_data: str,
        *,
        threshold: float | None,
        top_k: int,
    ) -> dict[str, object]:
        raise RuntimeError("얼굴 인식 모델을 사용할 수 없습니다.")

    monkeypatch.setattr(
        face_embeddings,
        "recognize_customer",
        raise_dependency_error,
    )

    payload = face_embeddings.RecognizeFaceRequest(
        image_data="data:image/jpeg;base64," + "a" * 32,
    )

    with pytest.raises(HTTPException) as error:
        face_embeddings.face_recognize(payload)

    assert error.value.status_code == 503
    assert error.value.detail == "얼굴 인식 모델을 사용할 수 없습니다."
