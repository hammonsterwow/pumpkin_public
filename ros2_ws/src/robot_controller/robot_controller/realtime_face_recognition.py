from __future__ import annotations

import os
import time
from collections import Counter, deque
from dataclasses import dataclass
from typing import Any, Iterable

import numpy as np


def cosine_similarity(left: Iterable[float], right: Iterable[float]) -> float:
    left_vector = np.asarray(list(left), dtype=np.float32)
    right_vector = np.asarray(list(right), dtype=np.float32)
    if left_vector.shape != right_vector.shape or left_vector.ndim != 1:
        raise ValueError("embedding dimensions do not match")
    denominator = float(np.linalg.norm(left_vector) * np.linalg.norm(right_vector))
    if denominator <= 0.0:
        return -1.0
    return float(np.dot(left_vector, right_vector) / denominator)


@dataclass(frozen=True)
class CustomerEmbedding:
    customer_id: str
    name: str
    preferred_menu: str
    preferred_temperature: str
    preferred_quantity: int
    model: str
    vector: np.ndarray


class RecognitionStabilizer:
    def __init__(self, window_size: int = 5, required_votes: int = 3) -> None:
        if required_votes < 1 or window_size < required_votes:
            raise ValueError("window_size must be >= required_votes >= 1")
        self.required_votes = required_votes
        self.votes: deque[str | None] = deque(maxlen=window_size)
        self.confirmed_customer_id: str | None = None

    def add(self, customer_id: str | None) -> str | None:
        self.votes.append(customer_id)
        if customer_id is None:
            return None
        count = Counter(self.votes)[customer_id]
        if count >= self.required_votes:
            self.confirmed_customer_id = customer_id
            return customer_id
        return None

    def reset(self) -> None:
        self.votes.clear()
        self.confirmed_customer_id = None


class FirestoreCustomerCache:
    def __init__(self, project_id: str, refresh_sec: float = 60.0) -> None:
        self.project_id = project_id
        self.refresh_sec = max(5.0, refresh_sec)
        self.customers: list[CustomerEmbedding] = []
        self.last_refresh = 0.0
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google.cloud import firestore
            self._client = firestore.Client(project=self.project_id)
        return self._client

    def refresh_if_due(self, *, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_refresh < self.refresh_sec:
            return

        loaded: list[CustomerEmbedding] = []
        for snapshot in self._get_client().collection("users").stream():
            data = snapshot.to_dict() or {}
            embedding = data.get("faceEmbedding")
            if not data.get("faceRegistered") or not isinstance(embedding, dict):
                continue
            vector = embedding.get("centroid")
            dimension = embedding.get("dimension")
            model = str(embedding.get("model") or "")
            if model != "buffalo_l" or not isinstance(vector, list):
                continue
            try:
                dimension = int(dimension)
                values = np.asarray(vector, dtype=np.float32)
                quantity = int(data.get("preferredQuantity") or 1)
            except (TypeError, ValueError):
                continue
            if dimension != 512 or values.shape != (512,) or quantity < 1:
                continue
            loaded.append(
                CustomerEmbedding(
                    customer_id=str(data.get("uid") or snapshot.id),
                    name=str(data.get("name") or "").strip(),
                    preferred_menu=str(data.get("preferredMenu") or "").strip(),
                    preferred_temperature=str(
                        data.get("preferredTemperature") or "NONE"
                    ).upper(),
                    preferred_quantity=quantity,
                    model=model,
                    vector=values,
                )
            )

        self.customers = loaded
        self.last_refresh = now


class RealtimeFaceRecognizer:
    """Run local buffalo_l recognition on selected frames.

    Optional heavy dependencies are imported only when this feature is enabled,
    so a recognition setup failure never prevents ordinary presence/order flow.
    """

    def __init__(self) -> None:
        project_id = os.getenv("PUMPKIN_FIREBASE_PROJECT_ID", "").strip()
        if not project_id:
            raise RuntimeError("PUMPKIN_FIREBASE_PROJECT_ID is required")

        self.threshold = float(os.getenv("PUMPKIN_FACE_THRESHOLD", "0.45"))
        self.interval_sec = max(
            0.1, float(os.getenv("PUMPKIN_FACE_INTERVAL_SEC", "0.4"))
        )
        self.cache = FirestoreCustomerCache(
            project_id,
            refresh_sec=float(os.getenv("PUMPKIN_FACE_CACHE_REFRESH_SEC", "5")),
        )
        self.stabilizer = RecognitionStabilizer(
            window_size=int(os.getenv("PUMPKIN_FACE_VOTE_WINDOW", "5")),
            required_votes=int(os.getenv("PUMPKIN_FACE_REQUIRED_VOTES", "3")),
        )
        # CPU-only InsightFace can consume every Jetson core. Bound each presence
        # session so an unregistered customer cannot slow the entire order flow
        # indefinitely. reset() starts a fresh budget for the next customer.
        self.max_attempts = max(
            self.stabilizer.required_votes,
            int(os.getenv("PUMPKIN_FACE_MAX_ATTEMPTS", "5")),
        )
        self.attempt_count = 0
        self.last_run = 0.0
        self.last_emitted_id: str | None = None

        from insightface.app import FaceAnalysis

        providers = ["CUDAExecutionProvider", "CPUExecutionProvider"]
        self.analyzer = FaceAnalysis(name="buffalo_l", providers=providers)
        self.analyzer.prepare(ctx_id=0, det_size=(640, 640))
        self.cache.refresh_if_due(force=True)

    def reset(self) -> None:
        self.stabilizer.reset()
        self.attempt_count = 0
        self.last_emitted_id = None

    def process(self, frame: Any) -> dict[str, Any] | None:
        # One physical customer session needs only one stable identity event.
        # On Jetson installations without onnxruntime-gpu, buffalo_l runs on CPU;
        # continuing to analyze every frame after a match starves STT/NLU. The
        # vision node calls reset() when the customer leaves, which re-enables
        # recognition for the next session.
        if (
            self.last_emitted_id is not None
            or self.attempt_count >= self.max_attempts
        ):
            return None

        now = time.monotonic()
        if now - self.last_run < self.interval_sec:
            return None
        self.last_run = now
        self.cache.refresh_if_due()

        self.attempt_count += 1
        faces = self.analyzer.get(frame)
        if len(faces) != 1:
            self.stabilizer.add(None)
            return None

        embedding = getattr(faces[0], "normed_embedding", None)
        if embedding is None:
            self.stabilizer.add(None)
            return None

        best_customer = None
        best_similarity = -1.0
        for customer in self.cache.customers:
            similarity = cosine_similarity(embedding, customer.vector)
            if similarity > best_similarity:
                best_customer = customer
                best_similarity = similarity

        candidate_id = (
            best_customer.customer_id
            if best_customer is not None and best_similarity >= self.threshold
            else None
        )
        confirmed_id = self.stabilizer.add(candidate_id)
        if confirmed_id is None or confirmed_id == self.last_emitted_id:
            return None

        customer = next(
            item for item in self.cache.customers
            if item.customer_id == confirmed_id
        )
        self.last_emitted_id = confirmed_id
        return {
            "matched": True,
            "customer_id": customer.customer_id,
            "name": customer.name,
            "similarity": round(best_similarity, 6),
            "threshold": self.threshold,
            "reason": "stable_match",
            "customer": {
                "preferred_menu": customer.preferred_menu,
                "preferred_temperature": customer.preferred_temperature,
                "preferred_quantity": customer.preferred_quantity,
            },
        }
