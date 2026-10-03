#!/usr/bin/env python3
"""Analyze Pumpkin TOD generation errors without re-running inference.

Reads evaluate.py's *_predictions.jsonl and joins it to the original Qwen split by
row id. The report focuses on actionable Student-v2 error families: slot
hallucination, missing-slot handling, decision errors, state errors, and
single-vs-multi-item behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SLOTS = ("menu", "temperature", "quantity")


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


def canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def parse_json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_user_payload(row: dict[str, Any]) -> dict[str, Any]:
    messages = row.get("messages")
    if not isinstance(messages, list) or len(messages) < 2:
        return {}
    user = messages[1]
    if not isinstance(user, dict):
        return {}
    return parse_json_object(user.get("content"))


def state_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, dict):
        return []
    items = value.get("items")
    if not isinstance(items, list):
        return []
    return [item if isinstance(item, dict) else {} for item in items]


def utterance_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item if isinstance(item, dict) else {} for item in value]
    if isinstance(value, dict):
        items = value.get("items")
        if isinstance(items, list):
            return [item if isinstance(item, dict) else {} for item in items]
        # Be tolerant of a single item encoded directly as a dict.
        if any(slot in value for slot in SLOTS):
            return [value]
    return []


def missing_state_slots(state: Any) -> tuple[str, ...]:
    items = state_items(state)
    if not items:
        return ("no_items",)
    missing: set[str] = set()
    for item in items:
        for slot in SLOTS:
            if item.get(slot) is None:
                missing.add(slot)
    return tuple(sorted(missing)) if missing else ("none",)


def item_bucket(state: Any) -> str:
    count = len(state_items(state))
    if count <= 0:
        return "0_items"
    if count == 1:
        return "single_item"
    return "multi_item"


def hallucinated_slots(gold_value: Any, pred_value: Any) -> list[dict[str, Any]]:
    gold = utterance_items(gold_value)
    pred = utterance_items(pred_value)
    result: list[dict[str, Any]] = []
    for index in range(max(len(gold), len(pred))):
        gold_item = gold[index] if index < len(gold) else {}
        pred_item = pred[index] if index < len(pred) else {}
        for slot in SLOTS:
            gold_value = gold_item.get(slot)
            pred_value = pred_item.get(slot)
            if gold_value is None and pred_value is not None:
                result.append({"item_index": index, "slot": slot, "predicted": pred_value})
    return result


def pct(num: int, den: int) -> float:
    return round(100.0 * num / den, 2) if den else 0.0


def counter_table(counter: Counter[str], denominator: int | None = None) -> list[dict[str, Any]]:
    total = denominator if denominator is not None else sum(counter.values())
    return [
        {"key": key, "count": count, "pct": pct(count, total)}
        for key, count in counter.most_common()
    ]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--predictions",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/tod_slm/qwen3_0.6b_lora_v1/evaluation/test_predictions.jsonl",
    )
    parser.add_argument(
        "--test-file",
        type=Path,
        default=PROJECT_ROOT / "data/tod/qwen/pumpkin_tod_v1_qwen_test.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT
        / "outputs/tod_slm/qwen3_0.6b_lora_v1/evaluation/error_analysis",
    )
    parser.add_argument("--examples-per-group", type=int, default=8)
    args = parser.parse_args()

    predictions_path = args.predictions.resolve()
    test_path = args.test_file.resolve()
    output_dir = args.output_dir.resolve()

    if not predictions_path.exists():
        raise FileNotFoundError(f"predictions not found: {predictions_path}")
    if not test_path.exists():
        raise FileNotFoundError(f"test file not found: {test_path}")

    source_by_id = {str(row.get("id")): row for row in iter_jsonl(test_path)}
    records = list(iter_jsonl(predictions_path))

    total = len(records)
    invalid_json = 0
    any_error = 0
    hallucination_rows = 0
    hallucinated_slot_total = 0

    field_names = (
        "intent",
        "order_status",
        "decision",
        "response_key",
        "fsm_state_after",
        "state_after",
        "utterance_items",
        "response",
    )
    field_errors: Counter[str] = Counter()
    decision_confusion: Counter[str] = Counter()
    intent_confusion: Counter[str] = Counter()
    hallucination_by_slot: Counter[str] = Counter()
    hallucination_by_decision: Counter[str] = Counter()
    hallucination_by_intent: Counter[str] = Counter()
    hallucination_by_item_bucket: Counter[str] = Counter()
    hallucination_by_missing_slots: Counter[str] = Counter()
    error_by_decision: Counter[str] = Counter()
    error_by_intent: Counter[str] = Counter()
    error_by_item_bucket: Counter[str] = Counter()
    total_by_decision: Counter[str] = Counter()
    total_by_intent: Counter[str] = Counter()
    total_by_item_bucket: Counter[str] = Counter()

    examples: list[dict[str, Any]] = []
    group_examples: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for record in records:
        row_id = str(record.get("id"))
        source = source_by_id.get(row_id, {})
        user_payload = extract_user_payload(source)
        user_text = user_payload.get("user_text")

        gold = record.get("gold")
        pred = record.get("prediction_json")
        if not isinstance(gold, dict):
            continue

        gold_decision = str(gold.get("decision"))
        gold_intent = str(gold.get("intent"))
        bucket = item_bucket(gold.get("state_after"))
        missing_slots = "+".join(missing_state_slots(gold.get("state_after")))

        total_by_decision[gold_decision] += 1
        total_by_intent[gold_intent] += 1
        total_by_item_bucket[bucket] += 1

        row_field_errors: list[str] = []
        if not isinstance(pred, dict):
            invalid_json += 1
            row_field_errors = list(field_names)
            for field in field_names:
                field_errors[field] += 1
            decision_confusion[f"{gold_decision} -> INVALID_JSON"] += 1
            intent_confusion[f"{gold_intent} -> INVALID_JSON"] += 1
            hallucinations: list[dict[str, Any]] = []
        else:
            for field in field_names:
                if canonical(pred.get(field)) != canonical(gold.get(field)):
                    row_field_errors.append(field)
                    field_errors[field] += 1
            if pred.get("decision") != gold.get("decision"):
                decision_confusion[
                    f"{gold_decision} -> {pred.get('decision')}"
                ] += 1
            if pred.get("intent") != gold.get("intent"):
                intent_confusion[f"{gold_intent} -> {pred.get('intent')}"] += 1
            hallucinations = hallucinated_slots(
                gold.get("utterance_items"), pred.get("utterance_items")
            )

        if row_field_errors:
            any_error += 1
            error_by_decision[gold_decision] += 1
            error_by_intent[gold_intent] += 1
            error_by_item_bucket[bucket] += 1

        if hallucinations:
            hallucination_rows += 1
            hallucinated_slot_total += len(hallucinations)
            hallucination_by_decision[gold_decision] += 1
            hallucination_by_intent[gold_intent] += 1
            hallucination_by_item_bucket[bucket] += 1
            hallucination_by_missing_slots[missing_slots] += 1
            for item in hallucinations:
                hallucination_by_slot[item["slot"]] += 1

        if row_field_errors or hallucinations:
            example = {
                "id": row_id,
                "user_text": user_text,
                "gold_intent": gold.get("intent"),
                "pred_intent": pred.get("intent") if isinstance(pred, dict) else None,
                "gold_decision": gold.get("decision"),
                "pred_decision": pred.get("decision") if isinstance(pred, dict) else None,
                "item_bucket": bucket,
                "missing_state_slots": missing_slots,
                "field_errors": row_field_errors,
                "hallucinations": hallucinations,
                "gold_utterance_items": gold.get("utterance_items"),
                "pred_utterance_items": pred.get("utterance_items") if isinstance(pred, dict) else None,
                "gold_state_after": gold.get("state_after"),
                "pred_state_after": pred.get("state_after") if isinstance(pred, dict) else None,
                "gold_response": gold.get("response"),
                "pred_response": pred.get("response") if isinstance(pred, dict) else None,
            }
            examples.append(example)
            if hallucinations:
                for h in hallucinations:
                    key = f"hallucination::{h['slot']}::{gold_decision}"
                    if len(group_examples[key]) < args.examples_per_group:
                        group_examples[key].append(example)
            if "decision" in row_field_errors:
                key = f"decision::{gold_decision}"
                if len(group_examples[key]) < args.examples_per_group:
                    group_examples[key].append(example)

    decision_error_rates = []
    for key, den in total_by_decision.items():
        num = error_by_decision[key]
        decision_error_rates.append(
            {"key": key, "errors": num, "total": den, "error_rate_pct": pct(num, den)}
        )
    decision_error_rates.sort(key=lambda x: (-x["error_rate_pct"], -x["errors"], x["key"]))

    intent_error_rates = []
    for key, den in total_by_intent.items():
        num = error_by_intent[key]
        intent_error_rates.append(
            {"key": key, "errors": num, "total": den, "error_rate_pct": pct(num, den)}
        )
    intent_error_rates.sort(key=lambda x: (-x["error_rate_pct"], -x["errors"], x["key"]))

    item_error_rates = []
    for key, den in total_by_item_bucket.items():
        num = error_by_item_bucket[key]
        item_error_rates.append(
            {"key": key, "errors": num, "total": den, "error_rate_pct": pct(num, den)}
        )
    item_error_rates.sort(key=lambda x: (-x["error_rate_pct"], -x["errors"], x["key"]))

    report = {
        "total_rows": total,
        "invalid_json_rows": invalid_json,
        "rows_with_any_exact_match_error": any_error,
        "rows_with_any_exact_match_error_rate": round(any_error / total, 6) if total else 0.0,
        "hallucination_rows": hallucination_rows,
        "hallucination_row_rate": round(hallucination_rows / total, 6) if total else 0.0,
        "hallucinated_slot_total": hallucinated_slot_total,
        "field_error_counts": counter_table(field_errors, total),
        "decision_error_rates": decision_error_rates,
        "intent_error_rates": intent_error_rates,
        "item_error_rates": item_error_rates,
        "decision_confusions": counter_table(decision_confusion),
        "intent_confusions": counter_table(intent_confusion),
        "hallucination_by_slot": counter_table(hallucination_by_slot, hallucinated_slot_total),
        "hallucination_rows_by_gold_decision": counter_table(hallucination_by_decision, hallucination_rows),
        "hallucination_rows_by_gold_intent": counter_table(hallucination_by_intent, hallucination_rows),
        "hallucination_rows_by_item_bucket": counter_table(hallucination_by_item_bucket, hallucination_rows),
        "hallucination_rows_by_missing_state_slots": counter_table(hallucination_by_missing_slots, hallucination_rows),
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "test_error_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    examples_path = output_dir / "test_error_examples.jsonl"
    with examples_path.open("w", encoding="utf-8") as handle:
        for example in examples:
            handle.write(json.dumps(example, ensure_ascii=False, separators=(",", ":")) + "\n")

    grouped_path = output_dir / "test_grouped_examples.json"
    grouped_path.write_text(
        json.dumps(group_examples, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    csv_path = output_dir / "test_error_examples.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "user_text",
                "gold_intent",
                "pred_intent",
                "gold_decision",
                "pred_decision",
                "item_bucket",
                "missing_state_slots",
                "field_errors",
                "hallucinations",
            ],
        )
        writer.writeheader()
        for example in examples:
            writer.writerow(
                {
                    "id": example["id"],
                    "user_text": example["user_text"],
                    "gold_intent": example["gold_intent"],
                    "pred_intent": example["pred_intent"],
                    "gold_decision": example["gold_decision"],
                    "pred_decision": example["pred_decision"],
                    "item_bucket": example["item_bucket"],
                    "missing_state_slots": example["missing_state_slots"],
                    "field_errors": ",".join(example["field_errors"]),
                    "hallucinations": json.dumps(example["hallucinations"], ensure_ascii=False),
                }
            )

    print("=== Pumpkin TOD Student v1: Test Error Analysis ===")
    print(f"rows: {total:,}")
    print(f"invalid JSON rows: {invalid_json:,}")
    print(f"rows with any exact-match error: {any_error:,} ({pct(any_error, total):.2f}%)")
    print(
        f"rows with slot hallucination: {hallucination_rows:,} "
        f"({pct(hallucination_rows, total):.2f}%)"
    )
    print(f"hallucinated slot assignments: {hallucinated_slot_total:,}")

    print("\n[Hallucinated slots]")
    for row in report["hallucination_by_slot"]:
        print(f"  {row['key']}: {row['count']} ({row['pct']:.2f}%)")

    print("\n[Hallucination rows by gold decision]")
    for row in report["hallucination_rows_by_gold_decision"][:10]:
        print(f"  {row['key']}: {row['count']} ({row['pct']:.2f}%)")

    print("\n[Highest decision-family error rates]")
    for row in decision_error_rates[:10]:
        print(
            f"  {row['key']}: {row['errors']}/{row['total']} "
            f"({row['error_rate_pct']:.2f}%)"
        )

    print("\n[Top decision confusions]")
    for row in report["decision_confusions"][:12]:
        print(f"  {row['key']}: {row['count']}")

    print(f"\nreport: {report_path}")
    print(f"examples JSONL: {examples_path}")
    print(f"examples CSV: {csv_path}")
    print(f"grouped examples: {grouped_path}")


if __name__ == "__main__":
    main()
