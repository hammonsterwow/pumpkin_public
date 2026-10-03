"""Predict user intent from STT-generated Korean text.

Usage:
    python -m nlu.predict_intent "아이스 아메리카노 한 잔 주세요"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

DEFAULT_MODEL_DIR = "nlu/saved_models/intent_model"
DEFAULT_CONFIDENCE_THRESHOLD = 0.15


class IntentPredictor:
    """koELECTRA-based intent classifier wrapper."""

    def __init__(self, model_dir: str | Path = DEFAULT_MODEL_DIR, device: str | None = None):
        self.model_dir = Path(model_dir)
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"Intent model not found: {self.model_dir}. "
                "Train it first with: python -m nlu.train_intent"
            )

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(str(self.model_dir))
        self.model = AutoModelForSequenceClassification.from_pretrained(str(self.model_dir))
        self.model.to(self.device)
        self.model.eval()

        self.id2label = self._load_id2label()

    def _load_id2label(self) -> dict[int, str]:
        label_map_path = self.model_dir / "label_map.json"
        if label_map_path.exists():
            with label_map_path.open("r", encoding="utf-8") as f:
                label_map = json.load(f)
            return {int(k): v for k, v in label_map["id2label"].items()}

        return {int(k): v for k, v in self.model.config.id2label.items()}

    def predict(self, text: str, max_length: int = 64) -> dict[str, Any]:
        clean_text = str(text).strip()
        if not clean_text:
            return {"text": clean_text, "intent": "UNKNOWN", "confidence": 0.0}

        inputs = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=max_length,
        )
        inputs = {key: value.to(self.device) for key, value in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            probabilities = torch.softmax(outputs.logits, dim=-1)[0]
            pred_id = int(torch.argmax(probabilities).item())
            confidence = float(probabilities[pred_id].item())

        return {
            "text": clean_text,
            "intent": self.id2label[pred_id],
            "confidence": round(confidence, 4),
        }

    def predict_with_action(self, text: str, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict[str, Any]:
        result = self.predict(text)
        result["needs_reprompt"] = result["confidence"] < threshold
        if result["needs_reprompt"]:
            result["robot_response"] = "죄송해요. 다시 한 번 말씀해주시겠어요?"
        elif result["intent"] == "ORDER":
            result["robot_response"] = "주문 내용을 확인해드릴게요."
        elif result["intent"] == "GUIDE":
            result["robot_response"] = "매장 이용 안내를 도와드릴게요."
        elif result["intent"] == "PAYMENT":
            result["robot_response"] = "결제 관련 안내를 도와드릴게요."
        elif result["intent"] == "CANCEL":
            result["robot_response"] = "주문 취소를 도와드릴게요."
        elif result["intent"] == "MODIFY":
            result["robot_response"] = "주문 변경을 도와드릴게요."
        elif result["intent"] == "AFFIRM":
            result["robot_response"] = "네, 확인했습니다."
        elif result["intent"] == "DENY":
            result["robot_response"] = "아니오로 확인했습니다."
        else:
            result["robot_response"] = "주문이나 매장 안내를 도와드릴 수 있어요."
        return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict intent with trained koELECTRA model.")
    parser.add_argument("text", nargs="?", help="STT text to classify.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR, help="Saved model directory.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = IntentPredictor(args.model_dir)

    if args.text:
        print(json.dumps(predictor.predict_with_action(args.text, args.threshold), ensure_ascii=False, indent=2))
        return

    while True:
        text = input("STT text> ").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        print(json.dumps(predictor.predict_with_action(text, args.threshold), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
