#!/usr/bin/env python3
"""Complete context-required Pumpkin TOD rows with deterministic dialogue context.

The first rule-label pass intentionally leaves standalone context-dependent
utterances (AFFIRM, DENY, MODIFY, CANCEL, and slot-only ORDER answers) partially
supervised.  This script turns those rows into fully supervised multi-turn
examples without asking an LLM to invent order truth.

Design goals
------------
* Preserve the original user utterance and source intent/slot labels.
* Generate only menu-policy-valid previous states.
* Derive previous robot prompts and next responses from ResponseManager.
* Mirror the current FSM semantics for confirmation/correction/cancellation.
* Create 3 deterministic context variants per train/valid source row, but only
  1 variant per test source row so evaluation size and source weighting remain
  unchanged.
* Produce a final SFT dataset that contains no ``context_required`` rows.
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
    SUPPORTED_MENUS,
    allowed_temperatures,
)
from robot_controller.order_schema import (  # noqa: E402
    calculate_order_status,
    extract_items,
)
from robot_controller.dialogue_act_resolver import DialogueActResolver  # noqa: E402
from robot_controller.response_manager import ResponseManager  # noqa: E402

from generate_rule_labels import response_text  # noqa: E402


SCHEMA_VERSION = "pumpkin_tod_multiturn_v1"
TRAIN_CONTEXT_VARIANTS = 3
TEST_CONTEXT_VARIANTS = 1
EXPECTED_CONTEXT_REQUIRED = {
    "train_valid": 3_180,
    "test": 580,
}
CONTEXT_SCENARIOS = {
    "affirm",
    "deny",
    "modify",
    "cancel",
    "order_contextual_slot_answer",
}
DUAL_TEMPERATURE_MENUS = tuple(
    menu for menu in SUPPORTED_MENUS
    if allowed_temperatures(menu) == frozenset({"ICE", "HOT"})
)


def iter_jsonl(path: Path) -> Iterable[dict[str, Any]]:
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


def normalize_items(raw_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return extract_items({"items": raw_items})


def state(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"items": deepcopy(items)}


def order(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "items": deepcopy(items),
        "order_status": calculate_order_status(items),
    }


def choose_quantity(source_index: int, variant: int, *, avoid: int | None = None) -> int:
    # Prefer ordinary cafe quantities for synthetic context while retaining the
    # source utterance's own quantity exactly when it is the target slot.
    candidates = (1, 2, 3, 4, 5)
    start = (source_index + variant * 2) % len(candidates)
    for offset in range(len(candidates)):
        value = candidates[(start + offset) % len(candidates)]
        if value != avoid:
            return value
    return 1 if avoid != 1 else 2


def choose_menu(
    source_index: int,
    variant: int,
    *,
    required_temperature: str | None = None,
    avoid: str | None = None,
) -> str:
    pool = list(DUAL_TEMPERATURE_MENUS if required_temperature == "HOT" else SUPPORTED_MENUS)
    pool = [menu for menu in pool if menu != avoid] or pool
    return pool[(source_index + variant) % len(pool)]


def choose_temperature(
    menu: str,
    source_index: int,
    variant: int,
    *,
    avoid: str | None = None,
) -> str:
    allowed = tuple(sorted(allowed_temperatures(menu)))
    if not allowed:
        raise ValueError(f"unsupported synthetic menu: {menu}")
    candidates = [value for value in allowed if value != avoid] or list(allowed)
    return candidates[(source_index + variant) % len(candidates)]


def complete_item(
    source_index: int,
    variant: int,
    *,
    menu: str | None = None,
    temperature: str | None = None,
    quantity: int | None = None,
) -> dict[str, Any]:
    chosen_menu = menu or choose_menu(source_index, variant, required_temperature=temperature)
    chosen_temperature = temperature or choose_temperature(chosen_menu, source_index, variant)
    chosen_quantity = quantity or choose_quantity(source_index, variant)
    items = normalize_items([{
        "menu": chosen_menu,
        "temperature": chosen_temperature,
        "quantity": chosen_quantity,
    }])
    if len(items) != 1 or calculate_order_status(items) != "VALID":
        raise ValueError(f"failed to build complete synthetic item: {items}")
    return items[0]


def render(
    manager: ResponseManager,
    response_key: str,
    *,
    user_text: str,
    items: list[dict[str, Any]],
    response_args: dict[str, Any] | None = None,
) -> str:
    return response_text(
        manager,
        response_key,
        text=user_text,
        order=order(items),
        response_args=response_args,
    )


def waiting_prompt(
    manager: ResponseManager,
    user_text: str,
    items: list[dict[str, Any]],
    slot: str,
    item_id: int = 0,
) -> tuple[str, dict[str, Any]]:
    item = next(
        (
            candidate for index, candidate in enumerate(items)
            if int(candidate.get("item_id", index)) == item_id
        ),
        {},
    )
    args = {
        "item_id": item_id,
        "slot": slot,
        "menu": item.get("menu"),
    }
    return render(
        manager,
        f"ask_{slot}",
        user_text=user_text,
        items=items,
        response_args=args,
    ), args


def confirmation_history(
    manager: ResponseManager,
    user_text: str,
    items: list[dict[str, Any]],
) -> list[dict[str, str]]:
    speech = render(
        manager,
        "confirm_order",
        user_text=user_text,
        items=items,
    )
    return [{"role": "assistant", "text": speech}]


def base_target(row: dict[str, Any]) -> dict[str, Any]:
    target = row.get("target")
    if not isinstance(target, dict):
        raise ValueError(f"{row.get('id')}: missing target")
    return target


def make_completed_row(
    source_row: dict[str, Any],
    *,
    variant: int,
    scenario: str,
    history: list[dict[str, str]],
    fsm_before: str,
    state_before_items: list[dict[str, Any]],
    state_after_items: list[dict[str, Any]],
    order_status: str,
    decision: str,
    response_key: str,
    response_args: dict[str, Any],
    response: str,
    fsm_after: str,
    strategy: str,
) -> dict[str, Any]:
    source_target = base_target(source_row)
    parent_id = str(source_row.get("id") or "unknown")
    return {
        "schema_version": SCHEMA_VERSION,
        "id": f"{parent_id}_ctx{variant + 1}",
        "source": {
            **deepcopy(source_row.get("source") or {}),
            "parent_rule_id": parent_id,
            "context_variant": variant + 1,
        },
        "scenario_group": scenario,
        "history": deepcopy(history),
        "fsm_state_before": fsm_before,
        "state_before": state(state_before_items),
        "user_text": str(source_row.get("user_text") or ""),
        "target": {
            "intent": str(source_target.get("intent") or "UNKNOWN"),
            "utterance_items": deepcopy(source_target.get("utterance_items") or []),
            "state_after": state(state_after_items),
            "order_status": order_status,
            "decision": decision,
            "response_key": response_key,
            "response_args": deepcopy(response_args),
            "response": response,
            "inferred_policy_slots": [],
        },
        "fsm_state_after": fsm_after,
        "label_quality": {
            "mode": "deterministic_multiturn_context",
            "fully_supervised": True,
            "context_required": False,
            "usable_for_intent_slots": True,
            "usable_for_tod_response": True,
            "reasons": [strategy],
        },
        "context_generation": {
            "strategy": strategy,
            "variant": variant + 1,
            "source_scenario": source_row.get("scenario_group"),
            "llm_used_for_labels": False,
        },
    }


def build_slot_answer(
    row: dict[str, Any],
    manager: ResponseManager,
    source_index: int,
    variant: int,
) -> dict[str, Any]:
    utterance_items = deepcopy(base_target(row).get("utterance_items") or [])
    if not utterance_items:
        raise ValueError(f"{row.get('id')}: slot-answer row has no utterance items")

    before_raw: list[dict[str, Any]] = []
    for item_index, incoming in enumerate(utterance_items):
        explicit_temp = incoming.get("temperature")
        # If the user is answering temperature, the previous menu must
        # genuinely support both ICE and HOT. ICE-only menus are normalized to
        # ICE before the FSM can ask a temperature question.
        if explicit_temp is not None:
            menu = DUAL_TEMPERATURE_MENUS[
                (source_index + item_index + variant) % len(DUAL_TEMPERATURE_MENUS)
            ]
        else:
            menu = choose_menu(source_index + item_index, variant)
        quantity = (
            None
            if incoming.get("quantity") is not None
            else choose_quantity(source_index + item_index, variant)
        )
        temperature = (
            None
            if explicit_temp is not None
            else choose_temperature(menu, source_index + item_index, variant)
        )
        before_raw.append({
            "menu": menu,
            "temperature": temperature,
            "quantity": quantity,
        })

    before_items = normalize_items(before_raw)
    if not before_items:
        raise ValueError(f"{row.get('id')}: could not construct previous slot context")

    # The current FSM asks the first missing slot in item-first,
    # menu -> quantity -> temperature order.
    waiting_slot: str | None = None
    waiting_item_id = 0
    for index, item in enumerate(before_items):
        for slot in ("menu", "quantity", "temperature"):
            if item.get(slot) is None:
                waiting_slot = slot
                waiting_item_id = int(item.get("item_id", index))
                break
        if waiting_slot:
            break
    if waiting_slot not in {"quantity", "temperature"}:
        raise ValueError(
            f"{row.get('id')}: unexpected synthetic waiting slot {waiting_slot}: {before_items}"
        )

    after_raw: list[dict[str, Any]] = []
    for index, previous in enumerate(before_items):
        incoming = utterance_items[index] if index < len(utterance_items) else {}
        updated = {
            "menu": previous.get("menu"),
            "temperature": previous.get("temperature"),
            "quantity": previous.get("quantity"),
        }
        for slot in ("menu", "temperature", "quantity"):
            if incoming.get(slot) is not None:
                updated[slot] = incoming.get(slot)
        after_raw.append(updated)

    after_items = normalize_items(after_raw)
    if calculate_order_status(after_items) != "VALID":
        raise ValueError(
            f"{row.get('id')}: slot context did not become valid: before={before_items}, after={after_items}"
        )

    previous_speech, _ = waiting_prompt(
        manager,
        str(row.get("user_text") or ""),
        before_items,
        waiting_slot,
        waiting_item_id,
    )
    response = render(
        manager,
        "confirm_order",
        user_text=str(row.get("user_text") or ""),
        items=after_items,
    )
    return make_completed_row(
        row,
        variant=variant,
        scenario="order_contextual_slot_answer_multiturn",
        history=[{"role": "assistant", "text": previous_speech}],
        fsm_before=f"ASK_{waiting_slot.upper()}",
        state_before_items=before_items,
        state_after_items=after_items,
        order_status="VALID",
        decision="CONFIRM_ORDER",
        response_key="confirm_order",
        response_args={},
        response=response,
        fsm_after="ORDER_CONFIRM",
        strategy="fill_explicit_slot_into_deterministic_previous_order",
    )


def build_affirm_or_deny(
    row: dict[str, Any],
    manager: ResponseManager,
    source_index: int,
    variant: int,
    *,
    intent: str,
) -> dict[str, Any]:
    before_item = complete_item(source_index, variant)
    before_items = [before_item]
    history = confirmation_history(manager, str(row.get("user_text") or ""), before_items)

    if intent == "AFFIRM":
        # Match the production OrderHandoffDecisionNode exactly: affirming the
        # order summary does not clear the active order. The robot asks one more
        # explicit finish question, and only the following AFFIRM clears it.
        after_items = deepcopy(before_items)
        decision = "ORDER_CONFIRMED"
        response_key = "ask_next_customer"
        fsm_after = "WAIT_NEXT_CUSTOMER"
        order_status = "VALID"
        strategy = "affirm_order_summary_enters_finish_confirmation"
    else:
        # The synthetic DENY context contains exactly one active item, so the
        # production AdditionalOrderDecisionNode does not need target selection.
        # Keep the order untouched and ask which slot is wrong.
        after_items = deepcopy(before_items)
        decision = "MODIFY_ORDER"
        response_key = "ask_correction_content"
        fsm_after = "ORDER_CORRECTION"
        order_status = "VALID"
        strategy = "deny_single_item_confirmation_asks_correction_content"

    response = render(
        manager,
        response_key,
        user_text=str(row.get("user_text") or ""),
        items=before_items,
    )
    return make_completed_row(
        row,
        variant=variant,
        scenario=f"{intent.lower()}_multiturn",
        history=history,
        fsm_before="ORDER_CONFIRM",
        state_before_items=before_items,
        state_after_items=after_items,
        order_status=order_status,
        decision=decision,
        response_key=response_key,
        response_args={},
        response=response,
        fsm_after=fsm_after,
        strategy=strategy,
    )


def build_cancel(
    row: dict[str, Any],
    manager: ResponseManager,
    source_index: int,
    variant: int,
) -> dict[str, Any]:
    # Use three different active-dialogue stages in training so CANCEL is
    # grounded as a command that works throughout an active order, not only at
    # final confirmation.
    stage = variant % 3
    base_item = complete_item(source_index, variant)
    raw = {
        "menu": base_item.get("menu"),
        "temperature": base_item.get("temperature"),
        "quantity": base_item.get("quantity"),
    }

    if stage == 0:
        before_items = normalize_items([raw])
        history = confirmation_history(manager, str(row.get("user_text") or ""), before_items)
        fsm_before = "ORDER_CONFIRM"
    elif stage == 1:
        raw["quantity"] = None
        before_items = normalize_items([raw])
        speech, _ = waiting_prompt(
            manager,
            str(row.get("user_text") or ""),
            before_items,
            "quantity",
        )
        history = [{"role": "assistant", "text": speech}]
        fsm_before = "ASK_QUANTITY"
    else:
        # Only dual-temperature menus can genuinely wait for temperature.
        menu = choose_menu(
            source_index,
            variant,
            required_temperature="HOT",
        )
        raw = {
            "menu": menu,
            "temperature": None,
            "quantity": choose_quantity(source_index, variant),
        }
        before_items = normalize_items([raw])
        speech, _ = waiting_prompt(
            manager,
            str(row.get("user_text") or ""),
            before_items,
            "temperature",
        )
        history = [{"role": "assistant", "text": speech}]
        fsm_before = "ASK_TEMPERATURE"

    user_text = str(row.get("user_text") or "")
    command = DialogueActResolver().resolve_command({"text": user_text})
    if command == "RESTART":
        decision = "REORDER_REQUEST"
        response_key = "restart_order"
        response_args: dict[str, Any] = {}
        fsm_after = "ORDER_LISTEN"
        strategy = "cancel_labeled_source_with_explicit_restart_command"
    else:
        decision = "CANCEL_ORDER"
        response_key = "cancel_order"
        response_args = {"active": True}
        fsm_after = "IDLE"
        strategy = "cancel_during_active_order"

    response = render(
        manager,
        response_key,
        user_text=user_text,
        items=before_items,
        response_args=response_args,
    )
    return make_completed_row(
        row,
        variant=variant,
        scenario="cancel_multiturn",
        history=history,
        fsm_before=fsm_before,
        state_before_items=before_items,
        state_after_items=[],
        order_status="NONE",
        decision=decision,
        response_key=response_key,
        response_args=response_args,
        response=response,
        fsm_after=fsm_after,
        strategy=strategy,
    )


def build_modify(
    row: dict[str, Any],
    manager: ResponseManager,
    source_index: int,
    variant: int,
) -> dict[str, Any]:
    utterance_items = deepcopy(base_target(row).get("utterance_items") or [])

    # A generic "수정할게요" with no explicit slots should enter correction
    # mode without changing any order value.
    if not utterance_items:
        before_items = [complete_item(source_index, variant)]
        response = render(
            manager,
            "ask_correction_content",
            user_text=str(row.get("user_text") or ""),
            items=before_items,
        )
        return make_completed_row(
            row,
            variant=variant,
            scenario="modify_multiturn_request_only",
            history=confirmation_history(manager, str(row.get("user_text") or ""), before_items),
            fsm_before="ORDER_CONFIRM",
            state_before_items=before_items,
            state_after_items=before_items,
            order_status="VALID",
            decision="MODIFY_ORDER",
            response_key="ask_correction_content",
            response_args={},
            response=response,
            fsm_after="ORDER_CORRECTION",
            strategy="modify_request_without_explicit_slot_change",
        )

    before_raw: list[dict[str, Any]] = []
    after_raw: list[dict[str, Any]] = []

    for item_index, incoming in enumerate(utterance_items):
        target_menu = incoming.get("menu")
        target_temp = incoming.get("temperature")
        target_qty = incoming.get("quantity")

        # Choose a resulting menu compatible with an explicit target
        # temperature.  If the user names the menu, keep that target exactly.
        resulting_menu = target_menu or choose_menu(
            source_index + item_index,
            variant,
            required_temperature=target_temp,
        )

        # Previous menu differs when menu itself is being modified.  Preserve a
        # temperature that remains legal after the menu replacement, especially
        # when the target is an ICE-only drink.
        previous_menu = (
            choose_menu(
                source_index + item_index + 1,
                variant,
                required_temperature=target_temp,
                avoid=resulting_menu,
            )
            if target_menu is not None
            else resulting_menu
        )

        if target_temp is not None:
            # For temperature correction, choose the opposite legal value where
            # possible so the synthetic context truly represents a change.
            if target_menu is None:
                resulting_menu = choose_menu(
                    source_index + item_index,
                    variant,
                    required_temperature=target_temp,
                )
                previous_menu = resulting_menu
            previous_temp = choose_temperature(
                previous_menu,
                source_index + item_index,
                variant,
                avoid=target_temp,
            )
        else:
            # If the target menu is ICE-only, the previous temperature must be
            # ICE too; otherwise carrying HOT across a menu replacement would
            # create an artificial invalid correction.
            desired_temp = "ICE" if allowed_temperatures(resulting_menu) == frozenset({"ICE"}) else None
            previous_temp = desired_temp or choose_temperature(
                previous_menu,
                source_index + item_index,
                variant,
            )

        previous_qty = choose_quantity(
            source_index + item_index,
            variant,
            avoid=target_qty,
        )

        before_raw.append({
            "menu": previous_menu,
            "temperature": previous_temp,
            "quantity": previous_qty,
        })
        after_raw.append({
            "menu": target_menu if target_menu is not None else previous_menu,
            "temperature": target_temp if target_temp is not None else previous_temp,
            "quantity": target_qty if target_qty is not None else previous_qty,
        })

    before_items = normalize_items(before_raw)
    after_items = normalize_items(after_raw)
    after_status = calculate_order_status(after_items)

    if after_status == "INVALID":
        response_key = "invalid_correction"
        decision = "MODIFY_ORDER"
        fsm_after = "ORDER_CORRECTION"
        strategy = "explicit_modify_rejected_by_menu_policy"
    elif after_status == "INCOMPLETE":
        # This should be rare because synthetic previous states fill all
        # untouched slots, but keep the rule deterministic if a future source
        # schema introduces an explicit nulling correction.
        missing_slot = None
        missing_item_id = 0
        for index, item in enumerate(after_items):
            for slot in ("menu", "quantity", "temperature"):
                if item.get(slot) is None:
                    missing_slot = slot
                    missing_item_id = int(item.get("item_id", index))
                    break
            if missing_slot:
                break
        if missing_slot is None:
            raise ValueError(f"{row.get('id')}: incomplete modify without missing slot")
        response_key = f"ask_{missing_slot}"
        decision = f"ASK_{missing_slot.upper()}"
        fsm_after = decision
        strategy = "explicit_modify_requires_followup_slot"
        _speech, response_args = waiting_prompt(
            manager,
            str(row.get("user_text") or ""),
            after_items,
            missing_slot,
            missing_item_id,
        )
        response = _speech
        return make_completed_row(
            row,
            variant=variant,
            scenario="modify_multiturn",
            history=confirmation_history(manager, str(row.get("user_text") or ""), before_items),
            fsm_before="ORDER_CONFIRM",
            state_before_items=before_items,
            state_after_items=after_items,
            order_status=after_status,
            decision=decision,
            response_key=response_key,
            response_args=response_args,
            response=response,
            fsm_after=fsm_after,
            strategy=strategy,
        )
    else:
        response_key = "confirm_order"
        decision = "CONFIRM_ORDER"
        fsm_after = "ORDER_CONFIRM"
        strategy = "apply_explicit_modify_to_synthetic_previous_order"

    response = render(
        manager,
        response_key,
        user_text=str(row.get("user_text") or ""),
        items=after_items,
    )
    return make_completed_row(
        row,
        variant=variant,
        scenario="modify_multiturn",
        history=confirmation_history(manager, str(row.get("user_text") or ""), before_items),
        fsm_before="ORDER_CONFIRM",
        state_before_items=before_items,
        state_after_items=after_items,
        order_status=after_status,
        decision=decision,
        response_key=response_key,
        response_args={},
        response=response,
        fsm_after=fsm_after,
        strategy=strategy,
    )


def build_context_variant(
    row: dict[str, Any],
    manager: ResponseManager,
    source_index: int,
    variant: int,
) -> dict[str, Any]:
    scenario = str(row.get("scenario_group") or "")
    if scenario == "order_contextual_slot_answer":
        return build_slot_answer(row, manager, source_index, variant)
    if scenario == "affirm":
        return build_affirm_or_deny(
            row, manager, source_index, variant, intent="AFFIRM"
        )
    if scenario == "deny":
        return build_affirm_or_deny(
            row, manager, source_index, variant, intent="DENY"
        )
    if scenario == "cancel":
        return build_cancel(row, manager, source_index, variant)
    if scenario == "modify":
        return build_modify(row, manager, source_index, variant)
    raise ValueError(f"{row.get('id')}: unsupported context scenario {scenario!r}")


def validate_completed(row: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    quality = row.get("label_quality") or {}
    target = row.get("target") or {}

    if not quality.get("fully_supervised"):
        errors.append("completed row must be fully_supervised")
    if quality.get("context_required"):
        errors.append("completed row cannot require context")
    if not row.get("history"):
        errors.append("completed multi-turn row must have history")
    if not isinstance(row.get("state_before"), dict):
        errors.append("completed row missing state_before")
    if not row.get("fsm_state_before"):
        errors.append("completed row missing fsm_state_before")
    if not row.get("fsm_state_after"):
        errors.append("completed row missing fsm_state_after")
    if not row.get("user_text"):
        errors.append("completed row missing user_text")
    for key in ("state_after", "decision", "response_key", "response"):
        if target.get(key) in (None, ""):
            errors.append(f"completed row missing target.{key}")

    before_items = (row.get("state_before") or {}).get("items", [])
    if not before_items:
        errors.append("synthetic context must contain an active previous order")
    if calculate_order_status(before_items) == "INVALID":
        errors.append("synthetic previous order cannot be INVALID")

    source_scenario = str(
        (row.get("context_generation") or {}).get("source_scenario") or ""
    )
    if source_scenario == "affirm":
        after_items = (target.get("state_after") or {}).get("items", [])
        if after_items != before_items:
            errors.append("AFFIRM after ORDER_CONFIRM must preserve active order")
        if target.get("decision") != "ORDER_CONFIRMED":
            errors.append("AFFIRM after ORDER_CONFIRM must emit ORDER_CONFIRMED")
        if target.get("response_key") != "ask_next_customer":
            errors.append("AFFIRM after ORDER_CONFIRM must ask finish confirmation")
        if row.get("fsm_state_after") != "WAIT_NEXT_CUSTOMER":
            errors.append("AFFIRM after ORDER_CONFIRM must enter WAIT_NEXT_CUSTOMER")

    if source_scenario == "deny":
        after_items = (target.get("state_after") or {}).get("items", [])
        if after_items != before_items:
            errors.append("bare DENY must preserve the active order")
        if target.get("decision") != "MODIFY_ORDER":
            errors.append("bare DENY must enter correction flow")
        if target.get("response_key") != "ask_correction_content":
            errors.append("single-item DENY must ask which slot is wrong")
        if row.get("fsm_state_after") != "ORDER_CORRECTION":
            errors.append("single-item DENY must enter ORDER_CORRECTION")

    if source_scenario == "cancel":
        expected_command = DialogueActResolver().resolve_command(
            {"text": row.get("user_text", "")}
        )
        if expected_command == "RESTART":
            if target.get("decision") != "REORDER_REQUEST":
                errors.append("restart wording must emit REORDER_REQUEST")
            if target.get("response_key") != "restart_order":
                errors.append("restart wording must use restart_order response")
            if row.get("fsm_state_after") != "ORDER_LISTEN":
                errors.append("restart wording must return to ORDER_LISTEN")
        else:
            if target.get("decision") != "CANCEL_ORDER":
                errors.append("pure cancel wording must emit CANCEL_ORDER")
            if row.get("fsm_state_after") != "IDLE":
                errors.append("pure cancel wording must end the active order")
    return errors


def collect_review_sample(
    generated_rows: list[dict[str, Any]],
    *,
    per_source_scenario: int = 40,
) -> list[dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in generated_rows:
        scenario = str((row.get("context_generation") or {}).get("source_scenario") or "unknown")
        if len(buckets[scenario]) < per_source_scenario:
            buckets[scenario].append(row)

    review: list[dict[str, Any]] = []
    for scenario in sorted(buckets):
        for row in buckets[scenario]:
            review.append({
                "id": row["id"],
                "source_scenario": scenario,
                "history": row["history"],
                "fsm_state_before": row["fsm_state_before"],
                "state_before": row["state_before"],
                "user_text": row["user_text"],
                "state_after": row["target"]["state_after"],
                "decision": row["target"]["decision"],
                "response_key": row["target"]["response_key"],
                "fsm_state_after": row["fsm_state_after"],
                "response": row["target"]["response"],
            })
    return review


def process_split(
    input_path: Path,
    *,
    split_name: str,
    variants: int,
    generated_output: Path,
    sft_output: Path,
    manager: ResponseManager,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    base_rows = list(iter_jsonl(input_path))
    contextual = [
        row for row in base_rows
        if bool((row.get("label_quality") or {}).get("context_required"))
    ]
    fully_supervised = [
        row for row in base_rows
        if bool((row.get("label_quality") or {}).get("fully_supervised"))
    ]

    expected = EXPECTED_CONTEXT_REQUIRED[split_name]
    if len(contextual) != expected:
        raise ValueError(
            f"{split_name}: expected {expected} context-required rows, got {len(contextual)}"
        )

    scenario_counts = Counter(str(row.get("scenario_group") or "unknown") for row in contextual)
    unexpected = set(scenario_counts) - CONTEXT_SCENARIOS
    if unexpected:
        raise ValueError(f"{split_name}: unexpected context scenarios: {sorted(unexpected)}")

    generated: list[dict[str, Any]] = []
    validation_errors = 0
    for source_index, row in enumerate(contextual):
        for variant in range(variants):
            completed = build_context_variant(
                row,
                manager,
                source_index,
                variant,
            )
            errors = validate_completed(completed)
            if errors:
                validation_errors += 1
                raise ValueError(f"{completed.get('id')}: {errors}")
            generated.append(completed)

    generated_count = write_jsonl(generated_output, generated)

    # The final SFT set replaces unresolved source rows with completed context
    # variants. Test uses one variant, preserving the original test count.
    final_rows = [*fully_supervised, *generated]
    sft_count = write_jsonl(sft_output, final_rows)

    final_partial = sum(
        1 for row in final_rows
        if bool((row.get("label_quality") or {}).get("context_required"))
    )
    if final_partial:
        raise ValueError(f"{split_name}: final SFT dataset still has {final_partial} partial rows")

    return {
        "split": split_name,
        "base_total": len(base_rows),
        "base_fully_supervised": len(fully_supervised),
        "base_context_required": len(contextual),
        "variants_per_context_row": variants,
        "generated_multiturn": generated_count,
        "final_sft_total": sft_count,
        "context_scenario_counts": dict(sorted(scenario_counts.items())),
        "generated_scenario_counts": dict(sorted(Counter(
            str(row.get("scenario_group") or "unknown") for row in generated
        ).items())),
        "decision_counts": dict(sorted(Counter(
            str((row.get("target") or {}).get("decision") or "") for row in generated
        ).items())),
        "fsm_before_counts": dict(sorted(Counter(
            str(row.get("fsm_state_before") or "") for row in generated
        ).items())),
        "validation_error_count": validation_errors,
        "final_context_required": final_partial,
    }, generated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--train-input",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_train_valid.jsonl",
    )
    parser.add_argument(
        "--test-input",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_test.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "data" / "tod",
    )
    args = parser.parse_args()

    manager = ResponseManager()
    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    train_stats, train_generated = process_split(
        args.train_input,
        split_name="train_valid",
        variants=TRAIN_CONTEXT_VARIANTS,
        generated_output=output_dir / "pumpkin_tod_v1_multiturn_train_valid.jsonl",
        sft_output=output_dir / "pumpkin_tod_v1_sft_train_valid.jsonl",
        manager=manager,
    )
    test_stats, test_generated = process_split(
        args.test_input,
        split_name="test",
        variants=TEST_CONTEXT_VARIANTS,
        generated_output=output_dir / "pumpkin_tod_v1_multiturn_test.jsonl",
        sft_output=output_dir / "pumpkin_tod_v1_sft_test.jsonl",
        manager=manager,
    )

    expected_train_generated = EXPECTED_CONTEXT_REQUIRED["train_valid"] * TRAIN_CONTEXT_VARIANTS
    expected_test_generated = EXPECTED_CONTEXT_REQUIRED["test"] * TEST_CONTEXT_VARIANTS
    if train_stats["generated_multiturn"] != expected_train_generated:
        raise ValueError("train generated count mismatch")
    if test_stats["generated_multiturn"] != expected_test_generated:
        raise ValueError("test generated count mismatch")
    if test_stats["final_sft_total"] != 1_507:
        raise ValueError(
            f"test SFT must preserve 1,507 source cases, got {test_stats['final_sft_total']}"
        )

    review_rows = collect_review_sample(train_generated)
    review_count = write_jsonl(
        output_dir / "pumpkin_tod_v1_multiturn_review_sample.jsonl",
        review_rows,
    )

    stats = {
        "schema_version": SCHEMA_VERSION,
        "llm_used_for_labels": False,
        "policy": {
            "train_context_variants": TRAIN_CONTEXT_VARIANTS,
            "test_context_variants": TEST_CONTEXT_VARIANTS,
            "test_source_count_preserved": True,
            "previous_response_source": "robot_controller.response_manager.ResponseManager",
            "order_truth_source": "canonical Structure B labels + deterministic synthetic context",
        },
        "train_valid": train_stats,
        "test": test_stats,
        "review_sample_count": review_count,
        "review_sample_policy": "first 40 deterministic examples per context source scenario",
    }
    stats_path = output_dir / "pumpkin_tod_v1_multiturn_stats.json"
    stats_path.write_text(
        json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
