import numpy as np
import pytest

from robot_controller.realtime_face_recognition import (
    RecognitionStabilizer,
    RealtimeFaceRecognizer,
    cosine_similarity,
)


def test_cosine_similarity_matches_identical_embeddings():
    vector = np.array([1.0, 2.0, 3.0], dtype=np.float32)
    assert cosine_similarity(vector, vector) == pytest.approx(1.0)


def test_cosine_similarity_rejects_dimension_mismatch():
    with pytest.raises(ValueError):
        cosine_similarity([1.0, 2.0], [1.0])


def test_stabilizer_requires_three_votes_in_five_samples():
    stabilizer = RecognitionStabilizer(window_size=5, required_votes=3)

    assert stabilizer.add("customer-1") is None
    assert stabilizer.add(None) is None
    assert stabilizer.add("customer-1") is None
    assert stabilizer.add("customer-2") is None
    assert stabilizer.add("customer-1") == "customer-1"


def test_stabilizer_reset_removes_previous_votes():
    stabilizer = RecognitionStabilizer(window_size=3, required_votes=2)
    stabilizer.add("customer-1")
    stabilizer.reset()

    assert stabilizer.add("customer-1") is None


def test_recognizer_pauses_expensive_inference_after_stable_match():
    class AnalyzerSpy:
        calls = 0

        def get(self, frame):
            self.calls += 1
            raise AssertionError("analyzer must stay paused after a stable match")

    recognizer = RealtimeFaceRecognizer.__new__(RealtimeFaceRecognizer)
    recognizer.last_emitted_id = "customer-1"
    recognizer.analyzer = AnalyzerSpy()

    assert recognizer.process(object()) is None
    assert recognizer.analyzer.calls == 0


def test_recognizer_stops_after_bounded_unmatched_attempts():
    class AnalyzerSpy:
        calls = 0

        def get(self, frame):
            self.calls += 1
            raise AssertionError("analyzer must stop after the session budget")

    recognizer = RealtimeFaceRecognizer.__new__(RealtimeFaceRecognizer)
    recognizer.last_emitted_id = None
    recognizer.max_attempts = 5
    recognizer.attempt_count = 5
    recognizer.analyzer = AnalyzerSpy()

    assert recognizer.process(object()) is None
    assert recognizer.analyzer.calls == 0
