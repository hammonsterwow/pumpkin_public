from __future__ import annotations

import re
from typing import Any

from .dialogue_slots import extract_menus, extract_temperature
from .menu_policy import MENU_ALIASES, QUANTITY_WORDS, allowed_temperatures, compact_text


# S8 keeps exception handling rule-based and separate from the learned intent.
# Invalid menu/temperature requests are still order attempts; the FSM simply
# explains the policy and returns to a fresh ORDER_LISTEN turn.

_QUANTITY_TOKENS = sorted(QUANTITY_WORDS, key=len, reverse=True)
_QUANTITY_PATTERN = re.compile(
    rf"(?:\d+|{'|'.join(re.escape(token) for token in _QUANTITY_TOKENS)})(?:잔|개|컵)"
)

_ORDER_CONTEXT_CUES = (
    "주세요",
    "줘요",
    "줘",
    "주문",
    "시켜",
    "시킬",
    "마실",
    "먹을",
    "할게",
    "할래",
)

# Expressions that do not name a drink. They are stripped only for the narrow
# unsupported-menu fallback after exact supported-menu grounding has already
# failed. This lets clear phrases such as "카푸치노 한 잔 주세요" be rejected,
# while "아이스 두 잔 주세요" still follows the normal missing-menu flow.
_GENERIC_ORDER_FRAGMENTS = (
    "부탁드립니다",
    "부탁드려요",
    "부탁해요",
    "주문해주세요",
    "주문해줘요",
    "주문해줘",
    "주문할게요",
    "주문할래요",
    "시켜주세요",
    "시켜줘요",
    "시켜줘",
    "시킬게요",
    "시킬래요",
    "마실게요",
    "먹을게요",
    "주세요",
    "줘요",
    "줘",
    "주문",
    "시켜",
    "시킬",
    "할게요",
    "할래요",
    "할게",
    "할래",
    "아이스로",
    "아이스",
    "차갑게",
    "차가운",
    "차갑",
    "시원하게",
    "시원",
    "콜드",
    "따뜻하게",
    "따뜻한",
    "따뜻",
    "따듯하게",
    "따듯",
    "뜨겁게",
    "뜨거운",
    "뜨겁",
    "핫",
    "그리고",
    "이랑",
    "하고",
    "그냥",
    "그럼",
    "저기",
    "음",
    "어",
)

_TRAILING_PARTICLES = (
    "으로요",
    "로요",
    "을요",
    "를요",
    "은요",
    "는요",
    "이요",
    "가요",
    "으로",
    "로",
    "을",
    "를",
    "은",
    "는",
    "이",
    "가",
    "도",
    "좀",
    "만",
    "요",
)


def _strip_trailing_particles(value: str) -> str:
    token = compact_text(value)
    changed = True
    while token and changed:
        changed = False
        for particle in _TRAILING_PARTICLES:
            compact_particle = compact_text(particle)
            if token.endswith(compact_particle) and len(token) > len(compact_particle):
                token = token[: -len(compact_particle)]
                changed = True
                break
    return token


def _safe_text_supported_menus(text: str) -> list[str]:
    """Find supported menu mentions without treating compound names as aliases.

    Short aliases such as ``라떼`` are valid when spoken alone, but a substring
    match would incorrectly turn an unsupported ``초코라떼`` into 카페라떼. Token
    equality is therefore preferred for short aliases. Longer, distinctive aliases
    keep a compact-text fallback for ordinary no-space ASR output.
    """

    raw_tokens = re.findall(r"[0-9A-Za-z가-힣]+", str(text))
    normalized_tokens = {
        _strip_trailing_particles(token)
        for token in raw_tokens
        if _strip_trailing_particles(token)
    }
    compact = compact_text(text)

    found: list[str] = []
    for menu, aliases in MENU_ALIASES.items():
        matched = False
        for alias in aliases:
            compact_alias = compact_text(alias)
            if not compact_alias:
                continue
            if compact_alias in normalized_tokens:
                matched = True
                break
            if len(compact_alias) >= 4 and compact_alias in compact:
                matched = True
                break
        if matched:
            found.append(menu)
    return found


def _explicit_supported_menus(nlu_result: dict[str, Any]) -> list[str]:
    explicit_slots = nlu_result.get("explicit_slots")
    if isinstance(explicit_slots, dict):
        menus = explicit_slots.get("menus")
        if isinstance(menus, list):
            supported = [str(menu) for menu in menus if menu]
            if supported:
                return supported
        menu = explicit_slots.get("menu")
        if menu:
            return [str(menu)]
    return extract_menus(str(nlu_result.get("text") or ""))


def _explicit_temperature(nlu_result: dict[str, Any]) -> str | None:
    explicit_slots = nlu_result.get("explicit_slots")
    if isinstance(explicit_slots, dict):
        temperature = explicit_slots.get("temperature")
        if temperature in {"ICE", "HOT"}:
            return str(temperature)
    return extract_temperature(str(nlu_result.get("text") or ""))


def _waiting_menu(
    current_order: dict[str, Any] | None,
    waiting_for: dict[str, Any] | None,
) -> str | None:
    if not isinstance(current_order, dict) or not isinstance(waiting_for, dict):
        return None
    try:
        target_id = int(waiting_for.get("item_id", -1))
    except (TypeError, ValueError):
        return None

    items = current_order.get("items")
    if not isinstance(items, list):
        return None
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        try:
            item_id = int(item.get("item_id", index))
        except (TypeError, ValueError):
            item_id = index
        if item_id == target_id:
            menu = item.get("menu")
            return str(menu) if menu else None
    return None


def _looks_like_order_context(text: str) -> bool:
    compact = compact_text(text)
    if not compact:
        return False
    if any(cue in compact for cue in _ORDER_CONTEXT_CUES):
        return True
    if _QUANTITY_PATTERN.search(compact):
        return True
    return extract_temperature(text) is not None


def _unsupported_menu_residual(text: str) -> str:
    residual = compact_text(text)
    if not residual:
        return ""

    # Remove menu aliases only from the residual candidate. If an unsupported
    # compound contains a short alias (e.g. 초코라떼), the unknown prefix remains
    # and still causes rejection instead of silently becoming 카페라떼.
    aliases = sorted(
        {
            compact_text(alias)
            for aliases in MENU_ALIASES.values()
            for alias in aliases
            if compact_text(alias)
        },
        key=len,
        reverse=True,
    )
    for alias in aliases:
        residual = residual.replace(alias, "")

    residual = _QUANTITY_PATTERN.sub("", residual)
    for fragment in sorted(_GENERIC_ORDER_FRAGMENTS, key=len, reverse=True):
        residual = residual.replace(compact_text(fragment), "")

    return _strip_trailing_particles(residual)


def detect_order_exception(
    nlu_result: dict[str, Any],
    *,
    state: str,
    current_order: dict[str, Any] | None = None,
    waiting_for: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return one narrow S8 exception without mutating dialogue state.

    Supported cases:
    - HOT requested for an ICE-only menu (레몬에이드/딸기스무디),
    - a clear order/menu-answer containing no supported menu name.

    Generic slot-only utterances such as "아이스 두 잔 주세요" are deliberately
    not labeled as unsupported menus; the existing FSM should ask which menu.
    """

    text = str(nlu_result.get("text") or "")
    menus = _explicit_supported_menus(nlu_result)
    safe_text_menus = _safe_text_supported_menus(text)
    temperature = _explicit_temperature(nlu_result)

    temperature_menus = list(menus)
    if not temperature_menus and str(state) == "ASK_TEMPERATURE":
        waiting_menu = _waiting_menu(current_order, waiting_for)
        if waiting_menu:
            temperature_menus = [waiting_menu]

    if temperature is not None:
        for menu in temperature_menus:
            allowed = allowed_temperatures(menu)
            if allowed and temperature not in allowed:
                return {
                    "kind": "UNSUPPORTED_TEMPERATURE_FOR_MENU",
                    "menu": menu,
                    "temperature": temperature,
                }

    # Only textually safe supported-menu evidence suppresses the unsupported-menu
    # fallback. This prevents a short alias hidden inside an unsupported compound
    # (e.g. 초코라떼 -> 라떼) from bypassing S8.
    if safe_text_menus:
        return None

    state_key = str(state or "").upper()
    expecting_menu = state_key == "ASK_MENU"
    intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
    confidence = float(
        nlu_result.get("confidence")
        or nlu_result.get("intent_confidence")
        or 0.0
    )

    if not expecting_menu:
        if intent != "ORDER" or confidence < 0.75:
            return None
        if not _looks_like_order_context(text):
            return None

    residual = _unsupported_menu_residual(text)
    if len(residual) < 2:
        return None

    return {
        "kind": "UNSUPPORTED_MENU",
        "observed_text": residual,
    }
