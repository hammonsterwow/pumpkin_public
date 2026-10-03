from __future__ import annotations

from typing import Any

from .menu_policy import (
    MENU_ALIASES,
    SUPPORTED_MENUS,
    allowed_temperatures,
    compact_text,
)


SLOT_NAMES = ("menu", "temperature", "quantity")

# Fuzzy recovery is deliberately stricter than ordinary exact alias grounding.
# It never rewrites Whisper text and only upgrades a menu to explicit evidence
# when the NLU prediction and the local Hangul pronunciation pattern strongly
# agree. This is meant for live ASR variants such as ``카페라 때``, ``하페라떼``
# or dialectal ``깝훼라떼`` without re-introducing Whisper prompt/hotword bias.
FUZZY_MENU_MIN_INTENT_CONFIDENCE = 0.95
FUZZY_MENU_MIN_MODEL_CONFIDENCE = 0.995
FUZZY_MENU_MIN_SCORE = 0.80
FUZZY_MENU_MIN_MARGIN = 0.12
FUZZY_MENU_MAX_SYLLABLE_COST = 0.65

# Choseong indices in Unicode Hangul decomposition. Tense/aspirated members of
# the same articulation family receive a small substitution cost instead of a
# full mismatch: ㄱ/ㄲ/ㅋ, ㄷ/ㄸ/ㅌ, ㅂ/ㅃ/ㅍ, ㅅ/ㅆ, ㅈ/ㅉ/ㅊ.
_SIMILAR_INITIAL_GROUPS = (
    frozenset({0, 1, 15}),
    frozenset({3, 4, 16}),
    frozenset({7, 8, 17}),
    frozenset({9, 10}),
    frozenset({12, 13, 14}),
)

# Jungseong groups cover common Korean ASR confusions relevant to the menu
# vocabulary, especially ㅐ/ㅔ and contracted ㅙ/ㅚ/ㅞ-like realizations.
_SIMILAR_VOWEL_GROUPS = (
    frozenset({1, 5}),
    frozenset({3, 7}),
    frozenset({9, 10, 11}),
    frozenset({14, 15}),
    frozenset({5, 15}),
    frozenset({10, 15}),
)


def _refresh_item_missing_slots(item: dict[str, Any]) -> None:
    item["missing_slots"] = [slot for slot in SLOT_NAMES if item.get(slot) is None]


def _refresh_result_status(result: dict[str, Any]) -> None:
    items = result.get("items")
    if not isinstance(items, list) or not items:
        result["order_status"] = "UNPARSABLE"
        result["needs_reprompt"] = True
        return

    for item in items:
        if isinstance(item, dict):
            _refresh_item_missing_slots(item)

    has_missing_slots = any(
        item.get("missing_slots") for item in items if isinstance(item, dict)
    )
    result["order_status"] = "INCOMPLETE" if has_missing_slots else "VALID"
    result["needs_reprompt"] = has_missing_slots


def _same_confusion_group(
    first: int,
    second: int,
    groups: tuple[frozenset[int], ...],
) -> bool:
    return any(first in group and second in group for group in groups)


def _decompose_hangul_syllable(character: str) -> tuple[int, int, int] | None:
    if len(character) != 1:
        return None
    codepoint = ord(character)
    if not 0xAC00 <= codepoint <= 0xD7A3:
        return None

    syllable_index = codepoint - 0xAC00
    initial = syllable_index // 588
    vowel = (syllable_index % 588) // 28
    final = syllable_index % 28
    return initial, vowel, final


def _phonetic_syllable_cost(observed: str, expected: str) -> float:
    if observed == expected:
        return 0.0

    observed_parts = _decompose_hangul_syllable(observed)
    expected_parts = _decompose_hangul_syllable(expected)
    if observed_parts is None or expected_parts is None:
        return 1.0

    observed_initial, observed_vowel, observed_final = observed_parts
    expected_initial, expected_vowel, expected_final = expected_parts

    if observed_initial == expected_initial:
        initial_cost = 0.0
    elif _same_confusion_group(
        observed_initial,
        expected_initial,
        _SIMILAR_INITIAL_GROUPS,
    ):
        initial_cost = 0.25
    else:
        initial_cost = 1.0

    if observed_vowel == expected_vowel:
        vowel_cost = 0.0
    elif _same_confusion_group(
        observed_vowel,
        expected_vowel,
        _SIMILAR_VOWEL_GROUPS,
    ):
        vowel_cost = 0.25
    else:
        vowel_cost = 1.0

    final_cost = 0.0 if observed_final == expected_final else 1.0
    return 0.45 * initial_cost + 0.45 * vowel_cost + 0.10 * final_cost


def _fuzzy_alias_score(observed: str, expected: str) -> tuple[float, float]:
    if not observed or len(observed) != len(expected):
        return 0.0, 1.0

    costs = [
        _phonetic_syllable_cost(observed_char, expected_char)
        for observed_char, expected_char in zip(observed, expected)
    ]
    if not costs:
        return 0.0, 1.0

    score = 1.0 - (sum(costs) / len(costs))
    return max(0.0, score), max(costs)


def _best_fuzzy_menu_match(text: str, menu: str) -> dict[str, Any]:
    compact = compact_text(text)
    best = {
        "menu": menu,
        "score": 0.0,
        "max_syllable_cost": 1.0,
        "matched_text": "",
        "alias": "",
    }

    for alias in MENU_ALIASES.get(menu, ()):
        compact_alias = compact_text(alias)
        # Short aliases such as 라떼/라테 are already handled exactly and are too
        # ambiguous for fuzzy matching inside arbitrary conversational text.
        if len(compact_alias) < 4 or len(compact) < len(compact_alias):
            continue

        window_length = len(compact_alias)
        for start in range(len(compact) - window_length + 1):
            window = compact[start:start + window_length]
            score, max_cost = _fuzzy_alias_score(window, compact_alias)
            if score <= float(best["score"]):
                continue
            best = {
                "menu": menu,
                "score": score,
                "max_syllable_cost": max_cost,
                "matched_text": window,
                "alias": compact_alias,
            }

    return best


def recover_fuzzy_menu_evidence(
    text: str,
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> dict[str, Any] | None:
    """Conservatively recover one distorted menu mention from live ASR text.

    Recovery is allowed only when all independent signals agree:
    1) there is no already-grounded exact menu,
    2) NLU says ORDER with high intent confidence,
    3) exactly one item predicts a supported menu with very high menu confidence,
    4) that same menu is the best local jamo/phonetic match,
    5) the fuzzy score is high and clearly separated from the runner-up menu.

    The raw STT text is never modified. On success only ``explicit_slots`` gains
    menu evidence, so the existing grounding policy remains authoritative.
    """

    if not isinstance(explicit_slots, dict):
        return None
    if explicit_slots.get("menu") is not None:
        return None
    existing_menus = explicit_slots.get("menus")
    if isinstance(existing_menus, list) and any(existing_menus):
        return None

    if str(result.get("intent", "")).upper() != "ORDER":
        return None
    intent_confidence = float(result.get("intent_confidence") or 0.0)
    if intent_confidence < FUZZY_MENU_MIN_INTENT_CONFIDENCE:
        return None

    raw_items = result.get("items")
    items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
    if len(items) != 1:
        return None

    item = items[0]
    predicted_menu = item.get("menu")
    if predicted_menu not in SUPPORTED_MENUS:
        return None

    confidence = item.get("confidence")
    confidence = confidence if isinstance(confidence, dict) else {}
    menu_confidence = float(confidence.get("menu") or 0.0)
    active_confidence = float(confidence.get("active") or 0.0)
    if menu_confidence < FUZZY_MENU_MIN_MODEL_CONFIDENCE:
        return None
    if active_confidence and active_confidence < FUZZY_MENU_MIN_INTENT_CONFIDENCE:
        return None

    matches = [_best_fuzzy_menu_match(text, menu) for menu in SUPPORTED_MENUS]
    matches.sort(key=lambda match: float(match["score"]), reverse=True)
    if not matches:
        return None

    best = matches[0]
    runner_up_score = float(matches[1]["score"]) if len(matches) > 1 else 0.0
    best_score = float(best["score"])
    margin = best_score - runner_up_score

    if best.get("menu") != predicted_menu:
        return None
    if best_score < FUZZY_MENU_MIN_SCORE:
        return None
    if margin < FUZZY_MENU_MIN_MARGIN:
        return None
    if float(best["max_syllable_cost"]) > FUZZY_MENU_MAX_SYLLABLE_COST:
        return None

    explicit_slots["menu"] = predicted_menu
    explicit_slots["menus"] = [predicted_menu]
    return {
        "menu": predicted_menu,
        "matched_text": best["matched_text"],
        "alias": best["alias"],
        "score": round(best_score, 4),
        "margin": round(margin, 4),
        "model_menu_confidence": round(menu_confidence, 4),
        "intent_confidence": round(intent_confidence, 4),
    }


def _has_explicit_order_evidence(explicit_slots: dict[str, Any] | None) -> bool:
    return isinstance(explicit_slots, dict) and any(
        explicit_slots.get(slot) is not None
        for slot in ("menu", "temperature", "quantity")
    )


def _ground_item_hints(
    result: dict[str, Any],
    model_items: list[dict[str, Any]],
    explicit_slots: dict[str, Any],
) -> bool:
    """Materialize deterministic partial items recovered from literal text.

    ``dialogue_slots`` may detect a transcript such as
    ``한 잔이랑 바닐라라떼 15 잔`` where two quantities survived STT but only
    one menu did. The missing first menu must not cause the one-cup item to be
    silently discarded. Item hints preserve that first quantity as a partial item
    so the dialogue FSM can ask which menu it belongs to.
    """

    hints = explicit_slots.get("item_hints")
    if not isinstance(hints, list) or len(hints) <= 1:
        return False

    grounded_items: list[dict[str, Any]] = []
    for item_index, hint in enumerate(hints[:3]):
        if not isinstance(hint, dict):
            continue
        source = model_items[item_index] if item_index < len(model_items) else {}
        item = dict(source)

        previous_menu = item.get("menu")
        target_menu = hint.get("menu")
        if previous_menu is not None and previous_menu != target_menu:
            item["menu_prediction_ignored"] = previous_menu

        previous_temperature = item.get("temperature")
        target_temperature = hint.get("temperature")
        if previous_temperature is not None and previous_temperature != target_temperature:
            item["temperature_prediction_ignored"] = previous_temperature

        previous_quantity = item.get("quantity")
        target_quantity = hint.get("quantity")
        if previous_quantity is not None and previous_quantity != target_quantity:
            item["quantity_prediction_ignored"] = previous_quantity

        item["item_id"] = item_index
        item["menu"] = target_menu
        item["temperature"] = target_temperature
        item["quantity"] = target_quantity
        grounded_items.append(item)

    if not grounded_items:
        return False

    if len(model_items) > len(grounded_items):
        result["ungrounded_extra_items"] = model_items[len(grounded_items):]
    result["items"] = grounded_items
    result["literal_item_hints_applied"] = True
    _refresh_result_status(result)
    return True


def ground_order_items_to_explicit_evidence(
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> bool:
    """Prevent item-query hallucinations from becoming dialogue state.

    Structure B is intentionally allowed to model item structure, but real robot
    audio contains out-of-domain/background speech. The item-query decoder can be
    highly confident on those sentences and may activate several phantom items.

    Runtime policy therefore requires literal menu/temperature/quantity evidence
    before an ORDER frame is allowed to create order items. When explicit menu
    names are present, their count and names are authoritative. When only a
    follow-up slot such as ``세 잔이요`` is present, model-invented menu/cardinality
    is discarded and a single partial item is emitted for the FSM to merge into
    its current waiting slot.
    """

    if str(result.get("intent", "")).upper() != "ORDER":
        return False

    raw_items = result.get("items")
    items = [dict(item) for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []

    if not _has_explicit_order_evidence(explicit_slots):
        if not items:
            return False
        result["ungrounded_model_items"] = items
        result["items"] = []
        _refresh_result_status(result)
        return True

    assert isinstance(explicit_slots, dict)

    # A literal multi-quantity transcript with a dropped menu carries stronger
    # evidence than model item-query cardinality. Preserve every recoverable item
    # before applying the normal one-menu grounding path.
    if _ground_item_hints(result, items, explicit_slots):
        return True

    explicit_menus = explicit_slots.get("menus")
    if not isinstance(explicit_menus, list):
        explicit_menus = []
    explicit_menus = [str(menu) for menu in explicit_menus if menu]

    changed = False
    if explicit_menus:
        grounded_items: list[dict[str, Any]] = []
        for item_index, explicit_menu in enumerate(explicit_menus[:3]):
            source = items[item_index] if item_index < len(items) else {}
            item = dict(source)
            previous_menu = item.get("menu")
            if previous_menu not in {None, explicit_menu}:
                item["menu_prediction_ignored"] = previous_menu
            item["item_id"] = item_index
            item["menu"] = explicit_menu
            grounded_items.append(item)

        if len(grounded_items) != len(items):
            result["ungrounded_extra_items"] = items[len(grounded_items):]
            changed = True
        if grounded_items != items:
            changed = True
        items = grounded_items
        result["items"] = items
    else:
        # Slot-only utterance. Never let the model invent a menu or several items.
        source = items[0] if items else {}
        item = dict(source)
        if item.get("menu") is not None:
            item["menu_prediction_ignored"] = item.get("menu")
        item["item_id"] = 0
        item["menu"] = None
        item["temperature"] = explicit_slots.get("temperature")
        item["quantity"] = explicit_slots.get("quantity")
        result["items"] = [item]
        items = result["items"]
        changed = True

    apply_to_all = bool(explicit_slots.get("apply_to_all_items"))
    if len(items) == 1 or apply_to_all:
        for item in items:
            for slot in ("temperature", "quantity"):
                value = explicit_slots.get(slot)
                if value is None:
                    continue
                if item.get(slot) != value:
                    item[f"{slot}_prediction_ignored"] = item.get(slot)
                    item[slot] = value
                    changed = True

    if changed:
        _refresh_result_status(result)
    return changed


def reconcile_explicit_order_evidence(
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> bool:
    """Correct model items using unambiguous text evidence.

    Kept as a compatibility wrapper. New runtime behavior also grounds item
    cardinality so phantom query slots cannot enter the dialogue state.
    """

    return ground_order_items_to_explicit_evidence(result, explicit_slots)


def clear_unexpressed_temperature_predictions(
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> bool:
    """Remove unsupported inferred temperature values from choice menus.

    The item-query model may choose ICE or HOT even when the utterance contains
    no temperature expression. For menus where both temperatures are available,
    dialogue policy requires an explicit user choice. In that case the predicted
    temperature is changed back to ``None`` so Decision Node asks the user.

    ICE-only menus are not changed because their temperature is a menu policy
    default rather than a user-selectable option.
    """

    if isinstance(explicit_slots, dict) and explicit_slots.get("temperature") is not None:
        return False

    items = result.get("items")
    if not isinstance(items, list):
        return False

    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue

        menu = item.get("menu")
        if allowed_temperatures(menu) != frozenset({"ICE", "HOT"}):
            continue

        predicted_temperature = item.get("temperature")
        if predicted_temperature not in {"ICE", "HOT"}:
            continue

        item["temperature"] = None
        item["temperature_prediction_ignored"] = predicted_temperature
        changed = True

    if changed:
        _refresh_result_status(result)
    return changed


def clear_unexpressed_quantity_predictions(
    result: dict[str, Any],
    explicit_slots: dict[str, Any] | None,
) -> bool:
    """Do not accept a model-predicted quantity that was never spoken.

    Quantity is cheap and reliable to parse deterministically from Korean order
    text. A query decoder guessing ``1`` for ``아이스 아메리카노`` must therefore
    not silently turn a menu-only utterance into a one-cup order.
    """

    if isinstance(explicit_slots, dict) and explicit_slots.get("quantity") is not None:
        return False

    items = result.get("items")
    if not isinstance(items, list):
        return False

    changed = False
    for item in items:
        if not isinstance(item, dict):
            continue
        predicted_quantity = item.get("quantity")
        if predicted_quantity is None:
            continue
        item["quantity"] = None
        item["quantity_prediction_ignored"] = predicted_quantity
        changed = True

    if changed:
        _refresh_result_status(result)
    return changed
