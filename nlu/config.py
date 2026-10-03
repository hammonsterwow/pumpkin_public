"""Runtime configuration for the production Structure B NLU model."""

from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_NAME = "structure_b_item_query_decoder"
SCHEMA_VERSION = "1.0"

# Current production training uses koELECTRA-small. Keep base in the supported
# list so older Structure B checkpoints can still be restored when needed.
DEFAULT_ENCODER = "monologg/koelectra-small-v3-discriminator"
SUPPORTED_ENCODERS = (
    DEFAULT_ENCODER,
    "monologg/koelectra-base-v3-discriminator",
)

# Backward-compatible alias for code that imported the previous singular name.
SUPPORTED_ENCODER = DEFAULT_ENCODER

DEFAULT_MODEL_DIR = Path(
    os.getenv(
        "PUMPKIN_NLU_MODEL_DIR",
        PROJECT_ROOT / "nlu" / "saved_models" / MODEL_NAME,
    )
)
DEFAULT_CONFIDENCE_THRESHOLD = float(
    os.getenv("PUMPKIN_NLU_CONFIDENCE_THRESHOLD", "0.5")
)
DEFAULT_DEVICE = os.getenv("PUMPKIN_NLU_DEVICE", "auto").strip().lower()
