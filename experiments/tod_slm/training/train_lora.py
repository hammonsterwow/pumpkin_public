#!/usr/bin/env python3
"""Train the Pumpkin Qwen3-0.6B Student with assistant-only LoRA SFT."""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
import transformers
import yaml
from peft import LoraConfig, get_peft_model
from torch.utils.data import Dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    Trainer,
    TrainingArguments,
    set_seed,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]


def load_yaml(path: Path) -> dict[str, Any]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid YAML config: {path}")
    return value


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


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


def dtype_from_name(name: str):
    normalized = str(name).lower()
    if normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if normalized in {"fp16", "float16", "half"}:
        return torch.float16
    if normalized in {"fp32", "float32", "float"}:
        return torch.float32
    raise ValueError(f"unsupported dtype: {name}")


def apply_template(tokenizer, messages, *, add_generation_prompt: bool, enable_thinking: bool):
    return tokenizer.apply_chat_template(
        messages,
        tokenize=True,
        add_generation_prompt=add_generation_prompt,
        enable_thinking=enable_thinking,
    )


class PumpkinChatDataset(Dataset):
    """Pre-tokenized dataset with loss only on the assistant answer."""

    def __init__(
        self,
        path: Path,
        tokenizer,
        *,
        max_length: int,
        enable_thinking: bool,
        overlength_policy: str,
    ) -> None:
        self.samples: list[dict[str, Any]] = []
        dropped: list[dict[str, Any]] = []
        overlength: list[dict[str, Any]] = []

        for row in iter_jsonl(path):
            sample_id = str(row.get("id") or "")
            messages = row.get("messages")
            if not isinstance(messages, list) or len(messages) != 3:
                raise ValueError(f"{sample_id}: expected system/user/assistant messages")
            if [m.get("role") for m in messages] != ["system", "user", "assistant"]:
                raise ValueError(f"{sample_id}: invalid role order")

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
                    f"{sample_id}: prompt tokens are not a prefix of the full chat template"
                )

            if len(full_ids) > max_length:
                record = {"id": sample_id, "tokens": len(full_ids)}
                overlength.append(record)
                if overlength_policy == "drop":
                    dropped.append(record)
                    continue
                if overlength_policy == "error":
                    continue
                raise ValueError(f"unsupported overlength_policy: {overlength_policy}")

            labels = [-100] * len(prompt_ids) + full_ids[len(prompt_ids) :]
            if not any(label != -100 for label in labels):
                raise ValueError(f"{sample_id}: assistant target has no supervised tokens")

            self.samples.append(
                {
                    "id": sample_id,
                    "input_ids": full_ids,
                    "attention_mask": [1] * len(full_ids),
                    "labels": labels,
                }
            )

        if overlength and overlength_policy == "error":
            preview = json.dumps(overlength[:10], ensure_ascii=False)
            raise ValueError(
                f"{len(overlength)} samples exceed max_length={max_length}. "
                f"Run inspect_token_lengths.py first. Examples: {preview}"
            )
        if not self.samples:
            raise ValueError(f"no usable samples loaded from {path}")
        if dropped:
            print(f"warning: dropped {len(dropped)} overlength samples from {path}")

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.samples[index]


@dataclass
class AssistantOnlyCollator:
    pad_token_id: int

    def __call__(self, features: list[dict[str, Any]]) -> dict[str, torch.Tensor]:
        max_len = max(len(feature["input_ids"]) for feature in features)
        batch_size = len(features)
        input_ids = torch.full(
            (batch_size, max_len), self.pad_token_id, dtype=torch.long
        )
        attention_mask = torch.zeros((batch_size, max_len), dtype=torch.long)
        labels = torch.full((batch_size, max_len), -100, dtype=torch.long)

        for row_index, feature in enumerate(features):
            length = len(feature["input_ids"])
            input_ids[row_index, :length] = torch.tensor(feature["input_ids"], dtype=torch.long)
            attention_mask[row_index, :length] = 1
            labels[row_index, :length] = torch.tensor(feature["labels"], dtype=torch.long)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "labels": labels,
        }


def git_commit() -> str | None:
    if not (PROJECT_ROOT / ".git").exists():
        return None
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return None


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def save_run_metadata(output_root: Path, config_path: Path, config: dict[str, Any]) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "run_config.yaml").write_text(
        yaml.safe_dump(config, sort_keys=False, allow_unicode=True), encoding="utf-8"
    )
    commit = git_commit()
    (output_root / "git_commit.txt").write_text((commit or "unknown") + "\n", encoding="utf-8")
    metadata = {
        "config_source": str(config_path),
        "git_commit": commit,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda_available": torch.cuda.is_available(),
        "cuda_version": torch.version.cuda,
        "gpu_count": torch.cuda.device_count(),
        "gpu_names": [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
        "world_size": int(os.environ.get("WORLD_SIZE", "1")),
    }
    write_json(output_root / "run_metadata.json", metadata)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT
        / "experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml",
    )
    parser.add_argument("--resume-from-checkpoint", type=str, default=None)
    args = parser.parse_args()

    config_path = args.config.resolve()
    config = load_yaml(config_path)
    exp_cfg = config["experiment"]
    model_cfg = config["model"]
    data_cfg = config["data"]
    lora_cfg = config["lora"]
    train_cfg = config["training"]
    output_cfg = config["output"]

    set_seed(int(exp_cfg.get("seed", 42)))
    output_root = resolve_project_path(output_cfg["root_dir"])
    checkpoint_dir = output_root / "checkpoints"
    logs_dir = output_root / "logs" / "tensorboard"
    best_adapter_dir = output_root / "best_adapter"
    evaluation_dir = output_root / "evaluation"
    for path in (checkpoint_dir, logs_dir, evaluation_dir):
        path.mkdir(parents=True, exist_ok=True)
    save_run_metadata(output_root, config_path, config)

    if not torch.cuda.is_available():
        print("warning: CUDA is not available. This baseline is intended for a GPU training server.")

    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["name_or_path"],
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
    )
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "right"

    model = AutoModelForCausalLM.from_pretrained(
        model_cfg["name_or_path"],
        torch_dtype=dtype_from_name(model_cfg.get("dtype", "bfloat16")),
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
    )
    model.config.use_cache = bool(model_cfg.get("use_cache", False))

    if bool(train_cfg.get("gradient_checkpointing", True)):
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
        model.enable_input_require_grads()

    peft_config = LoraConfig(
        r=int(lora_cfg["r"]),
        lora_alpha=int(lora_cfg["alpha"]),
        lora_dropout=float(lora_cfg.get("dropout", 0.0)),
        bias=str(lora_cfg.get("bias", "none")),
        target_modules=list(lora_cfg["target_modules"]),
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()

    dataset_kwargs = {
        "tokenizer": tokenizer,
        "max_length": int(data_cfg["max_length"]),
        "enable_thinking": bool(data_cfg.get("enable_thinking", False)),
        "overlength_policy": str(data_cfg.get("overlength_policy", "error")),
    }
    train_dataset = PumpkinChatDataset(
        resolve_project_path(data_cfg["train_file"]), **dataset_kwargs
    )
    validation_dataset = PumpkinChatDataset(
        resolve_project_path(data_cfg["validation_file"]), **dataset_kwargs
    )

    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    effective_batch = (
        int(train_cfg["per_device_train_batch_size"])
        * int(train_cfg["gradient_accumulation_steps"])
        * world_size
    )
    print(
        f"Train rows={len(train_dataset):,}, Validation rows={len(validation_dataset):,}, "
        f"WORLD_SIZE={world_size}, effective batch={effective_batch}"
    )

    training_args = TrainingArguments(
        output_dir=str(checkpoint_dir),
        overwrite_output_dir=False,
        num_train_epochs=float(train_cfg["epochs"]),
        per_device_train_batch_size=int(train_cfg["per_device_train_batch_size"]),
        per_device_eval_batch_size=int(train_cfg["per_device_eval_batch_size"]),
        gradient_accumulation_steps=int(train_cfg["gradient_accumulation_steps"]),
        learning_rate=float(train_cfg["learning_rate"]),
        weight_decay=float(train_cfg["weight_decay"]),
        warmup_ratio=float(train_cfg["warmup_ratio"]),
        lr_scheduler_type=str(train_cfg["lr_scheduler_type"]),
        max_grad_norm=float(train_cfg["max_grad_norm"]),
        bf16=bool(train_cfg.get("bf16", True)),
        fp16=bool(train_cfg.get("fp16", False)),
        gradient_checkpointing=bool(train_cfg.get("gradient_checkpointing", True)),
        gradient_checkpointing_kwargs={"use_reentrant": False},
        logging_strategy="steps",
        logging_steps=int(train_cfg["logging_steps"]),
        eval_strategy="steps",
        eval_steps=int(train_cfg["eval_steps"]),
        save_strategy="steps",
        save_steps=int(train_cfg["save_steps"]),
        save_total_limit=int(train_cfg["save_total_limit"]),
        load_best_model_at_end=bool(train_cfg["load_best_model_at_end"]),
        metric_for_best_model=str(train_cfg["metric_for_best_model"]),
        greater_is_better=bool(train_cfg["greater_is_better"]),
        report_to=list(train_cfg.get("report_to") or []),
        logging_dir=str(logs_dir),
        remove_unused_columns=False,
        ddp_find_unused_parameters=False,
        seed=int(exp_cfg.get("seed", 42)),
        data_seed=int(exp_cfg.get("seed", 42)),
        optim="adamw_torch",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=validation_dataset,
        data_collator=AssistantOnlyCollator(tokenizer.pad_token_id),
        processing_class=tokenizer,
    )

    train_result = trainer.train(resume_from_checkpoint=args.resume_from_checkpoint)
    trainer.save_state()
    write_json(evaluation_dir / "train_metrics.json", train_result.metrics)

    validation_metrics = trainer.evaluate(eval_dataset=validation_dataset)
    write_json(evaluation_dir / "validation_loss_metrics.json", validation_metrics)

    # load_best_model_at_end=True means the Trainer now holds the selected best
    # checkpoint. Save that adapter separately from rotating intermediate checkpoints.
    best_adapter_dir.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(best_adapter_dir))
    tokenizer.save_pretrained(str(best_adapter_dir))

    summary = {
        "experiment": exp_cfg["name"],
        "best_model_checkpoint": trainer.state.best_model_checkpoint,
        "best_metric": trainer.state.best_metric,
        "best_adapter": str(best_adapter_dir),
        "train_rows": len(train_dataset),
        "validation_rows": len(validation_dataset),
        "effective_batch_size": effective_batch,
        "test_was_used_during_training": False,
    }
    write_json(output_root / "training_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
