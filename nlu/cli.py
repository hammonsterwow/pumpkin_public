"""Command-line smoke test for the production NLU predictor."""

from __future__ import annotations

import argparse
import json

from .config import DEFAULT_CONFIDENCE_THRESHOLD, DEFAULT_MODEL_DIR
from .predictor import StructureBNLUPredictor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Structure B item-query decoder NLU inference.",
    )
    parser.add_argument("text", nargs="?", help="STT text to analyze.")
    parser.add_argument("--model-dir", default=str(DEFAULT_MODEL_DIR))
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD,
    )
    parser.add_argument("--device", choices=["auto", "cpu", "cuda"], default="auto")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    predictor = StructureBNLUPredictor(
        model_dir=args.model_dir,
        device=args.device,
    )
    text = args.text or input("분석할 문장을 입력하세요: ").strip()
    result = predictor.predict(text, args.confidence_threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
