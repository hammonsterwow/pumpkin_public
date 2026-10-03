#!/usr/bin/env python3
"""Build Pumpkin TOD labels from the canonical Structure B ground truth.

This generator deliberately does *not* run the learned NLU model.  The source
JSONL labels are treated as ground truth, then the current Pumpkin order policy
and ResponseManager are used to derive deterministic dialogue labels.

Important limitation
--------------------
The canonical Structure B files contain independent utterances, not dialogue
history.  A full next-state/response label therefore cannot be truthfully
created for every row.  Context-dependent rows (for example bare AFFIRM/DENY,
MODIFY, CANCEL, or ORDER rows containing only a slot answer such as "두 잔이요")
are preserved with partial supervision and ``context_required=true`` instead of
inventing a fake previous order.

The output is intended as the first clean layer for Pumpkin TOD training.  A
later multi-turn scenario builder can fill the context-required rows using
explicit state_before/history generated from known FSM scenarios.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
ROBOT_CONTROLLER_SRC = PROJECT_ROOT / "ros2_ws" / "src" / "robot_controller"
if str(ROBOT_CONTROLLER_SRC) not in sys.path:
    sys.path.insert(0, str(ROBOT_CONTROLLER_SRC))

from robot_controller.menu_policy import (  # noqa: E402
    default_temperature,
    normalize_menu,
    normalize_quantity,
    normalize_temperature,
)
from robot_controller.order_schema import (  # noqa: E402
    calculate_order_status,
    extract_items,
)
from robot_controller.response_manager import ResponseManager  # noqa: E402


SCHEMA_VERSION = "pumpkin_tod_rule_v1"
EXPECTED_COUNTS = {
    "structure_b_train_valid": 22_512,
    "structure_b_test": 1_507,
}
EXPECTED_TOTAL = sum(EXPECTED_COUNTS.values())
SLOT_PRIORITY = ("menu", "quantity", "temperature")
CONTEXT_DEPENDENT_INTENTS = {"AFFIRM", "DENY", "MODIFY", "CANCEL"}


# ---------------------------------------------------------------------------
# Basic normalization helpers
# ---------------------------------------------------------------------------

def _none_token(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, str) and value.strip().upper() in {"", "NONE", "NULL"}:
        return None
    return value


def _source_candidates(record: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = record.get("items")
    if isinstance(candidates, list):
        return [item for item in candidates if isinstance(item, dict)][:3]

    order = record.get("order")
    if isinstance(order, dict):
        nested = order.get("items")
        if isinstance(nested, list):
            return [item for item in nested if isinstance(item, dict)][:3]
        if order:
            return [order]

    legacy = {
        "menu": record.get("menu") or record.get("menu_label") or record.get("drink"),
        "temperature": (
            record.get("temperature")
            or record.get("temp")
            or record.get("temperature_label")
        ),
        "quantity": record.get("quantity") or record.get("count") or record.get("qty"),
    }
    return [legacy] if any(value is not None for value in legacy.values()) else []


def source_utterance_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Copy only what the source utterance ground truth explicitly contains.

    Unlike ``order_schema.normalize_item``, this function intentionally does not
    inject the ICE default for ICE-only menus.  That distinction lets the new
    model learn both (a) what the customer actually said and (b) what the robot
    may safely infer from deterministic menu policy.
    """

    result: list[dict[str, Any]] = []
    for index, raw in enumerate(_source_candidates(record)):
        raw_menu = _none_token(raw.get("menu", raw.get("menu_name", raw.get("drink"))))
        raw_temp = _none_token(raw.get("temperature", raw.get("temp")))
        raw_qty = _none_token(raw.get("quantity", raw.get("count", raw.get("qty"))))

        menu = normalize_menu(raw_menu) if raw_menu is not None else None
        temperature = normalize_temperature(raw_temp) if raw_temp is not None else None
        quantity = normalize_quantity(raw_qty) if raw_qty is not None else None

        # Preserve an unsupported literal so the training record does not lose
        # evidence that the user actually named a menu/option outside policy.
        unsupported_menu = str(raw_menu).strip() if raw_menu is not None and menu is None else None
        unsupported_temperature = (
            str(raw_temp).strip()
            if raw_temp is not None and temperature is None
            else None
        )
        unsupported_quantity = (
            raw_qty if raw_qty is not None and quantity is None else None
        )

        has_any_evidence = any(
            value is not None
            for value in (
                menu,
                temperature,
                quantity,
                unsupported_menu,
                unsupported_temperature,
                unsupported_quantity,
            )
        )
        if not has_any_evidence:
            continue

        missing = [slot for slot, value in (
            ("menu", menu),
            ("quantity", quantity),
            ("temperature", temperature),
        ) if value is None]

        result.append({
            "item_id": index,
            "menu": menu,
            "temperature": temperature,
            "quantity": quantity,
            "missing_slots": missing,
            "unsupported_menu_literal": unsupported_menu,
            "unsupported_temperature_literal": unsupported_temperature,
            "unsupported_quantity_literal": unsupported_quantity,
            "source_validation_errors": list(raw.get("validation_errors") or []),
        })
    return result


def runtime_items(record: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply the same item normalization/default-temperature policy as runtime."""
    return extract_items(record)


def inferred_policy_slots(
    utterance_items: list[dict[str, Any]],
    normalized_items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    inferred: list[dict[str, Any]] = []
    for index, item in enumerate(normalized_items):
        spoken = utterance_items[index] if index < len(utterance_items) else {}
        if spoken.get("temperature") is None and item.get("temperature") is not None:
            menu = item.get("menu")
            if default_temperature(menu) == item.get("temperature"):
                inferred.append({
                    "item_id": int(item.get("item_id", index)),
                    "slot": "temperature",
                    "value": item.get("temperature"),
                    "reason": "single_allowed_temperature_menu_policy",
                })
    return inferred


# ---------------------------------------------------------------------------
# Deterministic dialogue rules
# ---------------------------------------------------------------------------

def first_missing_target(items: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    """Mirror DecisionNode/OrderDialogueManager: item-first, menu→quantity→temp."""
    for item_index, item in enumerate(items):
        item_id = int(item.get("item_id", item_index))
        for slot in SLOT_PRIORITY:
            if item.get(slot) is None:
                return {"item_id": item_id, "slot": slot}
    return None


def has_literal_menu_evidence(utterance_items: list[dict[str, Any]]) -> bool:
    return any(
        item.get("menu") is not None or item.get("unsupported_menu_literal") is not None
        for item in utterance_items
    )


def is_slot_only_order(
    intent: str,
    utterance_items: list[dict[str, Any]],
) -> bool:
    """Identify ORDER labels that require a previous dialogue state.

    Examples: "두 잔이요", "아이스요".  Labelling these as a new empty-order
    turn would teach the wrong state transition, so they remain partial labels.
    """
    if intent != "ORDER" or not utterance_items:
        return False
    return not has_literal_menu_evidence(utterance_items)


def response_text(
    manager: ResponseManager,
    response_key: str,
    *,
    text: str,
    order: dict[str, Any] | None = None,
    response_args: dict[str, Any] | None = None,
) -> str:
    context: dict[str, Any] = {
        "decision": "DATA_LABEL",
        "response_key": response_key,
        "response_args": dict(response_args or {}),
        "nlu_result": {"text": text},
    }
    if order is not None:
        context["order"] = order
    rendered = manager.render(context, include_debug_context=False)
    return str(rendered.get("speech") or "").strip()


def build_order_target(
    record: dict[str, Any],
    manager: ResponseManager,
    utterance_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    """Return target, quality and scenario for an ORDER source row."""
    text = str(record.get("text") or "").strip()
    normalized = runtime_items(record)
    inferred = inferred_policy_slots(utterance_items, normalized)

    # Short slot-only answers are valid NLU ground truth but not standalone TOD
    # transitions.  Keep them for later multi-turn scenario construction.
    if is_slot_only_order("ORDER", utterance_items):
        target = {
            "intent": "ORDER",
            "utterance_items": utterance_items,
            "state_after": None,
            "order_status": str(record.get("order_status") or "INCOMPLETE").upper(),
            "decision": None,
            "response_key": None,
            "response_args": None,
            "response": None,
            "inferred_policy_slots": [],
        }
        quality = {
            "mode": "source_ground_truth_partial",
            "fully_supervised": False,
            "context_required": True,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": False,
            "reasons": ["order_slot_answer_requires_previous_order_state"],
        }
        return target, quality, "order_contextual_slot_answer"

    status = calculate_order_status(normalized)
    order = {
        "items": deepcopy(normalized),
        "order_status": status,
    }

    validation_errors = [
        error
        for item in normalized
        for error in item.get("validation_errors", [])
    ]

    if not normalized:
        # ORDER with no usable item evidence cannot be completed from this row.
        target = {
            "intent": "ORDER",
            "utterance_items": utterance_items,
            "state_after": {"items": []},
            "order_status": "INCOMPLETE",
            "decision": "ASK_MENU",
            "response_key": "ask_menu",
            "response_args": {},
            "response": response_text(manager, "ask_menu", text=text, order=order),
            "inferred_policy_slots": [],
        }
        quality = {
            "mode": "deterministic_initial_state",
            "fully_supervised": True,
            "context_required": False,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": True,
            "reasons": ["initial_order_without_usable_item"],
        }
        return target, quality, "order_missing_menu"

    if validation_errors:
        target = {
            "intent": "ORDER",
            "utterance_items": utterance_items,
            "state_after": {"items": deepcopy(normalized)},
            "order_status": "INVALID",
            "decision": "OUT_OF_POLICY",
            "response_key": "invalid_order",
            "response_args": {},
            "response": response_text(manager, "invalid_order", text=text, order=order),
            "inferred_policy_slots": inferred,
        }
        quality = {
            "mode": "deterministic_initial_state",
            "fully_supervised": True,
            "context_required": False,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": True,
            "reasons": ["runtime_menu_policy_validation"],
        }
        return target, quality, "order_invalid"

    waiting = first_missing_target(normalized)
    if waiting is not None:
        slot = str(waiting["slot"])
        item_id = int(waiting["item_id"])
        waiting_item = next(
            (
                item for index, item in enumerate(normalized)
                if int(item.get("item_id", index)) == item_id
            ),
            {},
        )
        args = {
            "item_id": item_id,
            "slot": slot,
            "menu": waiting_item.get("menu"),
        }
        response_key = f"ask_{slot}"
        target = {
            "intent": "ORDER",
            "utterance_items": utterance_items,
            "state_after": {"items": deepcopy(normalized)},
            "order_status": "INCOMPLETE",
            "decision": f"ASK_{slot.upper()}",
            "response_key": response_key,
            "response_args": args,
            "response": response_text(
                manager,
                response_key,
                text=text,
                order=order,
                response_args=args,
            ),
            "inferred_policy_slots": inferred,
        }
        quality = {
            "mode": "deterministic_initial_state",
            "fully_supervised": True,
            "context_required": False,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": True,
            "reasons": [f"current_fsm_first_missing_slot_{slot}"],
        }
        multi = len(normalized) > 1
        return target, quality, f"order_{'multi_' if multi else ''}missing_{slot}"

    target = {
        "intent": "ORDER",
        "utterance_items": utterance_items,
        "state_after": {"items": deepcopy(normalized)},
        "order_status": "VALID",
        "decision": "CONFIRM_ORDER",
        "response_key": "confirm_order",
        "response_args": {},
        "response": response_text(manager, "confirm_order", text=text, order=order),
        "inferred_policy_slots": inferred,
    }
    quality = {
        "mode": "deterministic_initial_state",
        "fully_supervised": True,
        "context_required": False,
        "usable_for_intent_slots": True,
        "usable_for_tod_response": True,
        "reasons": ["all_runtime_required_slots_filled"],
    }
    multi = len(normalized) > 1
    return target, quality, "order_multi_complete" if multi else "order_complete"


def build_non_order_target(
    record: dict[str, Any],
    manager: ResponseManager,
    intent: str,
    utterance_items: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, Any] | None, str | None, str | None]:
    """Build safe labels for non-ORDER source rows.

    Returns target, quality, scenario, state_before, fsm_before, fsm_after.
    Context-dependent intents intentionally receive no fabricated transition.
    """
    text = str(record.get("text") or "").strip()
    source_status = str(record.get("order_status") or "NONE").upper()

    if intent in CONTEXT_DEPENDENT_INTENTS:
        target = {
            "intent": intent,
            "utterance_items": utterance_items,
            "state_after": None,
            "order_status": source_status,
            "decision": None,
            "response_key": None,
            "response_args": None,
            "response": None,
            "inferred_policy_slots": [],
        }
        quality = {
            "mode": "source_ground_truth_partial",
            "fully_supervised": False,
            "context_required": True,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": False,
            "reasons": [f"{intent.lower()}_transition_depends_on_previous_fsm_and_order"],
        }
        return target, quality, intent.lower(), None, None, None

    state = {"items": []}
    if intent == "GUIDE":
        decision, response_key, fsm_after = "GUIDE_CUSTOMER", "guide_customer", "ORDER_LISTEN"
        args = {"direction": record.get("direction")}
    elif intent == "PAYMENT":
        decision, response_key, fsm_after = "PAYMENT_GUIDE", "payment_guide", "ORDER_LISTEN"
        args = {}
    else:  # UNKNOWN and any future unsupported intent use current Decision fallback.
        decision, response_key, fsm_after = "OUT_OF_POLICY", "out_of_policy", "ORDER_LISTEN"
        args = {}

    response = response_text(
        manager,
        response_key,
        text=text,
        order={"items": []},
        response_args=args,
    )
    target = {
        "intent": intent,
        "utterance_items": utterance_items,
        "state_after": deepcopy(state),
        "order_status": source_status,
        "decision": decision,
        "response_key": response_key,
        "response_args": args,
        "response": response,
        "inferred_policy_slots": [],
    }
    quality = {
        "mode": "deterministic_initial_state",
        "fully_supervised": True,
        "context_required": False,
        "usable_for_intent_slots": True,
        "usable_for_tod_response": True,
        "reasons": ["current_fsm_initial_state_rule"],
    }
    return target, quality, intent.lower(), deepcopy(state), "ORDER_LISTEN", fsm_after


def build_record(
    record: dict[str, Any],
    *,
    dataset_name: str,
    source_index: int,
    manager: ResponseManager,
) -> dict[str, Any]:
    text = str(record.get("text") or "").strip()
    intent = str(record.get("intent") or "UNKNOWN").upper()
    utterance_items = source_utterance_items(record)

    state_before: dict[str, Any] | None = {"items": []}
    fsm_before: str | None = "ORDER_LISTEN"
    fsm_after: str | None

    if intent == "ORDER":
        target, quality, scenario = build_order_target(record, manager, utterance_items)
        if quality["context_required"]:
            state_before = None
            fsm_before = None
            fsm_after = None
        else:
            decision = str(target.get("decision") or "")
            fsm_after = "ORDER_CONFIRM" if decision == "CONFIRM_ORDER" else decision
    else:
        (
            target,
            quality,
            scenario,
            state_before,
            fsm_before,
            fsm_after,
        ) = build_non_order_target(record, manager, intent, utterance_items)

    return {
        "schema_version": SCHEMA_VERSION,
        "id": f"{dataset_name}_{source_index:06d}",
        "source": {
            "dataset": dataset_name,
            "source_index": source_index,
            "original_source": deepcopy(record.get("source")),
            "source_order_status": record.get("order_status"),
            "source_validation_errors": deepcopy(record.get("validation_errors") or []),
        },
        "scenario_group": scenario,
        "history": [],
        "fsm_state_before": fsm_before,
        "state_before": state_before,
        "user_text": text,
        "target": target,
        "fsm_state_after": fsm_after,
        "label_quality": quality,
    }


# ---------------------------------------------------------------------------
# Validation / IO
# ---------------------------------------------------------------------------

def iter_jsonl(path: Path) -> Iterable[tuple[int, dict[str, Any]]]:
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
            yield line_number, value


def validate_generated(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    quality = row["label_quality"]
    target = row["target"]

    if quality["context_required"] and quality["fully_supervised"]:
        errors.append("context_required row cannot be fully_supervised")

    if quality["fully_supervised"]:
        for key in ("decision", "response_key", "response", "state_after"):
            if target.get(key) in (None, ""):
                errors.append(f"fully_supervised row missing target.{key}")
    else:
        # Prevent the generator itself from silently creating a fake dialogue
        # state for context-dependent source rows.
        if target.get("state_after") is not None:
            errors.append("partial contextual row must not fabricate state_after")
        if target.get("response") is not None:
            errors.append("partial contextual row must not fabricate response")

    if not row.get("user_text"):
        errors.append("empty user_text")

    return errors


def write_dataset(
    source_path: Path,
    output_path: Path,
    *,
    dataset_name: str,
    manager: ResponseManager,
) -> dict[str, Any]:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    intent_counts: Counter[str] = Counter()
    scenario_counts: Counter[str] = Counter()
    supervision_counts: Counter[str] = Counter()
    decision_counts: Counter[str] = Counter()
    source_status_counts: Counter[str] = Counter()
    target_status_counts: Counter[str] = Counter()
    inferred_slot_counts: Counter[str] = Counter()
    status_changes: Counter[str] = Counter()
    validation_error_count = 0
    examples_by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)

    with output_path.open("w", encoding="utf-8") as output:
        for source_index, (_line_number, record) in enumerate(iter_jsonl(source_path)):
            row = build_record(
                record,
                dataset_name=dataset_name,
                source_index=source_index,
                manager=manager,
            )
            errors = validate_generated(row)
            if errors:
                validation_error_count += 1
                raise ValueError(
                    f"generated row {row['id']} failed validation: {errors}"
                )

            output.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            total += 1

            intent = str(row["target"].get("intent") or "UNKNOWN")
            scenario = str(row.get("scenario_group") or "unknown")
            decision = str(row["target"].get("decision") or "CONTEXT_REQUIRED")
            supervision = "fully_supervised" if row["label_quality"]["fully_supervised"] else "context_required"
            source_status = str(row["source"].get("source_order_status") or "NONE")
            target_status = str(row["target"].get("order_status") or "NONE")

            intent_counts[intent] += 1
            scenario_counts[scenario] += 1
            supervision_counts[supervision] += 1
            decision_counts[decision] += 1
            source_status_counts[source_status] += 1
            target_status_counts[target_status] += 1
            if source_status != target_status:
                status_changes[f"{source_status}->{target_status}"] += 1
            for inferred in row["target"].get("inferred_policy_slots") or []:
                inferred_slot_counts[f"{inferred['slot']}={inferred['value']}"] += 1

            if len(examples_by_scenario[scenario]) < 2:
                examples_by_scenario[scenario].append({
                    "id": row["id"],
                    "user_text": row["user_text"],
                    "decision": row["target"].get("decision"),
                    "response": row["target"].get("response"),
                    "context_required": row["label_quality"]["context_required"],
                })

    return {
        "dataset": dataset_name,
        "input": str(source_path.relative_to(PROJECT_ROOT)),
        "output": str(output_path.relative_to(PROJECT_ROOT)),
        "total": total,
        "intent_counts": dict(sorted(intent_counts.items())),
        "scenario_counts": dict(sorted(scenario_counts.items())),
        "supervision_counts": dict(sorted(supervision_counts.items())),
        "decision_counts": dict(sorted(decision_counts.items())),
        "source_order_status_counts": dict(sorted(source_status_counts.items())),
        "target_order_status_counts": dict(sorted(target_status_counts.items())),
        "source_to_runtime_status_changes": dict(sorted(status_changes.items())),
        "inferred_policy_slot_counts": dict(sorted(inferred_slot_counts.items())),
        "validation_error_count": validation_error_count,
        "examples_by_scenario": dict(sorted(examples_by_scenario.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod",
    )
    parser.add_argument(
        "--allow-count-mismatch",
        action="store_true",
        help="do not fail if canonical source row counts differ from the documented 24,019",
    )
    args = parser.parse_args()

    manager = ResponseManager()
    output_dir = args.output_dir.resolve()

    specs = [
        (
            "structure_b_train_valid",
            PROJECT_ROOT / "data" / "structure_b_train_valid.jsonl",
            output_dir / "pumpkin_tod_v1_train_valid.jsonl",
        ),
        (
            "structure_b_test",
            PROJECT_ROOT / "data" / "structure_b_test.jsonl",
            output_dir / "pumpkin_tod_v1_test.jsonl",
        ),
    ]

    summaries: list[dict[str, Any]] = []
    for dataset_name, source_path, output_path in specs:
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        summary = write_dataset(
            source_path,
            output_path,
            dataset_name=dataset_name,
            manager=manager,
        )
        summaries.append(summary)
        expected = EXPECTED_COUNTS[dataset_name]
        if summary["total"] != expected and not args.allow_count_mismatch:
            raise RuntimeError(
                f"{dataset_name}: expected {expected:,} rows, got {summary['total']:,}"
            )

    total = sum(summary["total"] for summary in summaries)
    if total != EXPECTED_TOTAL and not args.allow_count_mismatch:
        raise RuntimeError(f"expected {EXPECTED_TOTAL:,} total rows, got {total:,}")

    merged_intents: Counter[str] = Counter()
    merged_scenarios: Counter[str] = Counter()
    merged_supervision: Counter[str] = Counter()
    merged_decisions: Counter[str] = Counter()
    merged_status_changes: Counter[str] = Counter()
    merged_inferred: Counter[str] = Counter()
    for summary in summaries:
        merged_intents.update(summary["intent_counts"])
        merged_scenarios.update(summary["scenario_counts"])
        merged_supervision.update(summary["supervision_counts"])
        merged_decisions.update(summary["decision_counts"])
        merged_status_changes.update(summary["source_to_runtime_status_changes"])
        merged_inferred.update(summary["inferred_policy_slot_counts"])

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generator": str(Path(__file__).resolve().relative_to(PROJECT_ROOT)),
        "rule_basis": {
            "slot_priority": list(SLOT_PRIORITY),
            "item_policy": "finish one item before moving to the next",
            "ice_only_default": "use robot_controller.menu_policy.default_temperature",
            "response_source": "robot_controller.response_manager.ResponseManager",
            "ground_truth_policy": "never call learned NLU predictor; preserve canonical source labels",
            "context_policy": "do not invent prior state for context-dependent standalone utterances",
        },
        "total": total,
        "expected_total": EXPECTED_TOTAL,
        "intent_counts": dict(sorted(merged_intents.items())),
        "scenario_counts": dict(sorted(merged_scenarios.items())),
        "supervision_counts": dict(sorted(merged_supervision.items())),
        "decision_counts": dict(sorted(merged_decisions.items())),
        "source_to_runtime_status_changes": dict(sorted(merged_status_changes.items())),
        "inferred_policy_slot_counts": dict(sorted(merged_inferred.items())),
        "splits": summaries,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "pumpkin_tod_v1_stats.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps({
        "total": total,
        "supervision_counts": manifest["supervision_counts"],
        "decision_counts": manifest["decision_counts"],
        "scenario_counts": manifest["scenario_counts"],
        "stats": str(manifest_path.relative_to(PROJECT_ROOT)),
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
