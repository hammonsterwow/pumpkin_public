from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# 프로젝트 최상위 폴더를 Python import 경로에 추가
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

np = pytest.importorskip("numpy")

from api import face_embedding_service as service


def test_normalize_returns_unit_vector() -> None:
    """벡터가 길이 1인 단위 벡터로 정규화되는지 확인한다."""
    vector = np.array([3.0, 4.0], dtype=np.float32)

    result = service._normalize(vector, np)

    assert np.allclose(result, np.array([0.6, 0.8], dtype=np.float32))
    assert np.isclose(np.linalg.norm(result), 1.0)


def test_normalize_rejects_zero_vector() -> None:
    """크기가 0인 벡터는 정규화할 수 없어야 한다."""
    vector = np.array([0.0, 0.0], dtype=np.float32)

    with pytest.raises(Exception):
        service._normalize(vector, np)


def test_safe_customer_id_accepts_normal_id() -> None:
    """일반적인 고객 ID가 그대로 반환되는지 확인한다."""
    customer_id = "customer_001"

    result = service._safe_customer_id(customer_id)

    assert result == customer_id


@pytest.mark.parametrize(
    ("customer_id", "expected"),
    [
        ("", ""),
        ("../customer", ".._customer"),
        ("customer/001", "customer_001"),
        ("customer\\001", "customer_001"),
        ("customer 001", "customer_001"),
        ("customer@001", "customer_001"),
    ],
)
def test_safe_customer_id_replaces_unsafe_characters(
    customer_id: str,
    expected: str,
) -> None:
    """허용되지 않은 문자가 밑줄로 치환되는지 확인한다."""
    result = service._safe_customer_id(customer_id)

    assert result == expected


def test_extract_single_face_embedding(monkeypatch: pytest.MonkeyPatch) -> None:
    """얼굴 한 개가 탐지되면 임베딩·점수·bbox를 반환하는지 확인한다."""
    fake_face = SimpleNamespace(
        embedding=np.array([3.0, 4.0], dtype=np.float32),
        det_score=0.95,
        bbox=np.array([10.0, 20.0, 110.0, 220.0], dtype=np.float32),
    )

    fake_app = SimpleNamespace(get=lambda image: [fake_face])
    monkeypatch.setattr(service, "_load_face_app", lambda: fake_app)

    fake_image = np.zeros((240, 320, 3), dtype=np.uint8)

    embedding, detection_score, bbox = (
        service._extract_single_face_embedding(
            fake_image,
            context="unit-test",
        )
    )

    assert np.allclose(
        embedding,
        np.array([0.6, 0.8], dtype=np.float32),
    )
    assert np.isclose(np.linalg.norm(embedding), 1.0)
    assert detection_score == pytest.approx(0.95)
    assert bbox == pytest.approx([10.0, 20.0, 110.0, 220.0])


def test_extract_single_face_embedding_rejects_no_face(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """얼굴이 탐지되지 않으면 예외가 발생하는지 확인한다."""
    fake_app = SimpleNamespace(get=lambda image: [])
    monkeypatch.setattr(service, "_load_face_app", lambda: fake_app)

    fake_image = np.zeros((240, 320, 3), dtype=np.uint8)

    with pytest.raises(Exception):
        service._extract_single_face_embedding(
            fake_image,
            context="unit-test",
        )


def test_extract_single_face_embedding_rejects_multiple_faces(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """얼굴이 여러 개 탐지되면 예외가 발생하는지 확인한다."""
    fake_face = SimpleNamespace(
        embedding=np.array([1.0, 0.0], dtype=np.float32),
        det_score=0.9,
        bbox=np.array([0.0, 0.0, 10.0, 10.0], dtype=np.float32),
    )

    fake_app = SimpleNamespace(get=lambda image: [fake_face, fake_face])
    monkeypatch.setattr(service, "_load_face_app", lambda: fake_app)

    fake_image = np.zeros((240, 320, 3), dtype=np.uint8)

    with pytest.raises(Exception):
        service._extract_single_face_embedding(
            fake_image,
            context="unit-test",
        )


def _write_embedding(
    face_data_dir: Path,
    customer_id: str,
    centroid: list[float],
) -> None:
    customer_dir = face_data_dir / customer_id
    customer_dir.mkdir(parents=True)
    (customer_dir / "embedding.json").write_text(
        json.dumps(
            {
                "customer_id": customer_id,
                "model": "test-model",
                "centroid": centroid,
                "poses": {},
            }
        ),
        encoding="utf-8",
    )


def _mock_recognition_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    probe: list[float],
) -> None:
    monkeypatch.setattr(service, "_decode_image_data", lambda image_data: object())
    monkeypatch.setattr(
        service,
        "_extract_single_face_embedding",
        lambda image, context: (
            np.asarray(probe, dtype=np.float32),
            0.99,
            [1.0, 2.0, 3.0, 4.0],
        ),
    )


def test_recognize_customer_matches_best_candidate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """가장 유사한 등록 고객이 임계값을 넘으면 매칭되어야 한다."""
    face_data_dir = tmp_path / "faces"
    _write_embedding(face_data_dir, "customer_a", [1.0, 0.0])
    _write_embedding(face_data_dir, "customer_b", [0.0, 1.0])

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    _mock_recognition_pipeline(monkeypatch, [1.0, 0.0])
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda customer_id: {
            "name": "Alice" if customer_id == "customer_a" else "Bob",
            "face_registered": True,
        },
    )

    result = service.recognize_customer("data:image/jpeg;base64,fake", threshold=0.8)

    assert result["matched"] is True
    assert result["customer_id"] == "customer_a"
    assert result["name"] == "Alice"
    assert result["similarity"] == pytest.approx(1.0)
    assert result["reason"] == "matched"


def test_recognize_customer_returns_below_threshold(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """최고 유사도가 임계값보다 낮으면 고객을 반환하지 않아야 한다."""
    face_data_dir = tmp_path / "faces"
    _write_embedding(face_data_dir, "customer_a", [0.6, 0.8])

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    _mock_recognition_pipeline(monkeypatch, [1.0, 0.0])
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda customer_id: {"name": "Alice", "face_registered": True},
    )

    result = service.recognize_customer("data:image/jpeg;base64,fake", threshold=0.9)

    assert result["matched"] is False
    assert result["customer_id"] is None
    assert result["name"] is None
    assert result["similarity"] == pytest.approx(0.6)
    assert result["reason"] == "below_threshold"


def test_recognize_customer_returns_no_registered_embeddings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """등록 임베딩이 없으면 명확한 실패 사유를 반환해야 한다."""
    face_data_dir = tmp_path / "faces"
    face_data_dir.mkdir()

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    _mock_recognition_pipeline(monkeypatch, [1.0, 0.0])

    result = service.recognize_customer("data:image/jpeg;base64,fake")

    assert result["matched"] is False
    assert result["customer_id"] is None
    assert result["similarity"] is None
    assert result["reason"] == "no_registered_embeddings"


@pytest.mark.parametrize("threshold", [-0.01, 1.01])
def test_recognize_customer_rejects_invalid_threshold(threshold: float) -> None:
    """인식 임계값은 0과 1 사이 값만 허용해야 한다."""
    with pytest.raises(ValueError, match="0과 1 사이"):
        service.recognize_customer(
            "data:image/jpeg;base64,fake",
            threshold=threshold,
        )
def test_generate_customer_embeddings_rejects_missing_required_poses(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """필수 방향 사진이 모두 없으면 임베딩 생성을 거부해야 한다."""
    customer_id = "customer_001"
    face_data_dir = tmp_path / "faces"
    customer_dir = face_data_dir / customer_id
    customer_dir.mkdir(parents=True)

    # front 사진만 있고 나머지 필수 포즈는 없는 상황
    metadata = {
        "customer_id": customer_id,
        "samples": {
            "front": {
                "filename": "front.jpg",
            },
        },
    }
    (customer_dir / "enrollment.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda requested_id: {"customer_id": requested_id},
    )

    with pytest.raises(ValueError, match="모든 방향의 얼굴 사진"):
        service.generate_customer_embeddings(customer_id)
def test_generate_customer_embeddings_creates_embedding_and_updates_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """필수 포즈가 모두 있으면 임베딩 파일과 메타데이터가 생성되어야 한다."""
    customer_id = "customer_001"
    face_data_dir = tmp_path / "faces"
    customer_dir = face_data_dir / customer_id
    customer_dir.mkdir(parents=True)

    required_poses = ("front", "left", "right")
    metadata = {
        "customer_id": customer_id,
        "samples": {
            pose: {"filename": f"{pose}.jpg"}
            for pose in required_poses
        },
    }
    (customer_dir / "enrollment.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    monkeypatch.setattr(service, "REQUIRED_POSES", required_poses)
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda requested_id: {"customer_id": requested_id},
    )

    fake_cv2 = SimpleNamespace(imread=lambda path: object())
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    embeddings = {
        "front 사진": np.array([1.0, 0.0], dtype=np.float32),
        "left 사진": np.array([0.0, 1.0], dtype=np.float32),
        "right 사진": np.array([1.0, 1.0], dtype=np.float32)
        / np.sqrt(2.0),
    }

    def fake_extract(image: object, *, context: str):
        return embeddings[context], 0.99, [1.0, 2.0, 3.0, 4.0]

    monkeypatch.setattr(
        service,
        "_extract_single_face_embedding",
        fake_extract,
    )

    updated_customer: dict[str, object] = {}

    def fake_update_customer(
        requested_id: str,
        updates: dict[str, object],
    ) -> None:
        updated_customer["customer_id"] = requested_id
        updated_customer["updates"] = updates

    monkeypatch.setattr(service, "update_customer", fake_update_customer)
    monkeypatch.setattr(
        service,
        "_now_iso",
        lambda: "2026-07-19T00:00:00+00:00",
    )

    result = service.generate_customer_embeddings(customer_id)

    embedding_path = customer_dir / "embedding.json"
    assert embedding_path.exists()

    embedding_payload = json.loads(
        embedding_path.read_text(encoding="utf-8")
    )

    expected_centroid = np.array(
        [
            1.0 + 0.0 + 1.0 / np.sqrt(2.0),
            0.0 + 1.0 + 1.0 / np.sqrt(2.0),
        ],
        dtype=np.float32,
    )
    expected_centroid = expected_centroid / np.linalg.norm(expected_centroid)

    assert np.allclose(
        embedding_payload["centroid"],
        expected_centroid,
    )
    assert embedding_payload["embedding_dimension"] == 2
    assert set(embedding_payload["poses"]) == set(required_poses)

    updated_metadata = json.loads(
        (customer_dir / "enrollment.json").read_text(encoding="utf-8")
    )
    assert updated_metadata["embedding_ready"] is True
    assert updated_metadata["embedding_generated_at"] == (
        "2026-07-19T00:00:00+00:00"
    )

    assert updated_customer == {
        "customer_id": customer_id,
        "updates": {"face_registered": True},
    }

    assert result["embedding_ready"] is True
    assert result["embedding_dimension"] == 2
    assert result["sample_count"] == 3
def test_generate_customer_embeddings_rejects_unknown_customer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    customer_id = "missing_customer"

    monkeypatch.setattr(
        service,
        "get_customer",
        lambda requested_id: None,
    )

    with pytest.raises(KeyError) as error:
        service.generate_customer_embeddings(customer_id)

    assert error.value.args == (customer_id,)
def test_generate_customer_embeddings_rejects_unreadable_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    customer_id = "customer_001"
    face_data_dir = tmp_path / "faces"
    customer_dir = face_data_dir / customer_id
    customer_dir.mkdir(parents=True)

    required_poses = ("front", "left", "right")
    metadata = {
        "customer_id": customer_id,
        "samples": {
            pose: {"filename": f"{pose}.jpg"}
            for pose in required_poses
        },
    }
    (customer_dir / "enrollment.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    monkeypatch.setattr(service, "REQUIRED_POSES", required_poses)
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda requested_id: {"customer_id": requested_id},
    )

    fake_cv2 = SimpleNamespace(imread=lambda path: None)
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    with pytest.raises(ValueError, match="front 사진을 읽지 못했습니다"):
        service.generate_customer_embeddings(customer_id)
def test_generate_customer_embeddings_propagates_face_detection_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    customer_id = "customer_001"
    face_data_dir = tmp_path / "faces"
    customer_dir = face_data_dir / customer_id
    customer_dir.mkdir(parents=True)

    required_poses = ("front", "left", "right")

    metadata = {
        "customer_id": customer_id,
        "samples": {
            pose: {"filename": f"{pose}.jpg"}
            for pose in required_poses
        },
    }

    (customer_dir / "enrollment.json").write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    monkeypatch.setattr(service, "FACE_DATA_DIR", face_data_dir)
    monkeypatch.setattr(service, "REQUIRED_POSES", required_poses)
    monkeypatch.setattr(
        service,
        "get_customer",
        lambda _: {"customer_id": customer_id},
    )

    fake_cv2 = SimpleNamespace(imread=lambda _: object())
    monkeypatch.setitem(sys.modules, "cv2", fake_cv2)

    monkeypatch.setattr(
        service,
        "_extract_single_face_embedding",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            ValueError("front 사진에서 얼굴을 찾지 못했습니다.")
        ),
    )

    with pytest.raises(
        ValueError,
        match="front 사진에서 얼굴을 찾지 못했습니다.",
    ):
        service.generate_customer_embeddings(customer_id)