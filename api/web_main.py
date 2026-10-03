from __future__ import annotations

from fastapi import HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from api.main import WEB_DIST_DIR, app
from api.ros_bridge import ros_web_bridge


class AnalyzeStep3Request(BaseModel):
    text: str


@app.post("/api/stt/trigger")
def trigger_robot_stt() -> dict[str, object]:
    try:
        return ros_web_bridge.trigger_stt()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail=f"STT 시작 요청에 실패했습니다: {error}",
        ) from error


@app.get("/api/stt/latest")
def latest_robot_stt() -> dict[str, object]:
    """Return the latest unmodified ROS conversation-flow snapshot."""

    return ros_web_bridge.stt_snapshot()


@app.post("/api/orders/analyze-step3")
def analyze_order_step3(payload: AnalyzeStep3Request) -> dict[str, object]:
    """Inject test text into the real ROS flow and return NLU/Decision/Action data."""

    clean_text = payload.text.strip()
    if not clean_text:
        raise HTTPException(status_code=400, detail="주문 문장을 입력해주세요.")

    try:
        snapshot = ros_web_bridge.analyze_text(clean_text)
        raw_analysis = snapshot.get("analysis")
        if not isinstance(raw_analysis, dict):
            raise RuntimeError("nlu_node의 분석 결과를 받지 못했습니다.")

        result: dict[str, object] = dict(raw_analysis)
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


if WEB_DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=WEB_DIST_DIR, html=True), name="web")
