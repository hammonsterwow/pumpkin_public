from __future__ import annotations

import copy
import importlib.util
import json
import sys
import threading
import types
from pathlib import Path

import pytest


# The callback pipeline is pure Python. Provide tiny fallbacks so the regression
# suite can also run on development machines that do not have ROS2 installed.
if importlib.util.find_spec("rclpy") is None:
    rclpy_module = types.ModuleType("rclpy")
    rclpy_node_module = types.ModuleType("rclpy.node")

    class Node:
        pass

    rclpy_node_module.Node = Node
    rclpy_module.node = rclpy_node_module
    sys.modules["rclpy"] = rclpy_module
    sys.modules["rclpy.node"] = rclpy_node_module

if importlib.util.find_spec("std_msgs") is None:
    std_msgs_module = types.ModuleType("std_msgs")
    std_msgs_msg_module = types.ModuleType("std_msgs.msg")

    class String:
        def __init__(self):
            self.data = ""

    class Bool:
        def __init__(self):
            self.data = False

    std_msgs_msg_module.String = String
    std_msgs_msg_module.Bool = Bool
    std_msgs_module.msg = std_msgs_msg_module
    sys.modules["std_msgs"] = std_msgs_module
    sys.modules["std_msgs.msg"] = std_msgs_msg_module

if importlib.util.find_spec("nlu") is None:
    nlu_module = types.ModuleType("nlu")
    nlu_config_module = types.ModuleType("nlu.config")

    class StructureBNLUPredictor:
        pass

    nlu_module.StructureBNLUPredictor = StructureBNLUPredictor
    nlu_config_module.DEFAULT_CONFIDENCE_THRESHOLD = 0.5
    nlu_config_module.DEFAULT_MODEL_DIR = Path("unused")
    nlu_config_module.MODEL_NAME = "structure_b_item_query_decoder"
    sys.modules["nlu"] = nlu_module
    sys.modules["nlu.config"] = nlu_config_module

from std_msgs.msg import String

from robot_controller import action_node as action_module
from robot_controller.action_node import ActionNode
from robot_controller.decision_node import DecisionNode
from robot_controller.nlu_node import NLUNode
from robot_controller.response_manager import ResponseManager
from robot_controller.response_manager_node import ResponseManagerNode


class SilentLogger:
    def info(self, *_args, **_kwargs):
        pass

    def warning(self, *_args, **_kwargs):
        pass

    def error(self, *_args, **_kwargs):
        pass


LOGGER = SilentLogger()


class NoopThread:
    """Keep the timeout fallback from sleeping during deterministic tests."""

    def __init__(self, *args, **kwargs):
        self.target = kwargs.get("target")
        self.args = kwargs.get("args", ())

    def start(self):
        pass


class RoutedPublisher:
    def __init__(self, route=None):
        self.route = route
        self.messages: list[str] = []

    def publish(self, msg):
        self.messages.append(msg.data)
        if self.route is not None:
            self.route(msg)

    def json_messages(self):
        return [json.loads(message) for message in self.messages]


class FakePredictor:
    def __init__(self):
        self.responses: dict[str, dict] = {}
        self.device = "cpu"

    def set_response(self, text: str, result: dict):
        self.responses[text] = copy.deepcopy(result)

    def predict(self, text: str, confidence_threshold=0.5):
        del confidence_threshold
        return copy.deepcopy(
            self.responses.get(
                text,
                make_nlu_result(
                    text,
                    intent="UNKNOWN",
                    confidence=0.1,
                    order_status="NONE",
                    items=[],
                    needs_reprompt=True,
                ),
            )
        )


def make_nlu_result(
    text: str,
    *,
    intent: str = "ORDER",
    confidence: float = 0.99,
    order_status: str = "VALID",
    items: list[dict] | None = None,
    needs_reprompt: bool | None = None,
):
    if items is None:
        items = []
    if needs_reprompt is None:
        needs_reprompt = order_status != "VALID"
    return {
        "schema_version": "1.0",
        "model_name": "structure_b_item_query_decoder",
        "text": text,
        "intent": intent,
        "intent_confidence": confidence,
        "order_status": order_status,
        "order_status_confidence": confidence,
        "items": copy.deepcopy(items),
        "needs_reprompt": needs_reprompt,
        "device": "cpu",
        "latency_ms": 1.0,
    }


def item(menu, temperature=None, quantity=None):
    return {
        "menu": menu,
        "temperature": temperature,
        "quantity": quantity,
    }


class PipelineHarness:
    def __init__(self, monkeypatch):
        monkeypatch.setattr(action_module.threading, "Thread", NoopThread)
        for cls in (NLUNode, DecisionNode, ResponseManagerNode, ActionNode):
            monkeypatch.setattr(cls, "get_logger", lambda self: LOGGER, raising=False)

        self.predictor = FakePredictor()

        self.action = ActionNode.__new__(ActionNode)
        self.action.max_stt_retries = 2
        self.action.stt_retry_count = 0
        self.action.tts_done_timeout_sec = 12.0
        self.action._listen_lock = threading.Lock()
        self.action._listen_token = 0
        self.action._listen_pending = False
        self.action._listen_seen_speaking = False
        self.action.publisher = RoutedPublisher()
        self.action.stt_trigger_publisher = RoutedPublisher()

        self.response = ResponseManagerNode.__new__(ResponseManagerNode)
        self.response.manager = ResponseManager()
        self.response.publisher = RoutedPublisher(self.action.response_callback)
        self.action.response_request_publisher = RoutedPublisher(
            self.response.request_callback
        )

        self.decision = DecisionNode.__new__(DecisionNode)
        self.decision.state = "IDLE"
        self.decision.session_id = "test-session"
        self.decision.current_order = None
        self.decision.waiting_for = None
        self.decision.nlu_reprompt_count = 0
        self.decision.slot_retry_count = 0
        self.decision.max_nlu_reprompts = 2
        self.decision.max_slot_retries = 2
        self.decision.publisher = RoutedPublisher(self.response.decision_callback)

        self.nlu = NLUNode.__new__(NLUNode)
        self.nlu.predictor = self.predictor
        self.nlu.confidence_threshold = 0.5
        self.nlu.publisher = RoutedPublisher(self.decision.intent_callback)

    @property
    def nlu_results(self):
        return self.nlu.publisher.json_messages()

    @property
    def decisions(self):
        return self.decision.publisher.json_messages()

    @property
    def responses(self):
        return self.response.publisher.json_messages()

    @property
    def actions(self):
        return self.action.publisher.json_messages()

    @property
    def stt_triggers(self):
        return list(self.action.stt_trigger_publisher.messages)

    def say(self, text: str, result: dict | None = None):
        if result is not None:
            self.predictor.set_response(text, result)
        before = len(self.actions)
        msg = String()
        msg.data = text
        self.nlu.voice_callback(msg)
        assert len(self.actions) == before + 1
        return self.decisions[-1], self.actions[-1]

    def tts_status(self, status: str):
        msg = String()
        msg.data = status
        self.action.tts_status_callback(msg)
        self.decision.tts_status_callback(msg)


@pytest.fixture
def pipeline(monkeypatch):
    return PipelineHarness(monkeypatch)


def two_drinks_missing_temperature(text="아메리카노랑 라떼 하나씩 주세요"):
    return make_nlu_result(
        text,
        order_status="INCOMPLETE",
        items=[
            item("아메리카노", quantity=1),
            item("카페라떼", quantity=1),
        ],
    )


def two_drinks_complete(
    text="아메리카노랑 라떼 둘 다 따뜻하게 하나씩 주세요",
):
    """Return a complete order whose HOT labels are explicitly present in text."""
    return make_nlu_result(
        text,
        items=[
            item("아메리카노", "HOT", 1),
            item("카페라떼", "HOT", 1),
        ],
    )


def test_response_manager_separates_decision_text_from_robot_action(pipeline):
    text = "아이스 아메리카노 한 잔 주세요"
    decision, action = pipeline.say(
        text,
        make_nlu_result(text, items=[item("아메리카노", "ICE", 1)]),
    )

    response = pipeline.responses[-1]
    assert "speech" not in decision
    assert decision["response_key"] == "confirm_order"
    assert response["speech"] == "아이스 아메리카노 1잔 맞으신가요?"
    assert action["tts"] == response["speech"]
    assert action["raw_response"]["response_key"] == "confirm_order"


def test_voice_text_to_robot_action_for_cold_only_multi_order(pipeline):
    text = "딸기스무디랑 레모네이드 하나씩 주세요"
    decision, action = pipeline.say(
        text,
        make_nlu_result(
            text,
            items=[
                item("딸기스무디", quantity=1),
                item("레몬에이드", quantity=1),
            ],
        ),
    )

    assert pipeline.nlu_results[-1]["text"] == text
    assert decision["decision"] == "CONFIRM_ORDER"
    assert action["decision"] == "CONFIRM_ORDER"
    assert [entry["temperature"] for entry in decision["order"]["items"]] == [
        "ICE",
        "ICE",
    ]


def test_single_order_short_temperature_followup(pipeline):
    text = "아메리카노 하나요"
    decision, _ = pipeline.say(
        text,
        make_nlu_result(
            text,
            order_status="INCOMPLETE",
            items=[item("아메리카노", quantity=1)],
        ),
    )
    assert decision["decision"] == "ASK_TEMPERATURE"
    assert decision["waiting_for"] == {"item_id": 0, "slot": "temperature"}

    decision, _ = pipeline.say("따뜻하게요")
    assert decision["decision"] == "CONFIRM_ORDER"
    assert decision["order"]["items"][0]["temperature"] == "HOT"


def test_multi_order_asks_each_temperature_and_merges_by_item_id(pipeline):
    decision, _ = pipeline.say(
        "아메리카노랑 라떼 하나씩 주세요",
        two_drinks_missing_temperature(),
    )
    assert decision["decision"] == "ASK_TEMPERATURE"
    assert decision["waiting_for"] == {"item_id": 0, "slot": "temperature"}
    assert "speech" not in decision
    assert "아메리카노" in pipeline.responses[-1]["speech"]

    decision, _ = pipeline.say("따뜻하게요")
    assert decision["decision"] == "ASK_TEMPERATURE"
    assert decision["waiting_for"] == {"item_id": 1, "slot": "temperature"}
    assert "speech" not in decision
    assert "카페라떼" in pipeline.responses[-1]["speech"]

    decision, _ = pipeline.say("아이스요")
    assert decision["decision"] == "CONFIRM_ORDER"
    assert [entry["temperature"] for entry in decision["order"]["items"]] == [
        "HOT",
        "ICE",
    ]


def test_group_temperature_answer_applies_to_all_items(pipeline):
    pipeline.say(
        "아메리카노랑 라떼 하나씩 주세요",
        two_drinks_missing_temperature(),
    )
    decision, _ = pipeline.say("둘 다 아이스로요")

    assert pipeline.nlu_results[-1]["explicit_slots"]["apply_to_all_items"] is True
    assert decision["decision"] == "CONFIRM_ORDER"
    assert [entry["temperature"] for entry in decision["order"]["items"]] == [
        "ICE",
        "ICE",
    ]


def test_ambiguous_multi_item_correction_asks_for_menu_target(pipeline):
    complete_text = "아메리카노랑 라떼 둘 다 따뜻하게 하나씩 주세요"
    initial_decision, _ = pipeline.say(
        complete_text,
        two_drinks_complete(complete_text),
    )
    assert initial_decision["decision"] == "CONFIRM_ORDER"

    decision, _ = pipeline.say("아니요")
    assert decision["decision"] == "MODIFY_ORDER"

    decision, _ = pipeline.say("아이스로 바꿔주세요")
    assert decision["decision"] == "MODIFY_ORDER"
    assert decision["reason"] == "ambiguous_correction_target"
    assert "speech" not in decision
    assert "어떤 메뉴" in pipeline.responses[-1]["speech"]


def test_cancel_and_restart_clear_current_order(pipeline):
    pipeline.say(
        "아메리카노 하나요",
        make_nlu_result(
            "아메리카노 하나요",
            order_status="INCOMPLETE",
            items=[item("아메리카노", quantity=1)],
        ),
    )
    decision, _ = pipeline.say("주문 취소할게요")
    assert decision["decision"] == "CANCEL_ORDER"
    assert pipeline.decision.state == "IDLE"
    assert pipeline.decision.current_order is None

    pipeline.say(
        "아메리카노 하나요",
        make_nlu_result(
            "아메리카노 하나요",
            order_status="INCOMPLETE",
            items=[item("아메리카노", quantity=1)],
        ),
    )
    decision, _ = pipeline.say("처음부터 다시 주문할게요")
    assert decision["decision"] == "REORDER_REQUEST"
    assert pipeline.decision.state == "ORDER_LISTEN"
    assert pipeline.decision.current_order is None


def test_slot_answer_failure_stops_after_three_attempts(pipeline):
    pipeline.say(
        "아메리카노 하나요",
        make_nlu_result(
            "아메리카노 하나요",
            order_status="INCOMPLETE",
            items=[item("아메리카노", quantity=1)],
        ),
    )

    decisions = [pipeline.say(text)[0] for text in ("글쎄요", "모르겠어요", "뭐라고요")]
    assert [decision["decision"] for decision in decisions] == [
        "REPROMPT",
        "REPROMPT",
        "REORDER_REQUEST",
    ]
    assert decisions[-1]["reason"] == "slot_retry_exhausted"


def test_low_confidence_nlu_stops_after_three_attempts(pipeline):
    decisions = [pipeline.say(text)[0] for text in ("음", "저기", "모르겠어")]
    assert [decision["decision"] for decision in decisions] == [
        "REPROMPT",
        "REPROMPT",
        "REORDER_REQUEST",
    ]
    assert decisions[-1]["reason"] == "nlu_retry_exhausted"


def test_stt_starts_only_after_tts_speaking_then_done(pipeline):
    pipeline.say(
        "아메리카노 하나요",
        make_nlu_result(
            "아메리카노 하나요",
            order_status="INCOMPLETE",
            items=[item("아메리카노", quantity=1)],
        ),
    )
    assert pipeline.stt_triggers == []

    pipeline.tts_status("done")
    assert pipeline.stt_triggers == []

    pipeline.tts_status("speaking")
    assert pipeline.stt_triggers == []

    pipeline.tts_status("done")
    assert pipeline.stt_triggers == ["start"]


def test_stt_retry_text_is_rendered_by_response_manager(pipeline):
    msg = String()
    msg.data = "too_quiet"
    pipeline.action.stt_status_callback(msg)

    response = pipeline.responses[-1]
    action = pipeline.actions[-1]
    assert response["response_key"] == "stt_retry"
    assert response["response_source"] == "execution"
    assert action["decision"] == "STT_RETRY"
    assert action["tts"] == "잘 못 들었어요. 다시 한 번 말씀해 주세요."


def test_order_completion_tts_resets_dialogue_to_idle(pipeline):
    pipeline.say(
        "아이스 아메리카노 한 잔 주세요",
        make_nlu_result(
            "아이스 아메리카노 한 잔 주세요",
            items=[item("아메리카노", "ICE", 1)],
        ),
    )
    decision, action = pipeline.say("네")
    assert decision["decision"] == "ORDER_CONFIRMED"
    assert action["decision"] == "ORDER_CONFIRMED"
    assert pipeline.decision.state == "ORDER_COMPLETE"

    pipeline.tts_status("done")
    assert pipeline.decision.state == "IDLE"
    assert pipeline.decision.current_order is None
    assert pipeline.decision.waiting_for is None
