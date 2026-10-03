#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path

CHOICE_TEMP_MENUS = {"아메리카노", "카페라떼", "바닐라라떼"}
FIXED_ICE_MENUS = {"레몬에이드", "딸기스무디"}
ALL_MENUS = sorted(CHOICE_TEMP_MENUS | FIXED_ICE_MENUS)

MENU_SURFACE = {
    "아메리카노": ["아메리카노", "아메", "아아", "뜨아"],
    "카페라떼": ["카페라떼", "라떼", "카페라테"],
    "바닐라라떼": ["바닐라라떼", "바닐라 라떼", "바닐라라테"],
    "레몬에이드": ["레몬에이드", "레몬 에이드"],
    "딸기스무디": ["딸기스무디", "딸기 스무디"],
}
QUANTITY_SURFACE = {
    1: ["한 잔", "하나", "1잔"],
    2: ["두 잔", "둘", "2잔"],
    3: ["세 잔", "셋", "3잔"],
    4: ["네 잔", "넷", "4잔"],
}
TEMPERATURE_SURFACE = {
    "ICE": ["아이스", "차갑게", "시원하게"],
    "HOT": ["따뜻하게", "뜨겁게", "핫으로"],
}
CONNECTORS = ["이랑", "하고", ",", " 그리고 ", "에다가", "랑"]
ENDINGS = [" 주세요", " 부탁드려요", " 주문할게요", " 주세요.", " 부탁해요", "요"]
PREFIXES = ["", "저는 ", "음 ", "이번에는 ", "혹시 "]


def validate_item(item: dict) -> list[str]:
    errors: list[str] = []
    missing: list[str] = []
    menu = item.get("menu")
    quantity = item.get("quantity")
    temperature = item.get("temperature")

    if menu is None:
        missing.append("menu")
        errors.append("MISSING_MENU")
    if quantity is None:
        missing.append("quantity")
        errors.append("MISSING_QUANTITY")
    elif not isinstance(quantity, (int, float)) or quantity <= 0 or quantity > 20:
        errors.append("INVALID_QUANTITY")

    if menu in CHOICE_TEMP_MENUS and temperature is None:
        missing.append("temperature")
        errors.append("MISSING_TEMPERATURE")
    elif menu in FIXED_ICE_MENUS:
        if temperature is None:
            item["temperature"] = "ICE"
        elif temperature != "ICE":
            errors.append("TEMPERATURE_NOT_ALLOWED")
    elif menu is not None and menu not in ALL_MENUS:
        errors.append("UNKNOWN_MENU")

    item["missing_slots"] = missing
    item["validation_errors"] = errors
    return errors


def apply_order_status(record: dict) -> dict:
    if record.get("intent") != "ORDER":
        record["order_status"] = None
        record["validation_errors"] = []
        return record

    items = record.get("items") or []
    if not items:
        record["order_status"] = "UNPARSABLE"
        record["validation_errors"] = ["NO_ORDER_ITEM"]
        return record

    errors: list[str] = []
    for index, item in enumerate(items):
        item["item_id"] = index
        errors.extend(validate_item(item))

    errors = list(dict.fromkeys(errors))
    if any(error in errors for error in ("TEMPERATURE_NOT_ALLOWED", "UNKNOWN_MENU", "INVALID_QUANTITY")):
        status = "OUT_OF_POLICY"
    elif any(error.startswith("CONFLICT") or error == "AMBIGUOUS_ITEM_LINK" for error in errors):
        status = "CONFLICT"
    elif any(error.startswith("MISSING_") for error in errors):
        status = "INCOMPLETE"
    else:
        status = "VALID"

    record["order_status"] = status
    record["validation_errors"] = errors
    return record


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def choose_temperature(menu: str) -> str:
    return "ICE" if menu in FIXED_ICE_MENUS else random.choice(["ICE", "HOT"])


def make_item_phrase(menu: str, quantity: int, temperature: str, missing: set[str]) -> str:
    aliases = MENU_SURFACE[menu]
    if menu == "아메리카노":
        aliases = [
            alias for alias in aliases
            if not ((alias == "아아" and temperature != "ICE") or (alias == "뜨아" and temperature != "HOT"))
        ]
    alias = random.choice(aliases)
    parts: list[str] = []
    if "temperature" not in missing and menu in CHOICE_TEMP_MENUS and alias not in {"아아", "뜨아"}:
        parts.append(random.choice(TEMPERATURE_SURFACE[temperature]))
    parts.append(alias)
    if "quantity" not in missing:
        parts.append(random.choice(QUANTITY_SURFACE[quantity]))
    return " ".join(parts)


def make_synthetic(index: int, incomplete: bool) -> dict:
    item_count = random.choices([2, 3], [0.82, 0.18])[0]
    menus = random.sample(ALL_MENUS, item_count)
    candidates = [
        (item_index, slot)
        for item_index, menu in enumerate(menus)
        for slot in (["quantity", "temperature"] if menu in CHOICE_TEMP_MENUS else ["quantity"])
    ]
    missing_plan: set[tuple[int, str]] = set()
    if incomplete:
        count = min(len(candidates), random.choices([1, 2, 3], [0.5, 0.4, 0.1])[0])
        missing_plan = set(random.sample(candidates, count))

    items: list[dict] = []
    phrases: list[str] = []
    for item_index, menu in enumerate(menus):
        quantity = random.randint(1, 4)
        temperature = choose_temperature(menu)
        missing = {slot for index_value, slot in missing_plan if index_value == item_index}
        item = {
            "item_id": item_index,
            "menu": menu,
            "quantity": None if "quantity" in missing else quantity,
            "temperature": None if "temperature" in missing else temperature,
        }
        validate_item(item)
        items.append(item)
        phrases.append(make_item_phrase(menu, quantity, temperature, missing))

    text = random.choice(PREFIXES) + phrases[0]
    for phrase in phrases[1:]:
        connector = random.choice(CONNECTORS)
        text += (", " if connector == "," else connector) + phrase if connector in {",", " 그리고 "} else f" {connector} {phrase}"
    text += random.choice(ENDINGS)

    record = {
        "text": text.strip(),
        "intent": "ORDER",
        "items": items,
        "source": {"split": "synthetic", "row": index + 1, "generator": "complex_order_v1"},
        "synthetic": True,
        "synthetic_type": "complex_incomplete" if incomplete else "complex_complete",
    }
    return apply_order_status(record)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--train", required=True)
    parser.add_argument("--valid", required=True)
    parser.add_argument("--test", required=True)
    parser.add_argument("--output", default="data/merged_structure_b_v2.jsonl")
    parser.add_argument("--synthetic-count", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20260703)
    args = parser.parse_args()

    random.seed(args.seed)
    records: list[dict] = []
    for split, path in (("train", args.train), ("valid", args.valid), ("test", args.test)):
        for record in load_jsonl(Path(path)):
            source = record.setdefault("source", {})
            source.setdefault("split", split)
            records.append(apply_order_status(record))

    existing_texts = {record.get("text", "") for record in records}
    synthetic: list[dict] = []
    complete_target = args.synthetic_count // 2
    while len(synthetic) < args.synthetic_count:
        incomplete = len(synthetic) >= complete_target
        record = make_synthetic(len(synthetic), incomplete)
        if record["text"] in existing_texts:
            continue
        existing_texts.add(record["text"])
        synthetic.append(record)

    records.extend(synthetic)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    statistics = {
        "schema_version": "structure_b_v2",
        "total_rows": len(records),
        "synthetic_rows": len(synthetic),
        "intent_counts": dict(Counter(record.get("intent") for record in records)),
        "order_status_counts": dict(Counter(str(record.get("order_status")) for record in records)),
        "synthetic_type_counts": dict(Counter(record.get("synthetic_type") for record in synthetic)),
    }
    statistics_path = output.with_name(output.stem + "_statistics.json")
    statistics_path.write_text(json.dumps(statistics, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
