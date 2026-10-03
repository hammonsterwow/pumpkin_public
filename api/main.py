from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.customer_store import (
    create_customer,
    delete_customer,
    get_customer,
    list_customers,
    update_customer,
)
from api.face_enrollment_store import (
    finalize_face_enrollment,
    get_enrollment_status,
    reset_face_enrollment,
    save_face_sample,
    start_face_enrollment_session,
)
from api.firebase_face_backend import router as firebase_face_backend_router
from api.routers.face_embeddings import router as face_embeddings_router
from api.routers.orders import router as orders_router


ROOT_DIR = Path(__file__).resolve().parents[1]
WEB_DIST_DIR = ROOT_DIR / "web/dist"
NLU_MODEL_NAME = "structure_b_item_query_decoder"

app = FastAPI(title="Pumpkin Physical AI API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.getenv(
            "PUMPKIN_CORS_ORIGINS",
            "http://localhost:3000,http://127.0.0.1:3000",
        ).split(",")
        if origin.strip()
    ],
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
)
app.include_router(orders_router)
app.include_router(face_embeddings_router)
app.include_router(firebase_face_backend_router)


class AnalyzeRequest(BaseModel):
    text: str


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    model_name: str | None = None
    detail: str | None = None


class CustomerCreateRequest(BaseModel):
    customer_id: str | None = None
    name: str = Field(min_length=1, max_length=80)
    preferred_menu: str = Field(default="", max_length=100)
    preferred_temperature: Literal["HOT", "ICE", "NONE"] = "NONE"
    preferred_quantity: int = Field(default=1, ge=1, le=20)
    visit_count: int = Field(default=0, ge=0)
    face_registered: bool = False


class CustomerUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    preferred_menu: str | None = Field(default=None, max_length=100)
    preferred_temperature: Literal["HOT", "ICE", "NONE"] | None = None
    preferred_quantity: int | None = Field(default=None, ge=1, le=20)
    visit_count: int | None = Field(default=None, ge=0)
    face_registered: bool | None = None


class FaceSampleRequest(BaseModel):
    pose: Literal["front", "left", "right", "up", "down"]
    image_data: str = Field(min_length=32)


class FaceSessionRequest(BaseModel):
    customer_id: str = Field(min_length=1, max_length=120)
    reset_existing: bool = True


class FaceUploadRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=120)
    customer_id: str = Field(min_length=1, max_length=120)
    pose: Literal["front", "left", "right", "up", "down"]
    image_data: str = Field(min_length=32)
    captured_at: str | None = Field(default=None, max_length=80)
    sequence: int | None = Field(default=None, ge=0)


class FaceFinalizeRequest(BaseModel):
    session_id: str = Field(min_length=8, max_length=120)
    customer_id: str = Field(min_length=1, max_length=120)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Report whether the web API is connected to the production ROS pipeline."""

    try:
        from api.ros_bridge import ros_web_bridge

        ros_status = ros_web_bridge.status()
    except Exception as error:
        return HealthResponse(
            status="error",
            model_name=NLU_MODEL_NAME,
            detail=str(error),
        )

    if not ros_status.get("running"):
        missing = ros_status.get("missing_nodes") or []
        detail = ros_status.get("detail") or (
            f"ROS 핵심 노드가 준비되지 않았습니다: {', '.join(missing)}"
            if missing
            else "ROS 핵심 노드가 준비되지 않았습니다."
        )
        return HealthResponse(
            status="error",
            model_name=NLU_MODEL_NAME,
            detail=str(detail),
        )

    return HealthResponse(status="ok", model_name=NLU_MODEL_NAME)


@app.get("/api/ros/status")
def ros_status() -> dict[str, object]:
    try:
        from api.ros_bridge import ros_web_bridge

        return ros_web_bridge.status()
    except Exception as error:
        return {
            "running": False,
            "nodes": [],
            "state": "error",
            "detail": str(error),
        }


@app.get("/api/admin/snapshot")
def admin_snapshot() -> dict[str, object]:
    """Return one monitoring payload for the administrator dashboard."""

    try:
        from api.ros_bridge import ros_web_bridge

        return ros_web_bridge.admin_snapshot()
    except Exception as error:
        return {
            "system": {
                "running": False,
                "nodes": [],
                "state": "error",
                "detail": str(error),
            },
            "fsm_state": "ERROR",
            "pipeline": {
                "status": "error",
                "text": "",
                "analysis": None,
                "decision": None,
                "response_text": "",
                "action": None,
                "error": str(error),
            },
            "face": {
                "detected": False,
                "matched": False,
                "customer_id": None,
                "similarity": None,
                "reason": "bridge_error",
            },
        }


@app.get("/api/customers")
def customers_list() -> list[dict[str, object]]:
    return list_customers()


@app.get("/api/customers/{customer_id}")
def customer_detail(customer_id: str) -> dict[str, object]:
    customer = get_customer(customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    return customer


@app.post("/api/customers", status_code=201)
def customer_create(payload: CustomerCreateRequest) -> dict[str, object]:
    try:
        return create_customer(payload.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.put("/api/customers/{customer_id}")
def customer_update(
    customer_id: str,
    payload: CustomerUpdateRequest,
) -> dict[str, object]:
    customer = update_customer(customer_id, payload.model_dump(exclude_unset=True))
    if customer is None:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    return customer


@app.delete("/api/customers/{customer_id}", status_code=204)
def customer_delete(customer_id: str) -> Response:
    if not delete_customer(customer_id):
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    return Response(status_code=204)


@app.get("/api/customers/{customer_id}/face-enrollment")
def face_enrollment_status(customer_id: str) -> dict[str, object]:
    status = get_enrollment_status(customer_id)
    if status is None:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    return status


@app.post("/api/customers/{customer_id}/face-enrollment/samples")
def face_enrollment_sample(
    customer_id: str,
    payload: FaceSampleRequest,
) -> dict[str, object]:
    try:
        return save_face_sample(customer_id, payload.pose, payload.image_data)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.delete("/api/customers/{customer_id}/face-enrollment", status_code=204)
def face_enrollment_reset(customer_id: str) -> Response:
    if not reset_face_enrollment(customer_id):
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.")
    return Response(status_code=204)


@app.post("/api/faces/session", status_code=201)
def face_session_start(payload: FaceSessionRequest) -> dict[str, object]:
    """Start a customer-app enrollment session and return the first required pose."""

    try:
        return start_face_enrollment_session(
            payload.customer_id,
            reset_existing=payload.reset_existing,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error


@app.post("/api/faces/upload")
def face_session_upload(payload: FaceUploadRequest) -> dict[str, object]:
    """Store one automatically captured candidate frame for a required pose."""

    try:
        return save_face_sample(
            payload.customer_id,
            payload.pose,
            payload.image_data,
            session_id=payload.session_id,
            captured_at=payload.captured_at,
            sequence=payload.sequence,
        )
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/faces/finalize")
def face_session_finalize(payload: FaceFinalizeRequest) -> dict[str, object]:
    """Mark image collection complete without claiming that embeddings exist yet."""

    try:
        return finalize_face_enrollment(payload.customer_id, payload.session_id)
    except KeyError as error:
        raise HTTPException(status_code=404, detail="고객을 찾을 수 없습니다.") from error
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error


@app.post("/api/orders/analyze")
def analyze_order(payload: AnalyzeRequest) -> dict[str, object]:
    """Compatibility endpoint that runs text through the real ROS pipeline."""

    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="주문 문장을 입력해주세요.")

    try:
        from api.ros_bridge import ros_web_bridge

        snapshot = ros_web_bridge.analyze_text(clean_text)
        analysis = snapshot.get("analysis")
        if not isinstance(analysis, dict):
            raise RuntimeError("nlu_node의 분석 결과를 받지 못했습니다.")

        result: dict[str, object] = dict(analysis)
        result["confirmation_text"] = str(snapshot.get("response_text") or "")
        result["decision"] = snapshot.get("decision")
        result["action"] = snapshot.get("action")
        result["flow_status"] = str(snapshot.get("status") or "unknown")
        return result
    except (RuntimeError, TimeoutError) as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"ROS 주문 흐름 테스트에 실패했습니다: {error}",
        ) from error
