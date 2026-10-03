from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

SUPPORTED_MENUS = (
    "아메리카노",
    "카페라떼",
    "바닐라라떼",
    "레몬에이드",
    "딸기스무디",
)
MAX_QUANTITY = 20

MENU_ALIASES = {
    "아메리카노": ("아메리카노", "아메", "아아", "뜨아"),
    "카페라떼": ("카페라떼", "카페라테", "카페라때", "라떼", "라테"),
    "바닐라라떼": (
        "바닐라라떼",
        "바닐라라테",
        "바닐라떼",
        "바닐라테",
    ),
    "레몬에이드": ("레몬에이드", "레모네이드"),
    "딸기스무디": ("딸기스무디",),
}

MENU_TEMPERATURE_POLICY = {
    "아메리카노": frozenset({"ICE", "HOT"}),
    "카페라떼": frozenset({"ICE", "HOT"}),
    "바닐라라떼": frozenset({"ICE", "HOT"}),
    "레몬에이드": frozenset({"ICE"}),
    "딸기스무디": frozenset({"ICE"}),
}

TEMPERATURE_TEXT_PATTERNS = {
    "ICE": (
        r"아이스",
        r"차갑",
        r"차가운",
        r"찬\s*거",
        r"시원",
        r"콜드",
        r"냉\s*으로",
        r"아아",
    ),
    "HOT": (
        r"따뜻",
        r"따듯",
        r"뜨겁",
        r"뜨거운",
        r"핫",
        r"온\s*(?:거|으로)",
        r"뜨아",
    ),
}

TEMPERATURE_ALIASES = {
    "ICE": "ICE",
    "ICED": "ICE",
    "COLD": "ICE",
    "아이스": "ICE",
    "차갑게": "ICE",
    "차가운": "ICE",
    "찬거": "ICE",
    "시원하게": "ICE",
    "냉으로": "ICE",
    "HOT": "HOT",
    "WARM": "HOT",
    "따뜻하게": "HOT",
    "따뜻한": "HOT",
    "따듯하게": "HOT",
    "뜨겁게": "HOT",
    "뜨거운": "HOT",
    "핫": "HOT",
    "온으로": "HOT",
    "NONE": None,
}

QUANTITY_WORDS = {
    "한": 1,
    "하나": 1,
    "두": 2,
    "둘": 2,
    "세": 3,
    "셋": 3,
    "네": 4,
    "넷": 4,
    "다섯": 5,
    "여섯": 6,
    "일곱": 7,
    "여덟": 8,
    "아홉": 9,
    "열": 10,
    "열한": 11,
    "열하나": 11,
    "열두": 12,
    "열둘": 12,
    "열세": 13,
    "열셋": 13,
    "열네": 14,
    "열넷": 14,
    "열다섯": 15,
    "열여섯": 16,
    "열일곱": 17,
    "열여덟": 18,
    "열아홉": 19,
    "스무": 20,
    "스물": 20,
}

MODEL_MENU_LABELS = frozenset({"NONE", *SUPPORTED_MENUS})
MODEL_TEMPERATURE_LABELS = frozenset({"NONE", "ICE", "HOT"})
MODEL_QUANTITY_LABELS = frozenset(
    {"NONE", *(str(quantity) for quantity in range(1, MAX_QUANTITY + 1))}
)


def compact_text(value: Any) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(value)).lower()


_MENU_ALIAS_LOOKUP = {
    compact_text(alias): menu
    for menu, aliases in MENU_ALIASES.items()
    for alias in aliases
}
_TEMPERATURE_ALIAS_LOOKUP = {
    compact_text(alias): temperature
    for alias, temperature in TEMPERATURE_ALIASES.items()
}


def normalize_menu(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return _MENU_ALIAS_LOOKUP.get(compact_text(value))


def normalize_temperature(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return _TEMPERATURE_ALIAS_LOOKUP.get(compact_text(value))


def normalize_quantity(value: Any) -> int | None:
    if value is None or value == "":
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, int):
        quantity = value
    else:
        token = compact_text(value)
        token = re.sub(r"(잔|개|컵)$", "", token)
        if token.isdigit():
            quantity = int(token)
        else:
            quantity = QUANTITY_WORDS.get(token, 0)

    return quantity if 1 <= quantity <= MAX_QUANTITY else None


def allowed_temperatures(menu: Any) -> frozenset[str]:
    normalized_menu = normalize_menu(menu)
    if normalized_menu is None:
        return frozenset()
    return MENU_TEMPERATURE_POLICY[normalized_menu]


def default_temperature(menu: Any) -> str | None:
    allowed = allowed_temperatures(menu)
    if allowed == frozenset({"ICE"}):
        return "ICE"
    return None


def is_temperature_allowed(menu: Any, temperature: Any) -> bool:
    normalized_menu = normalize_menu(menu)
    normalized_temperature = normalize_temperature(temperature)
    if normalized_menu is None or normalized_temperature is None:
        return False
    return normalized_temperature in MENU_TEMPERATURE_POLICY[normalized_menu]


def _extract_label_set(
    label_maps: Mapping[str, Any],
    task: str,
) -> frozenset[str]:
    task_map = label_maps.get(task)
    if not isinstance(task_map, Mapping):
        return frozenset()

    id_to_label = task_map.get("id2label")
    if isinstance(id_to_label, Mapping):
        return frozenset(str(label) for label in id_to_label.values())
    if isinstance(id_to_label, (list, tuple)):
        return frozenset(str(label) for label in id_to_label)
    return frozenset()


def validate_nlu_label_maps(label_maps: Mapping[str, Any]) -> list[str]:
    expected_by_task = {
        "menu": MODEL_MENU_LABELS,
        "temperature": MODEL_TEMPERATURE_LABELS,
        "quantity": MODEL_QUANTITY_LABELS,
    }
    errors: list[str] = []

    for task, expected in expected_by_task.items():
        actual = _extract_label_set(label_maps, task)
        if actual == expected:
            continue

        missing = sorted(expected - actual)
        unexpected = sorted(actual - expected)
        details: list[str] = []
        if missing:
            details.append(f"missing={missing}")
        if unexpected:
            details.append(f"unexpected={unexpected}")
        if not details:
            details.append("id2label is missing")
        errors.append(f"{task}: {', '.join(details)}")

    return errors
