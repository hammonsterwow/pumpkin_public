#!/usr/bin/env python3
"""Generate Pumpkin TOD predictions and compute structured-task metrics.

Validation is the default split. Test must be requested explicitly after model
selection so the fixed 1,507-row test set is not used for tuning.

Multi-GPU evaluation is supported with ``accelerate launch --multi_gpu``.
Each rank loads one model replica on its local GPU, evaluates a disjoint shard,
and rank 0 merges the prediction parts before computing final metrics.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

import torch
import torch.distributed as dist
import yaml
from peft import PeftModel
from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SLOTS = ("menu", "temperature", "quantity")


def load_yaml(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def resolve_project_path(value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (PROJECT_ROOT / path).resolve()


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


def dtype_from_name(name: str):
    normalized = str(name).lower()
    if normalized in {"bf16", "bfloat16"}:
        return torch.bfloat16
    if normalized in {"fp16", "float16", "half"}:
        return torch.float16
    return torch.float32


def strict_json(text: str) -> dict[str, Any] | None:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def slot_set(state: Any) -> set[tuple[int, str, str]]:
    if not isinstance(state, dict):
        return set()
    items = state.get("items")
    if not isinstance(items, list):
        return set()
    result: set[tuple[int, str, str]] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_id = (
            int(item.get("item_id", index))
            if str(item.get("item_id", index)).isdigit()
            else index
        )
        for slot in SLOTS:
            value = item.get(slot)
            if value is not None:
                result.add((item_id, slot, canonical(value)))
    return result


def hallucination_counts(gold_items: Any, pred_items: Any) -> tuple[int, int]:
    gold = gold_items if isinstance(gold_items, list) else []
    pred = pred_items if isinstance(pred_items, list) else []
    opportunities = 0
    hallucinations = 0
    max_items = max(len(gold), len(pred))
    for index in range(max_items):
        gold_item = (
            gold[index] if index < len(gold) and isinstance(gold[index], dict) else {}
        )
        pred_item = (
            pred[index] if index < len(pred) and isinstance(pred[index], dict) else {}
        )
        for slot in SLOTS:
            if gold_item.get(slot) is None:
                opportunities += 1
                if pred_item.get(slot) is not None:
                    hallucinations += 1
    return hallucinations, opportunities


def safe_div(num: float, den: float) -> float:
    return num / den if den else 0.0


def evaluate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    valid_json = 0
    fields = {
        "intent": 0,
        "order_status": 0,
        "decision": 0,
        "response_key": 0,
        "fsm_state_after": 0,
        "response": 0,
    }
    state_exact = 0
    utterance_exact = 0
    slot_tp = slot_pred = slot_gold = 0
    hallucinations = hallucination_opportunities = 0

    for record in records:
        gold = record["gold"]
        pred = record.get("prediction_json")
        if not isinstance(pred, dict):
            continue
        valid_json += 1
        for field in fields:
            if pred.get(field) == gold.get(field):
                fields[field] += 1
        if canonical(pred.get("state_after")) == canonical(gold.get("state_after")):
            state_exact += 1
        if canonical(pred.get("utterance_items")) == canonical(gold.get("utterance_items")):
            utterance_exact += 1

        gold_slots = slot_set(gold.get("state_after"))
        pred_slots = slot_set(pred.get("state_after"))
        slot_tp += len(gold_slots & pred_slots)
        slot_pred += len(pred_slots)
        slot_gold += len(gold_slots)

        h, opportunities = hallucination_counts(
            gold.get("utterance_items"), pred.get("utterance_items")
        )
        hallucinations += h
        hallucination_opportunities += opportunities

    precision = safe_div(slot_tp, slot_pred)
    recall = safe_div(slot_tp, slot_gold)
    slot_f1 = safe_div(2 * precision * recall, precision + recall)

    return {
        "rows": total,
        "json_valid_rate": safe_div(valid_json, total),
        "intent_accuracy": safe_div(fields["intent"], total),
        "order_status_accuracy": safe_div(fields["order_status"], total),
        "decision_accuracy": safe_div(fields["decision"], total),
        "response_key_accuracy": safe_div(fields["response_key"], total),
        "fsm_state_after_accuracy": safe_div(fields["fsm_state_after"], total),
        "state_exact_match": safe_div(state_exact, total),
        "utterance_items_exact_match": safe_div(utterance_exact, total),
        "state_slot_precision": precision,
        "state_slot_recall": recall,
        "state_slot_f1": slot_f1,
        "hallucinated_slot_count": hallucinations,
        "hallucinated_slot_opportunities": hallucination_opportunities,
        "hallucinated_slot_rate": safe_div(hallucinations, hallucination_opportunities),
        "response_exact_match": safe_div(fields["response"], total),
    }


def batched(values: list[Any], size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]


def distributed_context() -> tuple[int, int, int]:
    world_size = int(os.environ.get("WORLD_SIZE", "1"))
    rank = int(os.environ.get("RANK", "0"))
    local_rank = int(os.environ.get("LOCAL_RANK", "0"))
    if world_size > 1:
        if not torch.cuda.is_available():
            raise RuntimeError("multi-GPU evaluation requires CUDA")
        torch.cuda.set_device(local_rank)
        if not dist.is_initialized():
            dist.init_process_group(backend="nccl")
    return world_size, rank, local_rank


def barrier(world_size: int) -> None:
    if world_size > 1:
        dist.barrier()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=PROJECT_ROOT
        / "experiments/tod_slm/training/configs/qwen3_0.6b_lora_v1.yaml",
    )
    parser.add_argument("--split", choices=("validation", "test"), default="validation")
    parser.add_argument("--adapter", type=Path, default=None)
    parser.add_argument("--max-rows", type=int, default=None)
    args = parser.parse_args()

    world_size, rank, local_rank = distributed_context()

    config = load_yaml(args.config.resolve())
    model_cfg = config["model"]
    data_cfg = config["data"]
    eval_cfg = config["evaluation"]
    output_root = resolve_project_path(config["output"]["root_dir"])
    adapter_path = (
        args.adapter.resolve() if args.adapter else output_root / "best_adapter"
    )
    if not adapter_path.exists():
        raise FileNotFoundError(f"adapter not found: {adapter_path}")

    split_key = "validation_file" if args.split == "validation" else "test_file"
    rows = list(iter_jsonl(resolve_project_path(data_cfg[split_key])))
    if args.max_rows is not None:
        rows = rows[: args.max_rows]

    tokenizer = AutoTokenizer.from_pretrained(adapter_path)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    tokenizer.padding_side = "left"

    if torch.cuda.is_available():
        device = torch.device(f"cuda:{local_rank}")
    else:
        device = torch.device("cpu")

    base_model = AutoModelForCausalLM.from_pretrained(
        model_cfg["name_or_path"],
        torch_dtype=dtype_from_name(model_cfg.get("dtype", "bfloat16")),
        trust_remote_code=bool(model_cfg.get("trust_remote_code", False)),
    )
    model = PeftModel.from_pretrained(base_model, adapter_path)
    model.to(device)
    model.eval()
    model.config.use_cache = True

    prompts: list[dict[str, Any]] = []
    for global_index, row in enumerate(rows):
        if global_index % world_size != rank:
            continue
        messages = row.get("messages")
        if not isinstance(messages, list) or len(messages) != 3:
            raise ValueError(f"{row.get('id')}: invalid messages")
        gold = strict_json(str(messages[2].get("content") or ""))
        if gold is None:
            raise ValueError(f"{row.get('id')}: gold assistant content is not JSON")
        prompt_text = tokenizer.apply_chat_template(
            messages[:2],
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=bool(data_cfg.get("enable_thinking", False)),
        )
        prompts.append(
            {
                "global_index": global_index,
                "id": row.get("id"),
                "prompt": prompt_text,
                "gold": gold,
            }
        )

    batch_size = int(eval_cfg.get("batch_size", 8))
    prediction_records: list[dict[str, Any]] = []
    for batch in batched(prompts, batch_size):
        encoded = tokenizer(
            [entry["prompt"] for entry in batch],
            return_tensors="pt",
            padding=True,
            add_special_tokens=False,
        )
        encoded = {key: value.to(device) for key, value in encoded.items()}
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": int(eval_cfg.get("max_new_tokens", 512)),
            "do_sample": bool(eval_cfg.get("do_sample", False)),
            "pad_token_id": tokenizer.pad_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if generation_kwargs["do_sample"]:
            generation_kwargs["temperature"] = float(eval_cfg.get("temperature", 1.0))
            generation_kwargs["top_p"] = float(eval_cfg.get("top_p", 1.0))

        with torch.inference_mode():
            generated = model.generate(**encoded, **generation_kwargs)
        generated_only = generated[:, encoded["input_ids"].shape[1] :]
        decoded = tokenizer.batch_decode(generated_only, skip_special_tokens=True)

        for entry, text in zip(batch, decoded):
            prediction_records.append(
                {
                    "global_index": entry["global_index"],
                    "id": entry["id"],
                    "gold": entry["gold"],
                    "prediction_text": text.strip(),
                    "prediction_json": strict_json(text),
                }
            )
        print(
            f"[rank {rank}] generated {len(prediction_records):,}/{len(prompts):,} "
            f"(global rows={len(rows):,}, world_size={world_size})",
            flush=True,
        )

    evaluation_dir = output_root / "evaluation"
    parts_dir = evaluation_dir / f".{args.split}_parts"
    evaluation_dir.mkdir(parents=True, exist_ok=True)
    parts_dir.mkdir(parents=True, exist_ok=True)
    part_path = parts_dir / f"rank_{rank:02d}.jsonl"
    with part_path.open("w", encoding="utf-8") as handle:
        for record in prediction_records:
            handle.write(
                json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
            )

    barrier(world_size)

    if rank == 0:
        merged: list[dict[str, Any]] = []
        for part_rank in range(world_size):
            expected = parts_dir / f"rank_{part_rank:02d}.jsonl"
            if not expected.exists():
                raise FileNotFoundError(f"missing evaluation part: {expected}")
            merged.extend(iter_jsonl(expected))
        merged.sort(key=lambda record: int(record["global_index"]))
        if len(merged) != len(rows):
            raise RuntimeError(
                f"merged prediction count mismatch: {len(merged)} != {len(rows)}"
            )
        for record in merged:
            record.pop("global_index", None)

        metrics = evaluate_records(merged)
        predictions_path = evaluation_dir / f"{args.split}_predictions.jsonl"
        with predictions_path.open("w", encoding="utf-8") as handle:
            for record in merged:
                handle.write(
                    json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
                )
        metrics_path = evaluation_dir / f"{args.split}_metrics.json"
        metrics_path.write_text(
            json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )

        for part_path_to_delete in parts_dir.glob("rank_*.jsonl"):
            part_path_to_delete.unlink()
        try:
            parts_dir.rmdir()
        except OSError:
            pass

        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print(f"predictions: {predictions_path}")
        print(f"metrics: {metrics_path}")
        if args.split == "test":
            print(
                "NOTE: fixed test was evaluated. Do not use these results for "
                "hyperparameter tuning."
            )

    barrier(world_size)
    if world_size > 1 and dist.is_initialized():
        dist.destroy_process_group()


if __name__ == "__main__":
    main()
