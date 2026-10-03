from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from api import firebase_face_backend as backend


def test_bearer_token_requires_authorization() -> None:
    with pytest.raises(HTTPException) as error:
        backend._bearer_token(None)

    assert error.value.status_code == 401


def test_bearer_token_rejects_wrong_scheme() -> None:
    with pytest.raises(HTTPException) as error:
        backend._bearer_token("Basic abc")

    assert error.value.status_code == 401


def test_bearer_token_returns_token() -> None:
    assert backend._bearer_token("Bearer firebase-token") == "firebase-token"


def test_verify_uid_accepts_matching_firebase_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = SimpleNamespace(
        verify_id_token=lambda token, check_revoked: {"uid": "user-1"}
    )
    firestore_client = object()
    bucket = object()
    monkeypatch.setattr(
        backend,
        "_firebase_services",
        lambda: (auth, firestore_client, bucket),
    )

    assert backend._verify_uid(
        "user-1",
        "Bearer firebase-token",
    ) == (firestore_client, bucket)


def test_verify_uid_rejects_different_firebase_user(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auth = SimpleNamespace(
        verify_id_token=lambda token, check_revoked: {"uid": "user-2"}
    )
    monkeypatch.setattr(
        backend,
        "_firebase_services",
        lambda: (auth, object(), object()),
    )

    with pytest.raises(HTTPException) as error:
        backend._verify_uid("user-1", "Bearer firebase-token")

    assert error.value.status_code == 403


def test_verify_uid_rejects_invalid_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_token(token: str, check_revoked: bool) -> None:
        raise ValueError("invalid")

    auth = SimpleNamespace(verify_id_token=reject_token)
    monkeypatch.setattr(
        backend,
        "_firebase_services",
        lambda: (auth, object(), object()),
    )

    with pytest.raises(HTTPException) as error:
        backend._verify_uid("user-1", "Bearer invalid")

    assert error.value.status_code == 401
