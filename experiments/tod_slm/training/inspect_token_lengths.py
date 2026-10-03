#!/usr/bin/env python3
"""Inspect Qwen chat token lengths before starting LoRA training.

This script never changes the dataset. It applies the same non-thinking Qwen
chat template used by train_lora.py and reports prompt/full/assistant token
length percentiles. The training config intentionally uses overlength_policy=
"error" so an unsafe max_length is discovered before a long training run.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import yaml
from transformers import AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield value


def percentile(values: list[int], q: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(q * len(ordered)) - 1))
    return ordered[index]


def summarize(values: list[int]) -> dict[str, int]:
    return {
        "min": min(values) if values else 0,
        "p50": percentile(values, 0.50),
        "p90": percentile(values, 0.90),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": max(values) if values else 0,
    }


def apply_template(tokenizer, messages, *, add_generation_prompt: bool, enable_thinking: bool):
    kwargs = {
        "tokenize": True,
        "add_generation_prompt": add_generation_prompt,
    }
    # Qwen3 supports enable_thinking. Keeping it explicit protects the Pumpkin
    # baseline from accidentally learning/producing hidden reasoning blocks.
    kwargs["enable_thinking"] = enable_thinking
    return tokenizer.apply_chat_template(messages, **kwargs)


def inspect_split(tokenizer, path: Path, enable_thinking: bool) -> dict[str, Any]:
    full_lengths: list[int] = []
    prompt_lengths: list[int] = []
    assistant_lengths: list[int] = []
    longest: list[tuple[int, str]] = []

    for row in iter_jsonl(path):
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) != 3:
            raise ValueError(f"{row.get('id')}: expected three messages")
        full_ids = apply_template(
            tokenizer,
            messages,
            add_generation_prompt=False,
            enable_thinking=enable_thinking,
        )
        prompt_ids = apply_template(
            tokenizer,
            messages[:-1],
            add_generation_prompt=True,
            enable_thinking=enable_thinking,
        )
        if full_ids[: len(prompt_ids)] != prompt_ids:
            raise ValueError(
                f"{row.get('id')}: Qwen chat template prompt is not a prefix of full conversation"
            )
        full_len = len(full_ids)
        prompt_len = len(prompt_ids)
        assistant_len = full_len - prompt_len
        full_lengths.append(full_len)
        prompt_lengths.append(prompt_len)
        assistant_lengths.append(assistant_len)
        longest.append((full_len, str(row.get("id") or "")))

    longest.sort(reverse=True)
    return {
        "rows": len(full_lengths),
        "full": summarize(full_lengths),
        "prompt": summarize(prompt_lengths),
        "assistant": summarize(assistant_lengths),
        "longest_examples": [
            {"id": sample_id, "tokens": length}
            for length, sample_id in longest[:10]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT
        / "experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml",
    )
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    config = load_yaml(args.config.resolve())
    model_cfg = config["model"]
    data_cfg = config["data"]
    output_cfg = config["output"]

    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["name_or_path"],
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
    )
    enable_thinking = bool(data_cfg.get("enable_thinking", False))

    results: dict[str, Any] = {
        "model": model_cfg["name_or_path"],
        "enable_thinking": enable_thinking,
        "configured_max_length": int(data_cfg["max_length"]),
        "splits": {},
    }
    for split, key in (
        ("train", "train_file"),
        ("validation", "validation_file"),
        ("test", "test_file"),
    ):
        path = (PROJECT_ROOT / data_cfg[key]).resolve()
        results["splits"][split] = inspect_split(tokenizer, path, enable_thinking)

    max_seen = max(part["full"]["max"] for part in results["splits"].values())
    results["max_seen"] = max_seen
    results["configured_max_length_is_safe"] = max_seen <= int(data_cfg["max_length"])
    p99 = max(part["full"]["p99"] for part in results["splits"].values())
    results["p99_across_splits"] = p99
    results["recommended_multiple_of_128_at_or_above_p99"] = int(math.ceil(p99 / 128) * 128)

    output = args.output
    if output is None:
        output = PROJECT_ROOT / output_cfg["root_dir"] / "preflight/token_lengths.json"
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(results, ensure_ascii=False, indent=2))
    print(f"\nSaved: {output}")
    if not results["configured_max_length_is_safe"]:
        raise SystemExit(
            f"configured max_length={data_cfg['max_length']} is shorter than max sample={max_seen}; "
            "inspect the report before training"
        )


if __name__ == "__main__":
    main()
