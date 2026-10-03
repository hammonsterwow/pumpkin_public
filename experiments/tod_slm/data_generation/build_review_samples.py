#!/usr/bin/env python3
"""Build the combined human-review sample for Pumpkin TOD data.

The generated multi-turn sample audits the 3,760 context-dependent source rows.
This script adds a second, independent 200-row BASE DATA audit drawn only from
fully-supervised *train_valid* rows.  The fixed test split is deliberately not
used for human rule iteration, which keeps the later evaluation set untouched.

The final combined review file therefore contains:
- MULTITURN: 200 rows (40 per context-dependent scenario family)
- BASE DATA: 200 rows (stratified across initial-state order scenarios)

No label is changed by this script.  It only converts existing generated rows
into the compact schema used by the local review web.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TOD_DIR = PROJECT_ROOT / "data" / "tod"

BASE_INPUT = TOD_DIR / "pumpkin_tod_v1_train_valid.jsonl"
MULTITURN_INPUT = TOD_DIR / "pumpkin_tod_v1_multiturn_review_sample.jsonl"
BASE_OUTPUT = TOD_DIR / "pumpkin_tod_v1_base_review_sample.jsonl"
COMBINED_OUTPUT = TOD_DIR / "pumpkin_tod_v1_review_sample.jsonl"
STATS_OUTPUT = TOD_DIR / "pumpkin_tod_v1_review_stats.json"

# 200 total.  These buckets all exist in train_valid, so the fixed test set is
# not opened for manual review.  Missing-menu examples are test-only in the
# current canonical split and remain covered by deterministic generator checks.
BASE_REVIEW_QUOTAS: dict[str, int] = {
    "order_complete": 40,
    "order_missing_quantity": 25,
    "order_missing_temperature": 20,
    "order_multi_complete": 35,
    "order_multi_missing_quantity": 25,
    "order_multi_missing_temperature": 25,
    "guide": 15,
    "unknown": 15,
}

BASE_SCENARIO_LABELS: dict[str, str] = {
    "order_complete": "BASE DATA · 단일 주문 완료",
    "order_missing_quantity": "BASE DATA · 단일 수량 질문",
    "order_missing_temperature": "BASE DATA · 단일 온도 질문",
    "order_multi_complete": "BASE DATA · 다중 주문 완료",
    "order_multi_missing_quantity": "BASE DATA · 다중 수량 질문",
    "order_multi_missing_temperature": "BASE DATA · 다중 온도 질문",
    "guide": "BASE DATA · 안내",
    "unknown": "BASE DATA · UNKNOWN",
}


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            value = json.loads(line)
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


def systematic_sample(rows: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    """Pick deterministic examples spread across the entire scenario bucket."""
    if count <= 0:
        return []
    if len(rows) < count:
        raise ValueError(f"requested {count} rows from bucket containing only {len(rows)}")
    if len(rows) == count:
        return list(rows)

    # Midpoint systematic sampling avoids selecting only the first template
    # cluster when the canonical file is ordered by scenario/template family.
    picked_indexes: list[int] = []
    for index in range(count):
        position = int((index + 0.5) * len(rows) / count)
        position = min(position, len(rows) - 1)
        if picked_indexes and position <= picked_indexes[-1]:
            position = picked_indexes[-1] + 1
        picked_indexes.append(min(position, len(rows) - 1))

    if len(set(picked_indexes)) != count:
        raise ValueError("systematic sampler produced duplicate indexes")
    return [rows[index] for index in picked_indexes]


def to_base_review_row(row: dict[str, Any]) -> dict[str, Any]:
    quality = row.get("label_quality") or {}
    target = row.get("target") or {}
    scenario = str(row.get("scenario_group") or "unknown")

    if not quality.get("fully_supervised") or quality.get("context_required"):
        raise ValueError(f"{row.get('id')}: BASE DATA review requires fully-supervised row")
    for key in ("state_after", "decision", "response_key", "response"):
        if target.get(key) in (None, ""):
            raise ValueError(f"{row.get('id')}: missing target.{key}")

    fsm_before = row.get("fsm_state_before")
    fsm_after = row.get("fsm_state_after")
    state_before = row.get("state_before")
    if fsm_before != "ORDER_LISTEN":
        raise ValueError(f"{row.get('id')}: BASE DATA should start in ORDER_LISTEN, got {fsm_before}")
    if not isinstance(state_before, dict):
        raise ValueError(f"{row.get('id')}: missing state_before")

    return {
        "id": f"base_review__{row['id']}",
        "review_group": "BASE DATA",
        "source_id": row["id"],
        "base_scenario": scenario,
        "source_scenario": BASE_SCENARIO_LABELS.get(scenario, f"BASE DATA · {scenario}"),
        "history": deepcopy(row.get("history") or []),
        "fsm_state_before": fsm_before,
        "state_before": deepcopy(state_before),
        "user_text": str(row.get("user_text") or ""),
        "state_after": deepcopy(target["state_after"]),
        "decision": target["decision"],
        "response_key": target["response_key"],
        "fsm_state_after": fsm_after,
        "response": target["response"],
    }


def build_base_review() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    fully_supervised_total = 0

    for row in iter_jsonl(BASE_INPUT):
        quality = row.get("label_quality") or {}
        if not quality.get("fully_supervised") or quality.get("context_required"):
            continue
        fully_supervised_total += 1
        buckets[str(row.get("scenario_group") or "unknown")].append(row)

    if fully_supervised_total != 19_332:
        raise ValueError(
            f"expected 19,332 fully-supervised train_valid rows, got {fully_supervised_total}"
        )

    selected: list[dict[str, Any]] = []
    available_counts: dict[str, int] = {}
    for scenario, quota in BASE_REVIEW_QUOTAS.items():
        candidates = buckets.get(scenario, [])
        available_counts[scenario] = len(candidates)
        sampled = systematic_sample(candidates, quota)
        selected.extend(to_base_review_row(row) for row in sampled)

    if len(selected) != 200:
        raise ValueError(f"BASE DATA review must contain 200 rows, got {len(selected)}")

    selected_counts = Counter(row["base_scenario"] for row in selected)
    if dict(selected_counts) != BASE_REVIEW_QUOTAS:
        raise ValueError(
            f"BASE DATA quota mismatch: expected {BASE_REVIEW_QUOTAS}, got {dict(selected_counts)}"
        )

    return selected, {
        "source": str(BASE_INPUT.relative_to(PROJECT_ROOT)),
        "source_fully_supervised": fully_supervised_total,
        "test_rows_used_for_human_review": 0,
        "sampling": "deterministic midpoint systematic sampling within each scenario bucket",
        "available_counts": dict(sorted(available_counts.items())),
        "selected_counts": dict(sorted(selected_counts.items())),
        "selected_total": len(selected),
    }


def main() -> None:
    base_rows, base_stats = build_base_review()
    multiturn_rows = list(iter_jsonl(MULTITURN_INPUT))
    if len(multiturn_rows) != 200:
        raise ValueError(f"expected 200 multi-turn review rows, got {len(multiturn_rows)}")

    normalized_multiturn: list[dict[str, Any]] = []
    for row in multiturn_rows:
        copied = deepcopy(row)
        copied["review_group"] = "MULTITURN"
        normalized_multiturn.append(copied)

    base_count = write_jsonl(BASE_OUTPUT, base_rows)
    combined_rows = [*normalized_multiturn, *base_rows]
    combined_count = write_jsonl(COMBINED_OUTPUT, combined_rows)

    if base_count != 200 or combined_count != 400:
        raise ValueError(
            f"review count mismatch: base={base_count}, combined={combined_count}"
        )
    ids = [str(row.get("id") or "") for row in combined_rows]
    if len(ids) != len(set(ids)):
        raise ValueError("combined review sample contains duplicate ids")

    stats = {
        "multiturn": {
            "source": str(MULTITURN_INPUT.relative_to(PROJECT_ROOT)),
            "selected_total": len(normalized_multiturn),
            "scenario_counts": dict(sorted(Counter(
                str(row.get("source_scenario") or "unknown") for row in normalized_multiturn
            ).items())),
        },
        "base_data": base_stats,
        "combined_total": combined_count,
        "combined_output": str(COMBINED_OUTPUT.relative_to(PROJECT_ROOT)),
        "policy": {
            "human_review_test_split": False,
            "reason": "keep fixed test untouched while iterating generation rules",
        },
    }
    STATS_OUTPUT.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
