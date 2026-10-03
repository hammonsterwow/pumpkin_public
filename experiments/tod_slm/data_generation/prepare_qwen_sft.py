#!/usr/bin/env python3
"""Prepare leakage-safe Pumpkin TOD train/validation splits and Qwen chat JSONL.

Input
-----
* data/tod/pumpkin_tod_v1_sft_train_valid.jsonl
* data/tod/pumpkin_tod_v1_sft_test.jsonl

The 28,872 train/valid candidate rows include three deterministic context
variants for each context-dependent canonical source row.  A row-level random
split would leak ctx1/ctx2/ctx3 across train and validation.  This script groups
all rows by canonical source (source.dataset + source.source_index), performs a
deterministic scenario-stratified 90/10 group split, converts each row to a
Qwen messages record, and validates the result.

No third-party package is required and no LLM is used while preparing labels.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
SPLIT_VERSION = "pumpkin_tod_source_group_split_v1"
QWEN_FORMAT_VERSION = "pumpkin_tod_qwen_messages_v1"
DEFAULT_VALIDATION_RATIO = 0.10
DEFAULT_SEED = "pumpkin-tod-v1-source-group-split-2026-09-03"
EXPECTED_TRAIN_VALID_TOTAL = 28_872
EXPECTED_TEST_TOTAL = 1_507

SYSTEM_PROMPT = (
    "당신은 Pumpkin 무인카페 주문 로봇의 Task-Oriented Dialogue 모델입니다. "
    "입력에는 현재 FSM 상태, 현재 주문 상태, 이전 대화와 사용자의 현재 발화가 주어집니다. "
    "현재 발화에서 사용자가 실제로 표현한 정보와 기존 주문 상태를 구분하세요. "
    "사용자가 말하지 않은 메뉴, 온도, 수량을 임의로 만들지 마세요. "
    "단, 시스템 메뉴 정책으로 확정되는 값은 state_after에 반영할 수 있습니다. "
    "다음 주문 상태와 시스템 동작을 판단하고 응답을 생성하세요. "
    "반드시 지정된 JSON 객체만 출력하고 설명, 마크다운, 추론 과정은 출력하지 마세요."
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{path}:{line_number}: invalid JSON: {error}") from error
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number}: expected JSON object")
            yield value


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            count += 1
    return count


def canonical_group_id(row: dict[str, Any]) -> str:
    """Return the canonical source identity shared by all context variants."""
    source = row.get("source") or {}
    dataset = str(source.get("dataset") or "").strip()
    source_index = source.get("source_index")
    if dataset and isinstance(source_index, int):
        return f"{dataset}:{source_index:06d}"

    parent = str(source.get("parent_rule_id") or "").strip()
    if parent:
        return parent

    row_id = str(row.get("id") or "").strip()
    if row_id:
        # Defensive fallback for future imported datasets. Strip the known
        # context suffix so ctx1/ctx2/ctx3 still remain a single group.
        for suffix in ("_ctx1", "_ctx2", "_ctx3"):
            if row_id.endswith(suffix):
                return row_id[: -len(suffix)]
        return row_id
    raise ValueError("row has no usable canonical source identity")


def source_scenario(row: dict[str, Any]) -> str:
    context = row.get("context_generation") or {}
    original = str(context.get("source_scenario") or "").strip()
    if original:
        return f"context::{original}"
    return str(row.get("scenario_group") or "unknown")


def stable_score(group_id: str, seed: str) -> str:
    return hashlib.sha256(f"{seed}\n{group_id}".encode("utf-8")).hexdigest()


def build_groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[canonical_group_id(row)].append(row)

    for group_id, members in groups.items():
        scenarios = {source_scenario(row) for row in members}
        if len(scenarios) != 1:
            raise ValueError(f"{group_id}: source group spans scenarios {sorted(scenarios)}")
    return dict(groups)


def split_by_source_group(
    rows: list[dict[str, Any]],
    *,
    validation_ratio: float,
    seed: str,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if not 0.0 < validation_ratio < 0.5:
        raise ValueError("validation_ratio must be between 0 and 0.5")

    groups = build_groups(rows)
    strata: dict[str, list[str]] = defaultdict(list)
    for group_id, members in groups.items():
        strata[source_scenario(members[0])].append(group_id)

    validation_groups: set[str] = set()
    stratum_stats: dict[str, dict[str, Any]] = {}
    for scenario, group_ids in sorted(strata.items()):
        ordered = sorted(group_ids, key=lambda group_id: stable_score(group_id, seed))
        validation_group_count = int(round(len(ordered) * validation_ratio))
        if len(ordered) > 1:
            validation_group_count = max(1, min(len(ordered) - 1, validation_group_count))
        else:
            validation_group_count = 0
        selected = set(ordered[:validation_group_count])
        validation_groups.update(selected)
        validation_rows = sum(len(groups[group_id]) for group_id in selected)
        total_rows = sum(len(groups[group_id]) for group_id in ordered)
        stratum_stats[scenario] = {
            "source_groups": len(ordered),
            "validation_source_groups": validation_group_count,
            "rows": total_rows,
            "validation_rows": validation_rows,
        }

    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    for row in rows:
        if canonical_group_id(row) in validation_groups:
            validation.append(row)
        else:
            train.append(row)

    # Preserve deterministic source order in files after deterministic group
    # selection. This makes generated diffs stable across reruns.
    return train, validation, {
        "source_groups": len(groups),
        "validation_source_groups": len(validation_groups),
        "strata": stratum_stats,
    }


def compact_items(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        result.append({
            "item_id": int(item.get("item_id", index)),
            "menu": item.get("menu"),
            "temperature": item.get("temperature"),
            "quantity": item.get("quantity"),
        })
    return result


def compact_state(state: Any) -> dict[str, Any]:
    if not isinstance(state, dict):
        return {"items": []}
    return {"items": compact_items(state.get("items"))}


def compact_utterance_items(items: Any) -> list[dict[str, Any]]:
    return compact_items(items)


def user_payload(row: dict[str, Any]) -> dict[str, Any]:
    history = []
    for turn in row.get("history") or []:
        if not isinstance(turn, dict):
            continue
        history.append({
            "role": str(turn.get("role") or "assistant"),
            "text": str(turn.get("text") or ""),
        })
    return {
        "fsm_state_before": row.get("fsm_state_before"),
        "state_before": compact_state(row.get("state_before")),
        "history": history,
        "user_text": str(row.get("user_text") or ""),
    }


def assistant_payload(row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target") or {}
    return {
        "intent": target.get("intent"),
        "utterance_items": compact_utterance_items(target.get("utterance_items")),
        "state_after": compact_state(target.get("state_after")),
        "order_status": target.get("order_status"),
        "decision": target.get("decision"),
        "response_key": target.get("response_key"),
        "fsm_state_after": row.get("fsm_state_after"),
        "response": target.get("response"),
    }


def qwen_record(row: dict[str, Any], split: str) -> dict[str, Any]:
    return {
        "id": str(row.get("id") or ""),
        "source_group_id": canonical_group_id(row),
        "scenario_group": str(row.get("scenario_group") or "unknown"),
        "split": split,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    user_payload(row), ensure_ascii=False, separators=(",", ":")
                ),
            },
            {
                "role": "assistant",
                "content": json.dumps(
                    assistant_payload(row), ensure_ascii=False, separators=(",", ":")
                ),
            },
        ],
    }


def distribution(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "rows": len(rows),
        "source_groups": len({canonical_group_id(row) for row in rows}),
        "scenario_counts": dict(sorted(Counter(
            str(row.get("scenario_group") or "unknown") for row in rows
        ).items())),
        "source_scenario_counts": dict(sorted(Counter(
            source_scenario(row) for row in rows
        ).items())),
        "intent_counts": dict(sorted(Counter(
            str((row.get("target") or {}).get("intent") or "UNKNOWN") for row in rows
        ).items())),
        "decision_counts": dict(sorted(Counter(
            str((row.get("target") or {}).get("decision") or "") for row in rows
        ).items())),
    }


def exact_text_overlap(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> int:
    left_text = {str(row.get("user_text") or "").strip() for row in left if row.get("user_text")}
    right_text = {str(row.get("user_text") or "").strip() for row in right if row.get("user_text")}
    return len(left_text & right_text)


def validate_raw_split(
    train: list[dict[str, Any]],
    validation: list[dict[str, Any]],
    test: list[dict[str, Any]],
) -> dict[str, Any]:
    errors: list[str] = []
    if len(train) + len(validation) != EXPECTED_TRAIN_VALID_TOTAL:
        errors.append(
            f"train+validation must equal {EXPECTED_TRAIN_VALID_TOTAL}, got {len(train) + len(validation)}"
        )
    if len(test) != EXPECTED_TEST_TOTAL:
        errors.append(f"test must equal {EXPECTED_TEST_TOTAL}, got {len(test)}")

    train_groups = {canonical_group_id(row) for row in train}
    validation_groups = {canonical_group_id(row) for row in validation}
    test_groups = {canonical_group_id(row) for row in test}

    overlaps = {
        "train_validation_source_group": len(train_groups & validation_groups),
        "train_test_source_group": len(train_groups & test_groups),
        "validation_test_source_group": len(validation_groups & test_groups),
    }
    if any(overlaps.values()):
        errors.append(f"source-group leakage detected: {overlaps}")

    all_rows = [*train, *validation, *test]
    ids = [str(row.get("id") or "") for row in all_rows]
    if len(ids) != len(set(ids)):
        errors.append("duplicate row id across train/validation/test")

    for row in all_rows:
        quality = row.get("label_quality") or {}
        target = row.get("target") or {}
        if quality.get("context_required"):
            errors.append(f"{row.get('id')}: context_required survived final split")
            break
        for key in ("state_after", "decision", "response_key", "response"):
            if target.get(key) in (None, ""):
                errors.append(f"{row.get('id')}: missing target.{key}")
                break

    if errors:
        raise ValueError("; ".join(errors))
    return overlaps


def validate_qwen_records(
    source_rows: list[dict[str, Any]],
    records: list[dict[str, Any]],
    *,
    expected_split: str,
) -> None:
    if len(source_rows) != len(records):
        raise ValueError(f"{expected_split}: Qwen row count mismatch")

    for source, record in zip(source_rows, records):
        if record.get("split") != expected_split:
            raise ValueError(f"{record.get('id')}: wrong split marker")
        if record.get("id") != source.get("id"):
            raise ValueError("Qwen/source id order mismatch")
        if record.get("source_group_id") != canonical_group_id(source):
            raise ValueError(f"{record.get('id')}: wrong source group")

        messages = record.get("messages")
        if not isinstance(messages, list) or len(messages) != 3:
            raise ValueError(f"{record.get('id')}: expected exactly 3 messages")
        roles = [message.get("role") for message in messages if isinstance(message, dict)]
        if roles != ["system", "user", "assistant"]:
            raise ValueError(f"{record.get('id')}: invalid roles {roles}")

        try:
            user_json = json.loads(messages[1]["content"])
            assistant_json = json.loads(messages[2]["content"])
        except (KeyError, TypeError, json.JSONDecodeError) as error:
            raise ValueError(f"{record.get('id')}: invalid JSON message content") from error

        if user_json != user_payload(source):
            raise ValueError(f"{record.get('id')}: user payload changed during conversion")
        if assistant_json != assistant_payload(source):
            raise ValueError(f"{record.get('id')}: assistant target changed during conversion")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--train-valid-input",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_sft_train_valid.jsonl",
    )
    parser.add_argument(
        "--test-input",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_sft_test.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod" / "qwen",
    )
    parser.add_argument("--validation-ratio", type=float, default=DEFAULT_VALIDATION_RATIO)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    args = parser.parse_args()

    train_valid_input = args.train_valid_input.resolve()
    test_input = args.test_input.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    candidates = list(iter_jsonl(train_valid_input))
    test = list(iter_jsonl(test_input))
    if len(candidates) != EXPECTED_TRAIN_VALID_TOTAL:
        raise ValueError(
            f"expected {EXPECTED_TRAIN_VALID_TOTAL} train/valid candidate rows, got {len(candidates)}"
        )

    train, validation, split_meta = split_by_source_group(
        candidates,
        validation_ratio=args.validation_ratio,
        seed=args.seed,
    )
    overlaps = validate_raw_split(train, validation, test)

    raw_train_path = output_dir / "pumpkin_tod_v1_train.jsonl"
    raw_validation_path = output_dir / "pumpkin_tod_v1_validation.jsonl"
    raw_test_path = output_dir / "pumpkin_tod_v1_test.jsonl"
    write_jsonl(raw_train_path, train)
    write_jsonl(raw_validation_path, validation)
    # Copy test through JSON parsing/writing so all three prepared files have a
    # consistent normalized JSONL shape; no row is sampled or removed.
    write_jsonl(raw_test_path, test)

    qwen_train = [qwen_record(row, "train") for row in train]
    qwen_validation = [qwen_record(row, "validation") for row in validation]
    qwen_test = [qwen_record(row, "test") for row in test]

    validate_qwen_records(train, qwen_train, expected_split="train")
    validate_qwen_records(validation, qwen_validation, expected_split="validation")
    validate_qwen_records(test, qwen_test, expected_split="test")

    qwen_train_path = output_dir / "pumpkin_tod_v1_qwen_train.jsonl"
    qwen_validation_path = output_dir / "pumpkin_tod_v1_qwen_validation.jsonl"
    qwen_test_path = output_dir / "pumpkin_tod_v1_qwen_test.jsonl"
    write_jsonl(qwen_train_path, qwen_train)
    write_jsonl(qwen_validation_path, qwen_validation)
    write_jsonl(qwen_test_path, qwen_test)

    stats = {
        "split_version": SPLIT_VERSION,
        "qwen_format_version": QWEN_FORMAT_VERSION,
        "seed": args.seed,
        "validation_ratio_requested": args.validation_ratio,
        "validation_ratio_actual_rows": len(validation) / len(candidates),
        "group_key": "source.dataset + source.source_index",
        "source_group_policy": "all rows derived from one canonical source stay in exactly one split",
        "stratification": "source scenario family before deterministic stable-hash group selection",
        "test_policy": "fixed 1,507-row SFT test is never resampled",
        "chat_template": {
            "format": "Hugging Face messages: system/user/assistant",
            "recommended_qwen3_option": "apply_chat_template(..., enable_thinking=False)",
            "assistant_output": "JSON only",
        },
        "split_meta": split_meta,
        "train": distribution(train),
        "validation": distribution(validation),
        "test": distribution(test),
        "leakage_checks": overlaps,
        "diagnostic_exact_user_text_overlap_not_used_as_group_key": {
            "train_validation": exact_text_overlap(train, validation),
            "train_test": exact_text_overlap(train, test),
            "validation_test": exact_text_overlap(validation, test),
        },
        "files": {
            "raw_train": str(raw_train_path.relative_to(PROJECT_ROOT)),
            "raw_validation": str(raw_validation_path.relative_to(PROJECT_ROOT)),
            "raw_test": str(raw_test_path.relative_to(PROJECT_ROOT)),
            "qwen_train": str(qwen_train_path.relative_to(PROJECT_ROOT)),
            "qwen_validation": str(qwen_validation_path.relative_to(PROJECT_ROOT)),
            "qwen_test": str(qwen_test_path.relative_to(PROJECT_ROOT)),
            "fixed_test_input_sha256": sha256_file(test_input),
        },
    }
    stats_path = output_dir / "pumpkin_tod_v1_qwen_stats.json"
    stats_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "train_rows": len(train),
        "validation_rows": len(validation),
        "test_rows": len(test),
        "train_source_groups": stats["train"]["source_groups"],
        "validation_source_groups": stats["validation"]["source_groups"],
        "source_group_leakage": overlaps,
        "stats": str(stats_path.relative_to(PROJECT_ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
