from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FacePose = Literal["front", "left", "right", "up", "down", "unknown"]


@dataclass(frozen=True)
class FaceFrameAnalysis:
    accepted: bool
    detected_pose: FacePose
    quality: float
    reason: str
    face_count: int = 1


class FacePipeline:
    """Jetson-side face processing interface.

    Phase 1 keeps the API stable before a concrete detector/landmark/embedding
    backend is installed. The mobile app may send `requested_pose`; this
    fallback accepts the frame after basic validation in the enrollment store.

    In Phase 2, replace `analyze_enrollment_frame` with a MediaPipe/InsightFace
    implementation without changing the public FastAPI contract.
    """

    backend_name = "fallback-requested-pose"

    def analyze_enrollment_frame(
        self,
        *,
        requested_pose: FacePose,
        image_size_bytes: int,
    ) -> FaceFrameAnalysis:
        if requested_pose == "unknown":
            return FaceFrameAnalysis(
                accepted=False,
                detected_pose="unknown",
                quality=0.0,
                reason="requested_pose_required_until_face_model_is_connected",
                face_count=0,
            )

        # Temporary quality estimate used only to exercise the app-to-Jetson
        # enrollment flow. A real model will replace this value in Phase 2.
        quality = min(1.0, max(0.1, image_size_bytes / 250_000))
        return FaceFrameAnalysis(
            accepted=True,
            detected_pose=requested_pose,
            quality=round(quality, 3),
            reason="accepted_by_phase1_fallback",
        )

    def finalize_customer(self, customer_id: str, sample_count: int) -> dict[str, object]:
        """Phase 1 finalization response.

        Embedding generation is deliberately deferred until the real face model
        is connected. Returning a structured response lets the app integrate now.
        """
        return {
            "customer_id": customer_id,
            "complete": False,
            "embedding_ready": False,
            "embedding_count": 0,
            "model": None,
            "sample_count": sample_count,
            "reason": "face_embedding_backend_not_connected",
        }


face_pipeline = FacePipeline()
