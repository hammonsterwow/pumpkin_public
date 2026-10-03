"""Measure hierarchical multi-task NLU latency on the current device.

Usage:
    python -m nlu.benchmark_multitask --runs 50 --warmup 10
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

import torch

from .predict_multitask import DEFAULT_MODEL_DIR, HierarchicalNLUPredictor

DEFAULT_TEXTS = [
    "아이스 아메리카노 한 잔 주세요",
    "따뜻한 카페라떼 두 잔 주문할게요",
    "결제는 어디서 하나요",
    "방금 주문 취소해 주세요",
]


def synchronize() -> None:
    if torch.cuda.is_available():
        torch.cuda.synchronize()


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Benchmark multi-task NLU inference latency.")
    parser.add_argument("--model-dir", default=DEFAULT_MODEL_DIR)
    parser.add_argument("--runs", type=int, default=50)
    parser.add_argument("--warmup", type=int, default=10)
    parser.add_argument("--device", choices=["cpu", "cuda"], default=None)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.runs < 1 or args.warmup < 0:
        raise ValueError("runs는 1 이상, warmup은 0 이상이어야 합니다.")

    predictor = HierarchicalNLUPredictor(args.model_dir, device=args.device)

    for index in range(args.warmup):
        predictor.predict(DEFAULT_TEXTS[index % len(DEFAULT_TEXTS)])
    synchronize()

    latencies_ms: list[float] = []
    last_result = None
    for index in range(args.runs):
        text = DEFAULT_TEXTS[index % len(DEFAULT_TEXTS)]
        synchronize()
        started = time.perf_counter()
        last_result = predictor.predict(text)
        synchronize()
        latencies_ms.append((time.perf_counter() - started) * 1000.0)

    report = {
        "device": predictor.device,
        "runs": args.runs,
        "warmup": args.warmup,
        "mean_ms": round(statistics.fmean(latencies_ms), 3),
        "median_ms": round(statistics.median(latencies_ms), 3),
        "p95_ms": round(percentile(latencies_ms, 0.95), 3),
        "min_ms": round(min(latencies_ms), 3),
        "max_ms": round(max(latencies_ms), 3),
        "last_result": last_result,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
