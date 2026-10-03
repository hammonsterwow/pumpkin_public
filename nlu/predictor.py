"""Production inference for the Structure B item-query decoder.

This module performs only NLU work: model loading, inference, label decoding,
confidence calculation, and missing-slot detection. Dialogue decisions and robot
utterances belong to the ROS decision/action nodes.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import torch
from transformers import AutoConfig, AutoTokenizer

from .config import (
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_DEVICE,
    DEFAULT_ENCODER,
    DEFAULT_MODEL_DIR,
    MODEL_NAME,
    SCHEMA_VERSION,
)
from .model import ItemQueryDecoderModel, embedded_encoder_config
from .schema import NLUItem, NLUResult


def _load_checkpoint(path: Path, device: str) -> dict[str, Any]:
    try:
        return torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        return torch.load(path, map_location=device)


def _resolve_device(requested: str | None) -> str:
    value = (requested or DEFAULT_DEVICE or "auto").strip().lower()
    if value == "auto":
        return "cuda" if torch.cuda.is_available() else "cpu"
    if value not in {"cpu", "cuda"}:
        raise ValueError("device는 auto, cpu, cuda 중 하나여야 합니다.")
    if value == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA 장치를 요청했지만 torch.cuda.is_available()이 False입니다.")
    return value


def _load_encoder_config(model_dir: Path, encoder_name: str):
    config_dir = model_dir / "encoder_config"
    if config_dir.exists():
        return AutoConfig.from_pretrained(str(config_dir), local_files_only=True)
    try:
        return embedded_encoder_config(encoder_name)
    except ValueError as exc:
        raise FileNotFoundError(
            "encoder_config 폴더가 없고 내장 설정을 지원하지 않는 encoder입니다: "
            f"{encoder_name}"
        ) from exc


class StructureBNLUPredictor:
    """Load the saved Structure B model and return a structured NLU frame."""

    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        device: str | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.checkpoint_path = self.model_dir / "best_model.pt"
        self.tokenizer_dir = self.model_dir / "tokenizer"

        missing = [
            str(path)
            for path in (self.checkpoint_path, self.tokenizer_dir)
            if not path.exists()
        ]
        if missing:
            raise FileNotFoundError(
                "Structure B 모델 파일이 없습니다. 다음 경로를 확인하세요: "
                + ", ".join(missing)
            )

        self.device = _resolve_device(device)
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.tokenizer_dir),
            local_files_only=True,
        )
        checkpoint = _load_checkpoint(self.checkpoint_path, self.device)

        self.label_maps = checkpoint["label_maps"]
        self.max_length = int(checkpoint.get("max_length", 96))
        self.max_items = int(checkpoint.get("max_items", 3))
        encoder_name = str(checkpoint.get("model_name", DEFAULT_ENCODER))
        encoder_config = _load_encoder_config(self.model_dir, encoder_name)

        self.model = ItemQueryDecoderModel(
            encoder_config=encoder_config,
            label_maps=self.label_maps,
            max_items=self.max_items,
        )
        self.model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        self.model.to(self.device)
        self.model.eval()

    def _decode(self, task: str, class_id: int) -> str:
        mapping = self.label_maps[task]["id2label"]
        if class_id in mapping:
            return str(mapping[class_id])
        return str(mapping[str(class_id)])

    @staticmethod
    def _to_quantity(value: str | None) -> int | None:
        if value is None or value == "NONE":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def predict(
        self,
        text: str,
        confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD,
    ) -> NLUResult:
        started_at = time.perf_counter()
        clean_text = str(text).strip()

        if not clean_text:
            return {
                "schema_version": SCHEMA_VERSION,
                "model_name": MODEL_NAME,
                "text": "",
                "intent": "UNKNOWN",
                "intent_confidence": 0.0,
                "order_status": "UNPARSABLE",
                "order_status_confidence": 0.0,
                "items": [],
                "needs_reprompt": True,
                "device": self.device,
                "latency_ms": 0.0,
            }

        encoded = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        )
        input_ids = encoded["input_ids"].to(self.device)
        attention_mask = encoded["attention_mask"].to(self.device)

        with torch.inference_mode():
            outputs = self.model(input_ids=input_ids, attention_mask=attention_mask)
            probabilities = {
                key: torch.softmax(value, dim=-1)[0]
                for key, value in outputs.items()
            }

        intent_id = int(torch.argmax(probabilities["intent_logits"]).item())
        status_id = int(torch.argmax(probabilities["status_logits"]).item())
        intent = self._decode("intent", intent_id)
        order_status = self._decode("order_status", status_id)
        intent_confidence = float(probabilities["intent_logits"][intent_id].item())
        status_confidence = float(probabilities["status_logits"][status_id].item())

        items: list[NLUItem] = []
        if intent == "ORDER":
            active_ids = probabilities["active_logits"].argmax(dim=-1)
            for item_index in range(self.max_items):
                if int(active_ids[item_index].item()) != 1:
                    continue

                menu_probs = probabilities["menu_logits"][item_index]
                temperature_probs = probabilities["temperature_logits"][item_index]
                quantity_probs = probabilities["quantity_logits"][item_index]

                menu_id = int(torch.argmax(menu_probs).item())
                temperature_id = int(torch.argmax(temperature_probs).item())
                quantity_id = int(torch.argmax(quantity_probs).item())

                raw_menu = self._decode("menu", menu_id)
                raw_temperature = self._decode("temperature", temperature_id)
                raw_quantity = self._decode("quantity", quantity_id)

                menu = None if raw_menu == "NONE" else raw_menu
                temperature = None if raw_temperature == "NONE" else raw_temperature
                quantity = self._to_quantity(raw_quantity)

                confidence = {
                    "active": round(
                        float(probabilities["active_logits"][item_index, 1].item()),
                        4,
                    ),
                    "menu": round(float(menu_probs[menu_id].item()), 4),
                    "temperature": round(float(temperature_probs[temperature_id].item()), 4),
                    "quantity": round(float(quantity_probs[quantity_id].item()), 4),
                }
                missing_slots = [
                    slot
                    for slot, value in (
                        ("menu", menu),
                        ("temperature", temperature),
                        ("quantity", quantity),
                    )
                    if value is None
                ]

                items.append(
                    {
                        "item_id": item_index,
                        "menu": menu,
                        "temperature": temperature,
                        "quantity": quantity,
                        "confidence": confidence,
                        "missing_slots": missing_slots,
                    }
                )

        low_item_confidence = any(
            value < confidence_threshold
            for item in items
            for value in item["confidence"].values()
        )
        has_missing_slots = any(item["missing_slots"] for item in items)
        needs_reprompt = intent_confidence < confidence_threshold
        if intent == "ORDER":
            needs_reprompt = needs_reprompt or any(
                (
                    status_confidence < confidence_threshold,
                    not items,
                    order_status != "VALID",
                    has_missing_slots,
                    low_item_confidence,
                )
            )

        latency_ms = (time.perf_counter() - started_at) * 1000
        return {
            "schema_version": SCHEMA_VERSION,
            "model_name": MODEL_NAME,
            "text": clean_text,
            "intent": intent,
            "intent_confidence": round(intent_confidence, 4),
            "order_status": order_status,
            "order_status_confidence": round(status_confidence, 4),
            "items": items,
            "needs_reprompt": needs_reprompt,
            "device": self.device,
            "latency_ms": round(latency_ms, 2),
        }
