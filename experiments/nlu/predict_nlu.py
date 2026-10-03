"""Run full NLU: intent classification + order slot prediction.

Usage:
    python -m nlu.predict_nlu "아이스 아메리카노 한 잔 주세요" --threshold 0.2
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from .predict_intent import DEFAULT_CONFIDENCE_THRESHOLD as DEFAULT_INTENT_THRESHOLD
from .predict_intent import IntentPredictor
from .predict_order import DEFAULT_CONFIDENCE_THRESHOLD as DEFAULT_ORDER_THRESHOLD
from .predict_order import OrderPredictor


class NLUPredictor:
    """Full NLU pipeline for the robot ordering scenario."""

    def __init__(self, intent_model_dir: str = "nlu/saved_models/intent_model", order_model_dir: str = "nlu/saved_models"):
        self.intent_predictor = IntentPredictor(intent_model_dir)
        self.order_predictor = OrderPredictor(order_model_dir)

    def predict(
        self,
        text: str,
        intent_threshold: float = DEFAULT_INTENT_THRESHOLD,
        order_threshold: float = DEFAULT_ORDER_THRESHOLD,
    ) -> dict[str, Any]:
        intent_result = self.intent_predictor.predict_with_action(text, threshold=intent_threshold)

        result: dict[str, Any] = {
            "text": intent_result["text"],
            "intent": intent_result["intent"],
            "intent_confidence": intent_result["confidence"],
            "intent_needs_reprompt": intent_result["needs_reprompt"],
            "order": None,
            "robot_response": intent_result["robot_response"],
        }

        if intent_result["intent"] != "ORDER":
            return result

        order_result = self.order_predictor.predict(text, threshold=order_threshold)
        result["order"] = {
            "menu": order_result["order"]["menu"],
            "temperature": order_result["order"]["temperature"],
            "quantity": order_result["order"]["quantity"],
            "confidence": order_result["confidence"],
            "needs_reprompt": order_result["needs_reprompt"],
            "missing_slots": order_result["missing_slots"],
        }

        result["robot_response"] = make_order_response(result)
        return result


def make_order_response(nlu_result: dict[str, Any]) -> str:
    order = nlu_result.get("order")
    if not order:
        return nlu_result.get("robot_response", "주문을 도와드릴게요.")

    menu = order.get("menu")
    temperature = order.get("temperature")
    quantity = order.get("quantity")
    missing_slots = order.get("missing_slots", [])

    if "menu" in missing_slots or not menu:
        return "어떤 메뉴를 주문하시겠어요?"

    if "quantity" in missing_slots or not quantity:
        return f"{menu} 몇 잔 주문하시겠어요?"

    if "temperature" in missing_slots or not temperature:
        return f"{menu} {quantity}잔 맞으실까요? 아이스로 드릴까요, 따뜻하게 드릴까요?"

    temperature_text = {
        "ICE": "아이스",
        "HOT": "따뜻한",
        "COLD": "차가운",
        "NONE": "",
    }.get(str(temperature), str(temperature))

    return f"{temperature_text} {menu} {quantity}잔 맞으신가요?".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run full NLU pipeline.")
    parser.add_argument("text", nargs="?", help="STT text to analyze.")
    parser.add_argument("--intent-model-dir", default="nlu/saved_models/intent_model")
    parser.add_argument("--order-model-dir", default="nlu/saved_models")
    parser.add_argument("--intent-threshold", type=float, default=0.2)
    parser.add_argument("--order-threshold", type=float, default=0.2)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = NLUPredictor(args.intent_model_dir, args.order_model_dir)

    if args.text:
        print(
            json.dumps(
                predictor.predict(args.text, args.intent_threshold, args.order_threshold),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    while True:
        text = input("STT text> ").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        print(
            json.dumps(
                predictor.predict(text, args.intent_threshold, args.order_threshold),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
