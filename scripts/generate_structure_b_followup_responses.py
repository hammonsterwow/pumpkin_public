#!/usr/bin/env python3
"""Add 3,000 balanced synthetic follow-up responses to Structure B training data."""

from __future__ import annotations

import json
import math
import random
import re
from collections import Counter
from pathlib import Path

SEED = 20260808
ROOT = Path(__file__).resolve().parents[1]
TRAIN_VALID_PATH = ROOT / "data" / "structure_b_train_valid.jsonl"
TEST_PATH = ROOT / "data" / "structure_b_test.jsonl"

MENUS = {
    "아메리카노": ["아메리카노", "아메", "아메리카노 커피", "커피 아메리카노"],
    "카페라떼": ["카페라떼", "카페 라떼", "카페라테", "라떼"],
    "바닐라라떼": ["바닐라라떼", "바닐라 라떼", "바닐라라테", "바라"],
    "레몬에이드": ["레몬에이드", "레몬 에이드", "레모네이드", "레몬주스"],
    "딸기스무디": ["딸기스무디", "딸기 스무디", "딸기주스", "스트로베리 스무디"],
}
PREFIXES = [
    "", "음 ", "어 ", "아 ", "그럼 ", "네 그럼 ", "저는 ", "일단 ",
    "저기요 ", "아 네 ", "그러면 ", "음 그러면 ", "네 ", "그럼 저는 ",
]
QUANTITY_SURFACES = {
    1: ["한 잔", "1잔", "한 개"], 2: ["두 잔", "2잔", "두 개"],
    3: ["세 잔", "3잔", "세 개"], 4: ["네 잔", "4잔", "네 개"],
    5: ["다섯 잔", "5잔", "다섯 개"], 6: ["여섯 잔", "6잔", "여섯 개"],
    7: ["일곱 잔", "7잔", "일곱 개"], 8: ["여덟 잔", "8잔", "여덟 개"],
    9: ["아홉 잔", "9잔", "아홉 개"], 10: ["열 잔", "10잔", "열 개"],
    11: ["열한 잔", "11잔"], 12: ["열두 잔", "12잔"],
    13: ["열세 잔", "13잔"], 14: ["열네 잔", "14잔"],
    15: ["열다섯 잔", "15잔"], 16: ["열여섯 잔", "16잔"],
    17: ["열일곱 잔", "17잔"], 18: ["열여덟 잔", "18잔"],
    19: ["열아홉 잔", "19잔"], 20: ["스무 잔", "20잔"],
}
TEMP_ONLY_PHRASES = {
    "ICE": [
        "아이스로요", "아이스로 할게요", "아이스로 주세요", "아이스 부탁해요",
        "아이스요", "차갑게요", "차갑게 해주세요", "시원하게요", "시원하게 해주세요",
        "찬 걸로요", "찬 걸로 할게요", "차가운 걸로요",
    ],
    "HOT": [
        "핫으로요", "핫으로 할게요", "핫으로 주세요", "핫 부탁해요", "핫이요",
        "따뜻하게요", "따뜻하게 해주세요", "뜨겁게요", "뜨겁게 해주세요",
        "뜨신 걸로요", "뜨신 걸로 할게요", "따뜻한 걸로요",
    ],
}
TEMP_BEFORE = {"ICE": ["아이스", "차가운", "시원한"], "HOT": ["핫", "따뜻한", "뜨거운"]}
TEMP_AFTER = {"ICE": ["아이스로", "차갑게", "시원하게", "찬 걸로"], "HOT": ["핫으로", "따뜻하게", "뜨겁게", "뜨신 걸로"]}
FIXED_ICE_MENUS = {"레몬에이드", "딸기스무디"}
CATEGORIES = ("menu_only", "temperature_only", "quantity_only", "menu_temperature", "menu_quantity", "temperature_quantity")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as file:
        return [json.loads(line) for line in file if line.strip()]


def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return re.sub(r"\s+([,.!?])", r"\1", text).strip()


def make_item(menu=None, temperature=None, quantity=None) -> tuple[dict, list[str]]:
    missing_slots, errors = [], []
    if menu is None:
        missing_slots.append("menu"); errors.append("MISSING_MENU")
    if temperature is None:
        missing_slots.append("temperature"); errors.append("MISSING_TEMPERATURE")
    if quantity is None:
        missing_slots.append("quantity"); errors.append("MISSING_QUANTITY")
    return {
        "item_id": 0, "menu": menu, "temperature": temperature, "quantity": quantity,
        "missing_slots": missing_slots, "validation_errors": errors,
    }, errors


def make_record(text: str, category: str, menu=None, temperature=None, quantity=None) -> dict:
    item, errors = make_item(menu, temperature, quantity)
    return {
        "text": text, "intent": "ORDER", "items": [item],
        "source": {"kind": "followup", "category": category},
        "order_status": "INCOMPLETE", "validation_errors": errors,
    }


def exact_quantity_counts(total: int) -> dict[int, int]:
    weights = {1: 0.12, 2: 0.11, 3: 0.10}
    for quantity in range(4, 21):
        weights[quantity] = 0.67 / 17
    raw = {quantity: total * weight for quantity, weight in weights.items()}
    counts = {quantity: math.floor(value) for quantity, value in raw.items()}
    remaining = total - sum(counts.values())
    order = sorted(raw, key=lambda q: raw[q] - counts[q], reverse=True)
    for quantity in order[:remaining]:
        counts[quantity] += 1
    return counts


def build_candidates(blocked: set[str]) -> dict[str, dict[str, dict]]:
    candidates = {category: {} for category in CATEGORIES}

    def add(category: str, text: str, menu=None, temperature=None, quantity=None) -> None:
        text = clean_text(text)
        if not text or text in blocked or text in candidates[category]:
            return
        if re.search(r"(게로|잔로|개로|걸로로|이스로로|요요)", text):
            return
        candidates[category][text] = make_record(text, category, menu, temperature, quantity)

    menu_templates = [
        "{p}{m}요", "{p}{m}로 할게요", "{p}{m}로 주세요", "{p}{m}로 부탁해요",
        "{p}{m}로 주문할게요", "{p}{m}로 하겠습니다", "{p}{m}로 할래요",
        "{p}{m}가 좋아요", "{p}{m}로 정할게요", "{p}{m}로 갈게요",
        "{p}메뉴는 {m}요", "{p}{m} 맞아요", "{p}{m}입니다", "{p}{m}로요",
    ]
    for menu, aliases in MENUS.items():
        for alias in aliases:
            for prefix in PREFIXES:
                for template in menu_templates:
                    add("menu_only", template.format(p=prefix, m=alias), menu=menu)

    for temperature, phrases in TEMP_ONLY_PHRASES.items():
        for phrase in phrases:
            for prefix in PREFIXES:
                add("temperature_only", prefix + phrase, temperature=temperature)
                add("temperature_only", prefix + "온도는 " + phrase, temperature=temperature)

    quantity_templates = [
        "{p}{q}이요", "{p}{q} 주세요", "{p}{q} 부탁해요", "{p}{q}만 주세요",
        "{p}{q}면 돼요", "{p}{q} 주문할게요", "{p}수량은 {q}이요",
        "{p}{q}으로 해주세요", "{p}{q} 할게요", "{p}{q}로 하겠습니다",
    ]
    for quantity, surfaces in QUANTITY_SURFACES.items():
        for surface in surfaces:
            for prefix in PREFIXES:
                for template in quantity_templates:
                    text = template.format(p=prefix, q=surface)
                    if surface.endswith("잔") and "{q}로 " in template:
                        text = text.replace(surface + "로 ", surface + "으로 ")
                    add("quantity_only", text, quantity=quantity)

    for menu, aliases in MENUS.items():
        temperatures = ["ICE"] if menu in FIXED_ICE_MENUS else ["ICE", "HOT"]
        for temperature in temperatures:
            for alias in aliases:
                for prefix in PREFIXES:
                    for before in TEMP_BEFORE[temperature]:
                        for text in (
                            f"{prefix}{before} {alias}요", f"{prefix}{before} {alias}로 할게요",
                            f"{prefix}{before} {alias} 주세요", f"{prefix}{before} {alias} 부탁해요",
                            f"{prefix}{before} {alias}로 주문할게요",
                        ):
                            add("menu_temperature", text, menu=menu, temperature=temperature)
                    for after in TEMP_AFTER[temperature]:
                        for text in (
                            f"{prefix}{alias} {after}요", f"{prefix}{alias} {after} 할게요",
                            f"{prefix}{alias} {after} 주세요", f"{prefix}{alias} {after} 부탁해요",
                            f"{prefix}{alias}는 {after} 할게요",
                        ):
                            add("menu_temperature", text, menu=menu, temperature=temperature)

    menu_quantity_templates = [
        "{p}{m} {q}이요", "{p}{m} {q} 주세요", "{p}{q} {m}요", "{p}{m} {q} 부탁해요",
        "{p}{m} {q} 주문할게요", "{p}{m} {q}만 주세요", "{p}{m}로 {q} 주세요",
        "{p}{m}로 {q} 부탁해요", "{p}{q}만 {m}로 주세요", "{p}메뉴는 {m}, 수량은 {q}이요",
    ]
    for menu, aliases in MENUS.items():
        for alias in aliases:
            for quantity, surfaces in QUANTITY_SURFACES.items():
                for surface in surfaces:
                    for prefix in PREFIXES:
                        for template in menu_quantity_templates:
                            add("menu_quantity", template.format(p=prefix, m=alias, q=surface), menu=menu, quantity=quantity)

    for temperature, leads in TEMP_AFTER.items():
        for lead in leads:
            for quantity, surfaces in QUANTITY_SURFACES.items():
                for surface in surfaces:
                    for prefix in PREFIXES:
                        for text in (
                            f"{prefix}{lead} {surface}이요", f"{prefix}{lead} {surface} 주세요",
                            f"{prefix}{surface} {lead} 부탁해요", f"{prefix}{lead} {surface} 부탁해요",
                            f"{prefix}{surface} {lead} 할게요", f"{prefix}{lead} {surface} 주문할게요",
                            f"{prefix}온도는 {lead}, 수량은 {surface}이요",
                        ):
                            add("temperature_quantity", text, temperature=temperature, quantity=quantity)
    return candidates


def sample_followups(candidates: dict[str, dict[str, dict]]) -> list[dict]:
    rng = random.Random(SEED)
    selected = []

    for menu in MENUS:
        pool = [record for record in candidates["menu_only"].values() if record["items"][0]["menu"] == menu]
        rng.shuffle(pool); selected.extend(pool[:100])

    for temperature in ("ICE", "HOT"):
        pool = [record for record in candidates["temperature_only"].values() if record["items"][0]["temperature"] == temperature]
        rng.shuffle(pool); selected.extend(pool[:250])

    for quantity, count in exact_quantity_counts(500).items():
        pool = [record for record in candidates["quantity_only"].values() if record["items"][0]["quantity"] == quantity]
        rng.shuffle(pool)
        if len(pool) < count: raise RuntimeError(f"quantity_only q={quantity}: {len(pool)} < {count}")
        selected.extend(pool[:count])

    for menu in MENUS:
        targets = {"ICE": 100} if menu in FIXED_ICE_MENUS else {"ICE": 50, "HOT": 50}
        for temperature, count in targets.items():
            pool = [record for record in candidates["menu_temperature"].values() if record["items"][0]["menu"] == menu and record["items"][0]["temperature"] == temperature]
            rng.shuffle(pool); selected.extend(pool[:count])

    per_menu = exact_quantity_counts(100)
    for menu in MENUS:
        for quantity, count in per_menu.items():
            pool = [record for record in candidates["menu_quantity"].values() if record["items"][0]["menu"] == menu and record["items"][0]["quantity"] == quantity]
            rng.shuffle(pool)
            if len(pool) < count: raise RuntimeError(f"menu_quantity {menu} q={quantity}: {len(pool)} < {count}")
            selected.extend(pool[:count])

    per_temperature = exact_quantity_counts(250)
    for temperature in ("ICE", "HOT"):
        for quantity, count in per_temperature.items():
            pool = [record for record in candidates["temperature_quantity"].values() if record["items"][0]["temperature"] == temperature and record["items"][0]["quantity"] == quantity]
            rng.shuffle(pool)
            if len(pool) < count: raise RuntimeError(f"temperature_quantity {temperature} q={quantity}: {len(pool)} < {count}")
            selected.extend(pool[:count])

    if len(selected) != 3000: raise AssertionError(f"Expected 3000 follow-ups, got {len(selected)}")
    texts = [record["text"] for record in selected]
    if len(texts) != len(set(texts)): raise AssertionError("Duplicate generated follow-up text")
    rng.shuffle(selected)
    return selected


def main() -> None:
    all_pool = load_jsonl(TRAIN_VALID_PATH)
    test_records = load_jsonl(TEST_PATH)
    base_records = [record for record in all_pool if (record.get("source") or {}).get("kind") != "followup"]
    if len(base_records) != 17000: raise AssertionError(f"Expected 17,000 base records, got {len(base_records)}")
    if len(test_records) != 880: raise AssertionError(f"Expected 880 test records, got {len(test_records)}")

    base_texts = {record["text"].strip() for record in base_records}
    test_texts = {record["text"].strip() for record in test_records}
    followups = sample_followups(build_candidates(base_texts | test_texts))
    followup_texts = {record["text"] for record in followups}
    if followup_texts & base_texts: raise AssertionError("Generated text overlaps base training data")
    if followup_texts & test_texts: raise AssertionError("Generated text overlaps handmade test data")

    final_records = base_records + followups
    if len(final_records) != 20000: raise AssertionError(f"Expected 20,000 final records, got {len(final_records)}")
    if len({record["text"] for record in final_records}) != 20000: raise AssertionError("Final training pool contains exact duplicate text")

    with TRAIN_VALID_PATH.open("w", encoding="utf-8") as file:
        for record in final_records:
            file.write(json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n")

    category_counts = Counter((record.get("source") or {}).get("category") for record in followups)
    missing_counts = Counter(tuple(record["items"][0]["missing_slots"]) for record in followups)
    print("final records:", len(final_records))
    print("follow-up categories:", dict(sorted(category_counts.items())))
    print("missing-slot patterns:", dict(sorted(missing_counts.items())))


if __name__ == "__main__":
    main()
