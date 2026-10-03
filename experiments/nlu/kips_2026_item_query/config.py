from dataclasses import dataclass
from pathlib import Path

MODEL_NAME = 'monologg/koelectra-small-v3-discriminator'
MAX_LENGTH = 96
MAX_ITEMS = 3
BATCH_SIZE = 16
EPOCHS = 20
PATIENCE = 3
WEIGHT_DECAY = 0.01
WARMUP_RATIO = 0.1
GRAD_CLIP_NORM = 1.0
NUM_WORKERS = 2
BASE_LR = 1e-5
HEAD_LR = 5e-5
SPLIT_SEED = 20260809
VALID_RATIO = 0.10
RDROP_ALPHA = 0.5

MAIN_SEEDS = [42, 43, 44]
ABLATION_SEEDS = [42]

INTENT_LABELS = ['ORDER', 'MODIFY', 'CANCEL', 'AFFIRM', 'DENY', 'GUIDE', 'PAYMENT', 'UNKNOWN']
STATUS_LABELS = ['NONE', 'VALID', 'INCOMPLETE', 'CONFLICT', 'OUT_OF_POLICY', 'UNPARSABLE']
MENU_LABELS = ['NONE', '아메리카노', '카페라떼', '바닐라라떼', '레몬에이드', '딸기스무디']
TEMPERATURE_LABELS = ['NONE', 'ICE', 'HOT']
QUANTITY_LABELS = ['NONE'] + [str(v) for v in range(1, 21)]

RESULT_ROOT = Path('kips_2026_results')

@dataclass(frozen=True)
class ExperimentConfig:
    name: str
    architecture: str = 'item_query'
    differential_lr: bool = False
    oversample: bool = False
    weighted_loss: bool = False
    rdrop: bool = False

MAIN_CONFIGS = [
    ExperimentConfig('M0_independent_heads', architecture='independent'),
    ExperimentConfig('M1_item_query'),
    ExperimentConfig(
        'M2_improved_item_query',
        differential_lr=True,
        oversample=True,
        weighted_loss=True,
    ),
]

ABLATION_CONFIGS = [
    ExperimentConfig('M1_item_query'),
    ExperimentConfig('A1_plus_diff_lr', differential_lr=True),
    ExperimentConfig('A2_plus_oversampling', differential_lr=True, oversample=True),
    ExperimentConfig(
        'M2_improved_item_query',
        differential_lr=True,
        oversample=True,
        weighted_loss=True,
    ),
]

RDROP_CONFIG = ExperimentConfig(
    'A4_plus_rdrop',
    differential_lr=True,
    oversample=True,
    weighted_loss=True,
    rdrop=True,
)
