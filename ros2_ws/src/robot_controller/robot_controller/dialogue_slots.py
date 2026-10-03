from __future__ import annotations

import re
from typing import Any

from .menu_policy import (
    MAX_QUANTITY,
    MENU_ALIASES,
    QUANTITY_WORDS,
    TEMPERATURE_TEXT_PATTERNS,
    compact_text,
)

# ``아아`` and ``뜨아`` are handled separately because they are ambiguous in
# live conversational audio. The remaining temperature expressions are safe to
# match normally.
_SAFE_ICE_PATTERNS = tuple(
    pattern for pattern in TEMPERATURE_TEXT_PATTERNS["ICE"] if pattern != r"아아"
)
_SAFE_HOT_PATTERNS = tuple(
    pattern for pattern in TEMPERATURE_TEXT_PATTERNS["HOT"] if pattern != r"뜨아"
)
ICE_PATTERN = re.compile("|".join(_SAFE_ICE_PATTERNS))
HOT_PATTERN = re.compile("|".join(_SAFE_HOT_PATTERNS))
_QUANTITY_TOKENS = sorted(QUANTITY_WORDS, key=len, reverse=True)
_QUANTITY_TOKEN_PATTERN = "|".join(
    [r"\d+", *(re.escape(token) for token in _QUANTITY_TOKENS)]
)
ALL_ITEMS_PATTERN = re.compile(
    r"(둘\s*다|두\s*(?:개|잔)?\s*다|모두|전부|각각|"
    rf"(?:{_QUANTITY_TOKEN_PATTERN})\s*(?:잔|개|컵)?\s*씩)"
)
EACH_QUANTITY_PATTERN = re.compile(
    rf"(?P<number>{_QUANTITY_TOKEN_PATTERN})\s*(?:잔|개|컵)?\s*씩"
)
QUANTITY_PATTERN = re.compile(
    rf"(?P<number>{_QUANTITY_TOKEN_PATTERN})\s*(?:잔|개|컵)"
)
BARE_QUANTITY_PATTERN = re.compile(
    rf"(?<![0-9A-Za-z가-힣])"
    rf"(?P<number>{_QUANTITY_TOKEN_PATTERN})"
    rf"(?=\s*(?:이요|요|주세요|$))"
)
COMPACT_QUANTITY_PATTERN = re.compile(
    rf"(?P<number>{_QUANTITY_TOKEN_PATTERN})(?:잔|개|컵)"
)

# Live ReSpeaker + Faster-Whisper occasionally returns these exact strings for
# short HOT answers. Keep this list deliberately narrow: only full-utterance
# forms observed in physical tests are recovered, so unrelated longer sentences
# are never globally reinterpreted as a temperature choice.
_LIVE_HOT_STT_ALIASES = frozenset({
    "하세요로",
    "하세요로주세요",
    "하세로",
    "하세로주세요",
    "드신걸로",
    "드신걸로주세요",
    "뜨신걸로",
    "뜨신걸로주세요",
})

# Exact short-answer artifacts observed with the physical ReSpeaker and
# Faster-Whisper when the customer said "세 잔". These are not added to the
# global quantity grammar: recovery is used only while the FSM is explicitly
# waiting for a quantity, so unrelated words such as "채점" cannot create an
# order from the normal listening state.
_LIVE_THREE_QUANTITY_STT_ALIASES = frozenset({
    "세전",
    "세전이요",
    "세전세전이요",
    "새잔",
    "새잔이요",
    "새해잔",
    "새해쟌",
    "세잠",
    "세잠이요",
    "세점",
    "체점",
    "체점이요",
    "3단",
    "3단이요",
    "삼단",
    "삼단이요",
})

# ``아아``/``뜨아`` are convenient order aliases, but ``아아`` is also a very
# common hesitation/interjection in live microphone speech. Do not treat it as a
# menu merely because those two syllables occurred somewhere in a long sentence.
_AMBIGUOUS_SHORT_MENU_ALIASES = frozenset({"아아", "뜨아"})
_ORDER_CONTEXT_PATTERN = re.compile(
    r"(주문|주세요|줘요|줘|잔|개|컵|마실|먹을|시킬|할게|할래|"
    r"아이스|차갑|따뜻|뜨겁|핫|"
    rf"(?:{_QUANTITY_TOKEN_PATTERN})\s*(?:잔|개|컵))"
)

# Correction phrases are interpreted before the generic explicit-slot grounding
# step. Without this, ``A 말고 B`` expressions can incorrectly ground the source
# value instead of the requested replacement target.
_CORRECTION_CUES = (
    "말고",
    "대신",
    "아니고",
    "아니라",
    "바꿔",
    "바꿀",
    "변경",
    "수정",
)
_MENU_CORRECTION_CUES = _CORRECTION_CUES
_QUANTITY_CORRECTION_CUES = _CORRECTION_CUES


def _allow_ambiguous_short_alias(text: str, alias: str) -> bool:
    compact = compact_text(text)
    if compact == compact_text(alias):
        return True

    # The abbreviation itself must look like a token/particle-attached token,
    # not an arbitrary substring of another Korean word.
    alias_match = re.search(
        rf"(?<![0-9A-Za-z가-힣]){re.escape(alias)}(?=\s|[,.!?]|$|은|는|이|가|을|를|로|요)",
        text,
    )
    if alias_match is None:
        return False
    return _ORDER_CONTEXT_PATTERN.search(text) is not None


def _ambiguous_alias_position(text: str, alias: str) -> int | None:
    if not _allow_ambiguous_short_alias(text, alias):
        return None
    match = re.search(re.escape(alias), text)
    return match.start() if match is not None else None


def _compact_occurrences(text: str, token: str):
    """Yield every non-empty token occurrence in compact-text coordinates."""

    if not token:
        return
    start = 0
    while True:
        position = text.find(token, start)
        if position < 0:
            return
        yield position
        start = position + 1


def _quantity_value(token: str) -> int | None:
    quantity = int(token) if token.isdigit() else QUANTITY_WORDS.get(token)
    if quantity is None:
        return None
    return quantity if 1 <= quantity <= MAX_QUANTITY else None


def _menu_span(text: str, menu: str) -> tuple[int, int] | None:
    """Return the best compact-text span for one canonical menu mention."""

    compact = compact_text(text)
    candidates: list[tuple[int, int]] = []
    for alias in MENU_ALIASES.get(menu, ()):
        if (
            alias in _AMBIGUOUS_SHORT_MENU_ALIASES
            and not _allow_ambiguous_short_alias(text, alias)
        ):
            continue
        compact_alias = compact_text(alias)
        for position in _compact_occurrences(compact, compact_alias):
            candidates.append((position, position + len(compact_alias)))

    if not candidates:
        return None
    candidates.sort(key=lambda span: (span[0], -(span[1] - span[0])))
    return candidates[0]


def _quantity_mentions_with_spans(text: str) -> list[tuple[int, int, int]]:
    compact = compact_text(text)
    mentions: list[tuple[int, int, int]] = []
    for match in COMPACT_QUANTITY_PATTERN.finditer(compact):
        quantity = _quantity_value(match.group("number"))
        if quantity is None:
            continue
        mentions.append((match.start(), match.end(), quantity))
    return mentions


def _quantity_for_single_menu(
    text: str,
    menu: str,
    quantities: list[int],
) -> int | None:
    """Prefer the quantity syntactically attached to the only recognized menu."""

    if not quantities:
        return None
    if len(quantities) == 1:
        return quantities[0]

    menu_span = _menu_span(text, menu)
    mentions = _quantity_mentions_with_spans(text)
    if menu_span is None or not mentions:
        return quantities[0]

    menu_start, menu_end = menu_span
    following = [mention for mention in mentions if mention[0] >= menu_end]
    if following:
        following.sort(key=lambda mention: mention[0])
        return following[0][2]

    preceding = [mention for mention in mentions if mention[1] <= menu_start]
    if preceding:
        preceding.sort(key=lambda mention: mention[1], reverse=True)
        return preceding[0][2]

    return quantities[0]


def _item_hints_for_single_menu_multi_quantity(
    text: str,
    menu: str,
    selected_quantity: int | None,
) -> list[dict[str, Any]]:
    """Preserve quantities whose menu disappeared during STT.

    Example live transcript::

        한 잔이랑 바닐라라떼 15 잔

    The one-cup item cannot safely be discarded: the customer's first menu may
    have been lost by Whisper. Preserve it as a partial item with ``menu=None``
    so the FSM asks for that missing menu, while attaching 15 to 바닐라라떼.
    This recovery is intentionally limited to one surviving menu plus multiple
    explicit unit-bearing quantities.
    """

    if selected_quantity is None:
        return []
    menu_span = _menu_span(text, menu)
    mentions = _quantity_mentions_with_spans(text)
    if menu_span is None or len(mentions) <= 1:
        return []

    menu_start, menu_end = menu_span
    selected_index: int | None = None
    following_indexes = [
        index for index, mention in enumerate(mentions) if mention[0] >= menu_end
    ]
    if following_indexes:
        selected_index = following_indexes[0]
    else:
        preceding_indexes = [
            index for index, mention in enumerate(mentions) if mention[1] <= menu_start
        ]
        if preceding_indexes:
            selected_index = preceding_indexes[-1]

    if selected_index is None:
        return []

    events: list[tuple[int, dict[str, Any]]] = [
        (
            menu_start,
            {
                "menu": menu,
                "temperature": None,
                "quantity": selected_quantity,
            },
        )
    ]
    for index, mention in enumerate(mentions):
        if index == selected_index:
            continue
        events.append(
            (
                mention[0],
                {
                    "menu": None,
                    "temperature": None,
                    "quantity": mention[2],
                },
            )
        )

    events.sort(key=lambda event: event[0])
    return [item for _, item in events[:3]]


def extract_menus(text: str) -> list[str]:
    """Return explicitly mentioned menus in utterance order.

    Menu aliases can be nested. In particular ``라떼`` is a valid alias for
    ``카페라떼`` but is also a substring of ``바닐라라떼`` and the common STT
    spelling ``바닐라떼``. A plain substring search therefore used to turn a
    vanilla-latte utterance into a phantom cafe-latte mention. Prefer the longest
    alias at each text position and reject every later alias whose character span
    overlaps a menu that was already accepted.
    """

    compact = compact_text(text)
    candidates: list[tuple[int, int, str]] = []

    for menu, aliases in MENU_ALIASES.items():
        for alias in aliases:
            if (
                alias in _AMBIGUOUS_SHORT_MENU_ALIASES
                and not _allow_ambiguous_short_alias(text, alias)
            ):
                continue

            compact_alias = compact_text(alias)
            for position in _compact_occurrences(compact, compact_alias):
                candidates.append((position, position + len(compact_alias), menu))

    # Earlier mentions win; aliases beginning at the same position prefer the
    # longer span (e.g. 아메리카노 over 아메). Because candidates are processed
    # left-to-right, overlap with an accepted span means the candidate is merely
    # a substring alias of that already accepted explicit menu.
    candidates.sort(key=lambda candidate: (candidate[0], -(candidate[1] - candidate[0])))

    accepted: list[tuple[int, int, str]] = []
    seen_menus: set[str] = set()
    for start, end, menu in candidates:
        if menu in seen_menus:
            continue
        if any(start < accepted_end and end > accepted_start for accepted_start, accepted_end, _ in accepted):
            continue
        accepted.append((start, end, menu))
        seen_menus.add(menu)

    accepted.sort(key=lambda candidate: candidate[0])
    return [menu for _, _, menu in accepted]


def extract_menu(text: str) -> str | None:
    menus = extract_menus(text)
    return menus[0] if menus else None


def extract_menu_correction(text: str, menus: list[str] | None = None) -> dict[str, Any] | None:
    """Parse a natural-language menu replacement.

    Examples:
    - ``카페라떼 말고 바닐라라떼요`` -> from=카페라떼, to=바닐라라떼
    - ``아메리카노를 딸기스무디로 바꿀게요`` -> from=아메리카노, to=딸기스무디
    - ``메뉴를 바닐라떼로 바꿀게요`` -> from=None, to=바닐라라떼
    """

    compact = compact_text(text)
    if not any(cue in compact for cue in _MENU_CORRECTION_CUES):
        return None

    mentioned = list(menus if menus is not None else extract_menus(text))
    if not mentioned:
        return None

    if len(mentioned) >= 2:
        return {
            "slot": "menu",
            "from": mentioned[0],
            "to": mentioned[-1],
        }

    return {
        "slot": "menu",
        "from": None,
        "to": mentioned[0],
    }


def extract_temperature(text: str) -> str | None:
    candidates: list[tuple[int, str]] = []
    ice_match = ICE_PATTERN.search(text)
    hot_match = HOT_PATTERN.search(text)
    if ice_match:
        candidates.append((ice_match.start(), "ICE"))
    if hot_match:
        candidates.append((hot_match.start(), "HOT"))

    ice_alias_position = _ambiguous_alias_position(text, "아아")
    hot_alias_position = _ambiguous_alias_position(text, "뜨아")
    if ice_alias_position is not None:
        candidates.append((ice_alias_position, "ICE"))
    if hot_alias_position is not None:
        candidates.append((hot_alias_position, "HOT"))

    if candidates:
        candidates.sort(key=lambda candidate: candidate[0])
        return candidates[0][1]

    if compact_text(text) in _LIVE_HOT_STT_ALIASES:
        return "HOT"
    return None


def recover_live_quantity_answer(text: str) -> int | None:
    """Recover a known physical-ASR quantity artifact from a short answer."""

    compact = compact_text(text)
    if compact in _LIVE_THREE_QUANTITY_STT_ALIASES:
        return 3
    if re.fullmatch(r"(?:세전(?:이요|요)?){1,3}", compact):
        return 3
    return None


def extract_quantities(text: str) -> list[int]:
    """Return explicitly mentioned quantities in utterance order.

    ``QUANTITY_PATTERN`` covers the normal ``N잔/개/컵`` forms. Bare quantities
    are only used when no unit-bearing quantity exists, matching the historical
    behavior while allowing correction phrases to preserve both source and target.
    """

    quantities: list[int] = []
    for match in QUANTITY_PATTERN.finditer(text):
        quantity = _quantity_value(match.group("number"))
        if quantity is not None:
            quantities.append(quantity)

    if quantities:
        return quantities

    match = EACH_QUANTITY_PATTERN.search(text) or BARE_QUANTITY_PATTERN.search(text)
    if not match:
        return []
    quantity = _quantity_value(match.group("number"))
    return [quantity] if quantity is not None else []


def extract_quantity_correction(
    text: str,
    quantities: list[int] | None = None,
) -> dict[str, Any] | None:
    """Parse natural quantity replacements such as ``3잔 말고 5잔``.

    Two mentioned quantities preserve an explicit source -> target relationship.
    A one-quantity correction such as ``5잔으로 바꿔줘`` leaves the source empty;
    a single-item order can still apply that target safely.
    """

    compact = compact_text(text)
    if not any(cue in compact for cue in _QUANTITY_CORRECTION_CUES):
        return None

    mentioned = list(quantities if quantities is not None else extract_quantities(text))
    if not mentioned:
        return None

    if len(mentioned) >= 2:
        return {
            "slot": "quantity",
            "from": mentioned[0],
            "to": mentioned[-1],
        }

    return {
        "slot": "quantity",
        "from": None,
        "to": mentioned[0],
    }


def extract_quantity(text: str) -> int | None:
    quantities = extract_quantities(text)
    correction = extract_quantity_correction(text, quantities)
    if correction is not None and correction.get("to") is not None:
        return int(correction["to"])
    return quantities[0] if quantities else None


def extract_explicit_slots(text: str) -> dict[str, Any]:
    """Return values that are directly expressed in one utterance.

    Menu defaults and option validation are deliberately not applied here.
    ``order_schema`` applies the shared menu policy after model and follow-up
    values are converted to the same item schema.

    A group expression such as ``둘 다``, ``모두``, ``각각`` or ``하나씩``
    adds ``apply_to_all_items``. The dialogue manager may then apply an
    explicitly stated quantity or temperature to every current order item.

    Replacement utterances ground the target value while ``correction`` keeps
    the source and target relationship. This prevents explicit grounding from
    overwriting the requested replacement with the first value in the sentence.
    """

    menus = extract_menus(text)
    menu_correction = extract_menu_correction(text, menus)
    grounded_menus = menus
    if menu_correction is not None and menu_correction.get("to"):
        grounded_menus = [str(menu_correction["to"])]

    quantities = extract_quantities(text)
    quantity_correction = extract_quantity_correction(text, quantities)
    quantity = quantities[0] if quantities else None
    if quantity_correction is not None and quantity_correction.get("to") is not None:
        quantity = int(quantity_correction["to"])
    elif len(grounded_menus) == 1 and len(quantities) > 1:
        quantity = _quantity_for_single_menu(
            text,
            grounded_menus[0],
            quantities,
        )

    temperature = extract_temperature(text)
    slots: dict[str, Any] = {
        "menu": grounded_menus[0] if grounded_menus else None,
        "menus": grounded_menus,
        "temperature": temperature,
        "quantity": quantity,
    }

    # Preserve a likely STT-dropped item only when no global temperature or
    # correction expression makes scope ambiguous. The production NLU
    # postprocessor consumes these item hints as authoritative literal evidence.
    if (
        menu_correction is None
        and quantity_correction is None
        and temperature is None
        and len(grounded_menus) == 1
        and len(quantities) > 1
    ):
        item_hints = _item_hints_for_single_menu_multi_quantity(
            text,
            grounded_menus[0],
            quantity,
        )
        if len(item_hints) > 1:
            slots["item_hints"] = item_hints

    correction = menu_correction or quantity_correction
    if correction is not None:
        slots["correction"] = correction
    if ALL_ITEMS_PATTERN.search(text):
        slots["apply_to_all_items"] = True
    return slots


def has_explicit_slots(slots: dict[str, Any] | None) -> bool:
    return isinstance(slots, dict) and any(
        slots.get(slot) is not None for slot in ("menu", "temperature", "quantity")
    )

