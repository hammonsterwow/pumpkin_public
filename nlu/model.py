"""Neural-network definition for the Structure B item-query NLU model."""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
from transformers import AutoModel, ElectraConfig


KOELECTRA_SMALL = "monologg/koelectra-small-v3-discriminator"
KOELECTRA_BASE = "monologg/koelectra-base-v3-discriminator"


def embedded_koelectra_small_config() -> ElectraConfig:
    """Return the koELECTRA-small-v3 architecture without network access."""

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


def embedded_koelectra_base_config() -> ElectraConfig:
    """Return the koELECTRA-base-v3 architecture without network access."""

    return ElectraConfig(
        architectures=["ElectraForPreTraining"],
        attention_probs_dropout_prob=0.1,
        hidden_size=768,
        intermediate_size=3072,
        num_attention_heads=12,
        num_hidden_layers=12,
        embedding_size=768,
        hidden_act="gelu",
        hidden_dropout_prob=0.1,
        initializer_range=0.02,
        layer_norm_eps=1e-12,
        max_position_embeddings=512,
        type_vocab_size=2,
        vocab_size=35000,
        pad_token_id=0,
    )


def embedded_encoder_config(encoder_name: str) -> ElectraConfig:
    """Return an offline encoder config for supported koELECTRA checkpoints."""

    if encoder_name == KOELECTRA_SMALL:
        return embedded_koelectra_small_config()
    if encoder_name == KOELECTRA_BASE:
        return embedded_koelectra_base_config()
    raise ValueError(f"지원하지 않는 encoder입니다: {encoder_name}")


def label_count(label_maps: dict[str, Any], task: str) -> int:
    task_map = label_maps[task]
    if "label2id" in task_map:
        return len(task_map["label2id"])
    if "id2label" in task_map:
        return len(task_map["id2label"])
    raise KeyError(f"{task} label map에 label2id 또는 id2label이 없습니다.")


class ItemQueryDecoderModel(nn.Module):
    """koELECTRA encoder with learned item queries and a Transformer decoder."""

    def __init__(
        self,
        encoder_config,
        label_maps: dict[str, Any],
        max_items: int,
    ) -> None:
        super().__init__()
        self.encoder = AutoModel.from_config(encoder_config)
        hidden_size = self.encoder.config.hidden_size

        self.intent_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden_size, label_count(label_maps, "intent")),
        )
        self.status_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden_size, label_count(label_maps, "order_status")),
        )

        self.item_queries = nn.Parameter(torch.randn(max_items, hidden_size) * 0.02)
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=hidden_size,
            nhead=4,
            dim_feedforward=hidden_size * 4,
            dropout=0.15,
            activation="gelu",
            batch_first=True,
            norm_first=True,
        )
        self.item_decoder = nn.TransformerDecoder(decoder_layer, num_layers=2)
        self.item_norm = nn.LayerNorm(hidden_size)

        self.active_head = nn.Linear(hidden_size, 2)
        self.menu_head = nn.Linear(hidden_size, label_count(label_maps, "menu"))
        self.temperature_head = nn.Linear(
            hidden_size,
            label_count(label_maps, "temperature"),
        )
        self.quantity_head = nn.Linear(
            hidden_size,
            label_count(label_maps, "quantity"),
        )

    def forward(
        self,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> dict[str, torch.Tensor]:
        memory = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
        ).last_hidden_state
        cls = memory[:, 0]

        batch_size = input_ids.size(0)
        queries = self.item_queries.unsqueeze(0).expand(batch_size, -1, -1)
        decoded = self.item_decoder(
            tgt=queries,
            memory=memory,
            memory_key_padding_mask=(attention_mask == 0),
        )
        decoded = self.item_norm(decoded)

        return {
            "intent_logits": self.intent_head(cls),
            "status_logits": self.status_head(cls),
            "active_logits": self.active_head(decoded),
            "menu_logits": self.menu_head(decoded),
            "temperature_logits": self.temperature_head(decoded),
            "quantity_logits": self.quantity_head(decoded),
        }
