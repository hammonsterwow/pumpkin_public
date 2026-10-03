import torch
import torch.nn as nn
from transformers import AutoModel

from .config import (
    INTENT_LABELS,
    MAX_ITEMS,
    MENU_LABELS,
    MODEL_NAME,
    QUANTITY_LABELS,
    STATUS_LABELS,
    TEMPERATURE_LABELS,
)


class IndependentItemHeadModel(nn.Module):
    '''KoELECTRA-small + independent item-position heads baseline.'''

    def __init__(self):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(MODEL_NAME)
        hidden = self.encoder.config.hidden_size

        self.intent_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden, len(INTENT_LABELS)),
        )
        self.status_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden, len(STATUS_LABELS)),
        )

        self.active_head = nn.Linear(hidden, MAX_ITEMS * 2)
        self.menu_head = nn.Linear(hidden, MAX_ITEMS * len(MENU_LABELS))
        self.temperature_head = nn.Linear(
            hidden,
            MAX_ITEMS * len(TEMPERATURE_LABELS),
        )
        self.quantity_head = nn.Linear(
            hidden,
            MAX_ITEMS * len(QUANTITY_LABELS),
        )

    def forward(self, input_ids, attention_mask):
        memory = self.encoder(
            input_ids=input_ids,
            attention_mask=attention_mask,
        ).last_hidden_state
        cls = memory[:, 0]
        batch_size = cls.size(0)

        return {
            'intent_logits': self.intent_head(cls),
            'status_logits': self.status_head(cls),
            'active_logits': self.active_head(cls).view(batch_size, MAX_ITEMS, 2),
            'menu_logits': self.menu_head(cls).view(
                batch_size,
                MAX_ITEMS,
                len(MENU_LABELS),
            ),
            'temperature_logits': self.temperature_head(cls).view(
                batch_size,
                MAX_ITEMS,
                len(TEMPERATURE_LABELS),
            ),
            'quantity_logits': self.quantity_head(cls).view(
                batch_size,
                MAX_ITEMS,
                len(QUANTITY_LABELS),
            ),
        }


class ItemQueryDecoderModel(nn.Module):
    '''Current project structure: KoELECTRA-small + learned Item Query Decoder.'''

    def __init__(self):
        super().__init__()
        self.encoder = AutoModel.from_pretrained(MODEL_NAME)
        hidden = self.encoder.config.hidden_size

        self.intent_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden, len(INTENT_LABELS)),
        )
        self.status_head = nn.Sequential(
            nn.Dropout(0.15),
            nn.Linear(hidden, len(STATUS_LABELS)),
        )

        self.item_queries = nn.Parameter(torch.randn(MAX_ITEMS, hidden) * 0.02)
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=hidden,
            nhead=4,
            dim_feedforward=hidden * 4,
            dropout=0.15,
            activation='gelu',
            batch_first=True,
            norm_first=True,
        )
        self.item_decoder = nn.TransformerDecoder(
            decoder_layer,
            num_layers=2,
        )
        self.item_norm = nn.LayerNorm(hidden)

        self.active_head = nn.Linear(hidden, 2)
        self.menu_head = nn.Linear(hidden, len(MENU_LABELS))
        self.temperature_head = nn.Linear(hidden, len(TEMPERATURE_LABELS))
        self.quantity_head = nn.Linear(hidden, len(QUANTITY_LABELS))

    def forward(self, input_ids, attention_mask):
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
            'intent_logits': self.intent_head(cls),
            'status_logits': self.status_head(cls),
            'active_logits': self.active_head(decoded),
            'menu_logits': self.menu_head(decoded),
            'temperature_logits': self.temperature_head(decoded),
            'quantity_logits': self.quantity_head(decoded),
        }


def build_model(config):
    if config.architecture == 'independent':
        return IndependentItemHeadModel()
    if config.architecture == 'item_query':
        return ItemQueryDecoderModel()
    raise ValueError(f'unknown architecture: {config.architecture}')
