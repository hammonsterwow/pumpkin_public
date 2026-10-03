from __future__ import annotations

import pytest

from nlu.config import DEFAULT_ENCODER, SUPPORTED_ENCODERS
from nlu.model import (
    KOELECTRA_BASE,
    KOELECTRA_SMALL,
    embedded_encoder_config,
)


def test_small_is_default_runtime_encoder() -> None:
    assert DEFAULT_ENCODER == KOELECTRA_SMALL
    assert KOELECTRA_SMALL in SUPPORTED_ENCODERS
    assert KOELECTRA_BASE in SUPPORTED_ENCODERS


def test_embedded_small_config_matches_training_encoder() -> None:
    config = embedded_encoder_config(KOELECTRA_SMALL)

    assert config.hidden_size == 256
    assert config.embedding_size == 128
    assert config.intermediate_size == 1024
    assert config.num_attention_heads == 4
    assert config.num_hidden_layers == 12
    assert config.vocab_size == 35000


def test_embedded_base_config_remains_supported() -> None:
    config = embedded_encoder_config(KOELECTRA_BASE)

    assert config.hidden_size == 768
    assert config.embedding_size == 768
    assert config.intermediate_size == 3072
    assert config.num_attention_heads == 12
    assert config.num_hidden_layers == 12


def test_unknown_encoder_requires_explicit_encoder_config() -> None:
    with pytest.raises(ValueError, match="지원하지 않는 encoder"):
        embedded_encoder_config("example/unsupported-encoder")
