"""Inference for the hierarchical gated multi-task koELECTRA model.

Expected model directory::

    nlu/saved_models/hierarchical_gated_rdrop/
    ├── best_model.pt
    ├── label_maps.json
    ├── tokenizer/
    └── encoder_config/  # optional; embedded koELECTRA config is used if absent

Usage::

    python -m nlu.predict_multitask "아이스 카페라떼 두 잔 주세요"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from transformers import AutoConfig, AutoModel, AutoTokenizer, ElectraConfig

DEFAULT_MODEL_DIR = "nlu/saved_models/hierarchical_gated_rdrop"
DEFAULT_INTENT_THRESHOLD = 0.5
DEFAULT_SLOT_THRESHOLD = 0.5
MAX_LENGTH = 64
SLOT_NAMES = ("menu", "temperature", "quantity")
SUPPORTED_ENCODER = "monologg/koelectra-small-v3-discriminator"


def _embedded_koelectra_small_config() -> ElectraConfig:
    """Return the official koELECTRA-small-v3 architecture without network access."""
    return ElectraConfig(
        architectures=["ElectraForPreTraining"],
        attention_probs_dropout_prob=0.1,
        hidden_size=256,
        intermediate_size=1024,
        num_attention_heads=4,
        num_hidden_layers=12,
        embedding_size=128,
        hidden_act="gelu",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        layer_norm_eps=1e-12,
        max_position_embeddings=512,
        type_vocab_size=2,
        vocab_size=35000,
        pad_token_id=0,
    )


def load_encoder_config(model_dir: Path, encoder_name: str):
    """Load a local encoder config and never require an online model download."""
    config_dir = model_dir / "encoder_config"
    if config_dir.exists():
        return AutoConfig.from_pretrained(str(config_dir), local_files_only=True)
    if encoder_name == SUPPORTED_ENCODER:
        return _embedded_koelectra_small_config()
    raise FileNotFoundError(
        f"encoder_config 폴더가 없고 내장 설정을 지원하지 않는 encoder입니다: {encoder_name}"
    )


def load_checkpoint(path: Path, device: str):
    """Load only a trusted checkpoint produced by this project."""
    try:
        return torch.load(path, map_location=device, weights_only=False)
    except TypeError:
        # Older PyTorch releases do not expose the weights_only argument.
        return torch.load(path, map_location=device)


class GatedAttentionPooler(nn.Module):
    """Combine task-specific attention pooling with the CLS representation."""

    def __init__(self, hidden_size: int, dropout: float):
        super().__init__()
        self.attn = nn.Linear(hidden_size, 1)
        self.gate = nn.Linear(hidden_size * 2, hidden_size)
        self.norm = nn.LayerNorm(hidden_size)
        self.dropout = nn.Dropout(dropout)

    def forward(self, hidden_states: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        scores = self.attn(hidden_states).squeeze(-1)
        scores = scores.masked_fill(attention_mask == 0, -1e4)
        weights = torch.softmax(scores, dim=-1)
        attended = torch.bmm(weights.unsqueeze(1), hidden_states).squeeze(1)

        cls = hidden_states[:, 0]
        gate = torch.sigmoid(self.gate(torch.cat([cls, attended], dim=-1)))
        fused = gate * attended + (1.0 - gate) * cls
        return self.dropout(self.norm(fused))


class HierarchicalGatedMultiTaskModel(nn.Module):
    """Shared koELECTRA encoder with intent-conditioned slot heads."""

    def __init__(self, encoder_config, num_labels: dict[str, int], dropout: float = 0.15):
        super().__init__()
        # The full fine-tuned encoder weights are restored from best_model.pt below.
        # Constructing from config avoids downloading the base model on Jetson.
        self.encoder = AutoModel.from_config(encoder_config)
        hidden_size = self.encoder.config.hidden_size

        self.poolers = nn.ModuleDict(
            {
                task: GatedAttentionPooler(hidden_size, dropout)
                for task in ("intent", "menu", "temperature", "quantity")
            }
        )

        self.intent_head = nn.Sequential(
            nn.Linear(hidden_size, hidden_size),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_size, num_labels["intent"]),
        )

        self.intent_context = nn.Sequential(
            nn.Linear(num_labels["intent"], hidden_size),
            nn.Tanh(),
        )

        self.slot_heads = nn.ModuleDict(
            {
                task: nn.Sequential(
                    nn.Linear(hidden_size, hidden_size),
                    nn.GELU(),
                    nn.Dropout(dropout),
                    nn.Linear(hidden_size, num_labels[task]),
                )
                for task in SLOT_NAMES
            }
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        token_type_ids: torch.Tensor | None = None,
    ) -> dict[str, torch.Tensor]:
        encoder_kwargs = {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
        }
        if token_type_ids is not None:
            encoder_kwargs["token_type_ids"] = token_type_ids

        hidden_states = self.encoder(**encoder_kwargs).last_hidden_state

        intent_repr = self.poolers["intent"](hidden_states, attention_mask)
        intent_logits = self.intent_head(intent_repr)
        intent_probs = torch.softmax(intent_logits, dim=-1)
        intent_context = self.intent_context(intent_probs)

        logits = {"intent": intent_logits}
        for task in SLOT_NAMES:
            slot_repr = self.poolers[task](hidden_states, attention_mask)
            logits[task] = self.slot_heads[task](slot_repr + intent_context)
        return logits


class HierarchicalNLUPredictor:
    """Load one multi-task checkpoint and predict an entire NLU frame."""

    def __init__(
        self,
        model_dir: str | Path = DEFAULT_MODEL_DIR,
        device: str | None = None,
    ) -> None:
        self.model_dir = Path(model_dir)
        self.checkpoint_path = self.model_dir / "best_model.pt"
        self.tokenizer_dir = self.model_dir / "tokenizer"
        self.label_maps_path = self.model_dir / "label_maps.json"

        required_paths = [
            self.checkpoint_path,
            self.tokenizer_dir,
            self.label_maps_path,
        ]
        missing = [str(path) for path in required_paths if not path.exists()]
        if missing:
            raise FileNotFoundError(
                "멀티태스크 모델 파일이 없습니다. 다음 경로를 확인하세요: "
                + ", ".join(missing)
            )

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.tokenizer = AutoTokenizer.from_pretrained(
            str(self.tokenizer_dir),
            local_files_only=True,
        )

        with self.label_maps_path.open("r", encoding="utf-8") as file:
            self.label_maps = json.load(file)

        checkpoint = load_checkpoint(self.checkpoint_path, self.device)
        encoder_name = str(checkpoint.get("encoder_name", SUPPORTED_ENCODER))
        encoder_config = load_encoder_config(self.model_dir, encoder_name)

        self.model = HierarchicalGatedMultiTaskModel(
            encoder_config,
            num_labels={key: int(value) for key, value in checkpoint["num_labels"].items()},
            dropout=float(checkpoint["dropout"]),
        )
        self.model.load_state_dict(checkpoint["model_state_dict"], strict=True)
        self.model.to(self.device)
        self.model.eval()

    def _decode(self, task: str, class_id: int) -> str:
        return str(self.label_maps[task]["id_to_class"][str(class_id)])

    @staticmethod
    def _convert_quantity(value: str | None) -> int | str | None:
        if value is None:
            return None
        try:
            return int(float(value))
        except ValueError:
            return value

    def predict(
        self,
        text: str,
        intent_threshold: float = DEFAULT_INTENT_THRESHOLD,
        slot_threshold: float = DEFAULT_SLOT_THRESHOLD,
    ) -> dict[str, Any]:
        clean_text = str(text).strip()
        if not clean_text:
            return {
                "text": clean_text,
                "intent": "UNKNOWN",
                "intent_confidence": 0.0,
                "order": None,
                "needs_reprompt": True,
                "robot_response": "죄송해요. 다시 한 번 말씀해주시겠어요?",
            }

        encoded = self.tokenizer(
            clean_text,
            return_tensors="pt",
            truncation=True,
            max_length=MAX_LENGTH,
        )
        encoded = {key: value.to(self.device) for key, value in encoded.items()}

        with torch.inference_mode():
            logits = self.model(**encoded)
            probabilities = {
                task: torch.softmax(task_logits, dim=-1)[0]
                for task, task_logits in logits.items()
            }

        intent_id = int(torch.argmax(probabilities["intent"]).item())
        intent = self._decode("intent", intent_id)
        intent_confidence = float(probabilities["intent"][intent_id].item())

        result: dict[str, Any] = {
            "text": clean_text,
            "intent": intent,
            "intent_confidence": round(intent_confidence, 4),
            "order": None,
            "needs_reprompt": intent_confidence < intent_threshold,
            "device": self.device,
        }

        if intent != "ORDER":
            result["robot_response"] = self._make_non_order_response(intent, result["needs_reprompt"])
            return result

        order: dict[str, Any] = {}
        slot_confidence: dict[str, float] = {}
        missing_slots: list[str] = []

        for task in SLOT_NAMES:
            task_id = int(torch.argmax(probabilities[task]).item())
            raw_value = self._decode(task, task_id)
            confidence = float(probabilities[task][task_id].item())
            value: Any = None if raw_value == "NONE" else raw_value
            if task == "quantity":
                value = self._convert_quantity(value)

            order[task] = value
            slot_confidence[task] = round(confidence, 4)
            if value is None or confidence < slot_threshold:
                missing_slots.append(task)

        order["confidence"] = slot_confidence
        order["missing_slots"] = missing_slots
        order["needs_reprompt"] = bool(missing_slots)

        result["order"] = order
        result["needs_reprompt"] = result["needs_reprompt"] or order["needs_reprompt"]
        result["robot_response"] = self._make_order_response(order)
        return result

    @staticmethod
    def _make_non_order_response(intent: str, needs_reprompt: bool) -> str:
        if needs_reprompt:
            return "죄송해요. 다시 한 번 말씀해주시겠어요?"
        responses = {
            "GUIDE": "무엇을 안내해드릴까요?",
            "PAYMENT": "결제 방법을 안내해드릴게요.",
            "CANCEL": "취소할 주문을 확인해드릴게요.",
            "MODIFY": "변경할 주문 내용을 말씀해주세요.",
            "AFFIRM": "네, 확인했습니다.",
            "DENY": "알겠습니다. 다시 확인해드릴게요.",
            "UNKNOWN": "죄송해요. 주문이나 매장 이용에 관해 말씀해주세요.",
        }
        return responses.get(intent, "말씀하신 내용을 확인해드릴게요.")

    @staticmethod
    def _make_order_response(order: dict[str, Any]) -> str:
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
        }.get(str(temperature), str(temperature))
        return f"{temperature_text} {menu} {quantity}잔 맞으신가요?".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run hierarchical gated multi-task NLU inference.")
    parser.add_argument("text", nargs="?", help="STT text to analyze.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    parser.add_argument("--intent-threshold", type=float, default=DEFAULT_INTENT_THRESHOLD)
    parser.add_argument("--slot-threshold", type=float, default=DEFAULT_SLOT_THRESHOLD)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = HierarchicalNLUPredictor(args.model_dir, device=args.device)

    if args.text:
        print(
            json.dumps(
                predictor.predict(args.text, args.intent_threshold, args.slot_threshold),
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
                predictor.predict(text, args.intent_threshold, args.slot_threshold),
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    main()
