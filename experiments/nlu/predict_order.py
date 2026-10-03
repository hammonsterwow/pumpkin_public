"""Predict order slots from Korean ORDER text.

Usage:
    python -m nlu.predict_order "아이스 아메리카노 한 잔 주세요"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

DEFAULT_BASE_MODEL_DIR = "nlu/saved_models"
SLOT_NAMES = ["menu", "temperature", "quantity"]
DEFAULT_CONFIDENCE_THRESHOLD = 0.2


class SlotModel:
    def __init__(self, slot_name: str, model_dir: str | Path, device: str):
        self.slot_name = slot_name
        self.model_dir = Path(model_dir)
        if not self.model_dir.exists():
            raise FileNotFoundError(
                f"{slot_name} model not found: {self.model_dir}. "
                "Train it first with: python -m nlu.train_order_slots"
            )

        self.device = device
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
        inputs = self.tokenizer(
            text,
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

        label = self.id2label[pred_id]
        return {
            "slot": self.slot_name,
            "value": None if label == "NONE" else label,
            "raw_value": label,
            "confidence": round(confidence, 4),
        }


class OrderPredictor:
    """Predict menu, temperature, quantity using three slot classifiers."""

    def __init__(self, base_model_dir: str | Path = DEFAULT_BASE_MODEL_DIR, device: str | None = None):
        self.base_model_dir = Path(base_model_dir)
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.models = {
            slot_name: SlotModel(slot_name, self.base_model_dir / f"{slot_name}_model", self.device)
            for slot_name in SLOT_NAMES
        }

    def predict(self, text: str, threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> dict[str, Any]:
        clean_text = str(text).strip()
        if not clean_text:
            return {
                "text": clean_text,
                "order": {
                    "menu": None,
                    "temperature": None,
                    "quantity": None,
                },
                "confidence": {},
                "needs_reprompt": True,
                "missing_slots": SLOT_NAMES,
            }

        slot_results = {slot_name: model.predict(clean_text) for slot_name, model in self.models.items()}

        order = {}
        confidence = {}
        missing_slots = []

        for slot_name, result in slot_results.items():
            value = result["value"]
            if slot_name == "quantity" and value is not None:
                try:
                    value = int(float(value))
                except ValueError:
                    pass

            order[slot_name] = value
            confidence[slot_name] = result["confidence"]

            if value is None or result["confidence"] < threshold:
                missing_slots.append(slot_name)

        return {
            "text": clean_text,
            "order": order,
            "confidence": confidence,
            "needs_reprompt": len(missing_slots) > 0,
            "missing_slots": missing_slots,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict order slots with trained koELECTRA slot models.")
    parser.add_argument("text", nargs="?", help="ORDER text to parse.")
    parser.add_argument("--model-dir", default=DEFAULT_BASE_MODEL_DIR, help="Base saved model directory.")
    parser.add_argument("--threshold", type=float, default=DEFAULT_CONFIDENCE_THRESHOLD)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = OrderPredictor(args.model_dir)

    if args.text:
        print(json.dumps(predictor.predict(args.text, args.threshold), ensure_ascii=False, indent=2))
        return

    while True:
        text = input("ORDER text> ").strip()
        if text.lower() in {"q", "quit", "exit"}:
            break
        print(json.dumps(predictor.predict(text, args.threshold), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
