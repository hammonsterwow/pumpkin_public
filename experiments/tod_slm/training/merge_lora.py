#!/usr/bin/env python3
"""Merge the selected Pumpkin LoRA adapter into Qwen3-0.6B for deployment/export."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import torch
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def dtype_from_name(name: str):
    normalized = str(name).lower()
    if normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if normalized in {"fp16", "float16", "half"}:
        return torch.float16
    return torch.float32


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT
        / "experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml",
    )
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    config = load_yaml(args.config.resolve())
    model_cfg = config["model"]
    output_root = resolve_project_path(config["output"]["root_dir"])
    adapter = args.adapter.resolve() if args.adapter else output_root / "best_adapter"
    output = args.output.resolve() if args.output else output_root / "merged_model"

    if not adapter.exists():
        raise FileNotFoundError(f"adapter not found: {adapter}")

    tokenizer = AutoTokenizer.from_pretrained(adapter)
    base_model = AutoModelForCausalLM.from_pretrained(
        model_cfg["name_or_path"],
        torch_dtype=dtype_from_name(model_cfg.get("dtype", "bfloat16")),
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
    )
    peft_model = PeftModel.from_pretrained(base_model, adapter)
    merged = peft_model.merge_and_unload()

    output.mkdir(parents=True, exist_ok=True)
    merged.save_pretrained(output, safe_serialization=True)
    tokenizer.save_pretrained(output)
    print(f"Merged model saved to: {output}")
    print("This directory is intentionally git-ignored; keep large deployment artifacts outside Git.")


if __name__ == "__main__":
    main()
