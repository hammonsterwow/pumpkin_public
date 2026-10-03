#!/usr/bin/env python3
"""단일 메뉴 주문 데이터셋 생성기.

입력 CSV의 아이스 아메리카노 1잔 문장을 정제한 뒤,
유효한 메뉴-온도 8개 조합과 수량 1~20으로 확장한다.

출력 열:
    text,label,menu,temperature,quantity,memo
"""

from __future__ import annotations

import argparse
import base64
import collections
import csv
import gzip
import io
import hashlib
import json
import re
from pathlib import Path
from typing import Callable


COLUMNS = ["text", "label", "menu", "temperature", "quantity", "memo"]

COUNTER = {
    1: "한", 2: "두", 3: "세", 4: "네", 5: "다섯",
    6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉", 10: "열",
    11: "열한", 12: "열두", 13: "열세", 14: "열네", 15: "열다섯",
    16: "열여섯", 17: "열일곱", 18: "열여덟", 19: "열아홉", 20: "스무",
}

MENU_SPECS = [
    ("아메리카노", "ICE", ["아메리카노"]),
    ("아메리카노", "HOT", ["아메리카노"]),
    ("카페라떼", "ICE", ["카페라떼", "카페라테", "커피라떼"]),
    ("카페라떼", "HOT", ["카페라떼", "카페라테", "커피라떼"]),
    ("바닐라라떼", "ICE", ["바닐라라떼", "바닐라라테", "바닐라떼"]),
    ("바닐라라떼", "HOT", ["바닐라라떼", "바닐라라테", "바닐라떼"]),
    ("레몬에이드", "ICE", ["레몬에이드", "레모네이드", "레몬 주스"]),
    ("딸기스무디", "ICE", ["딸기스무디", "딸기 스무디", "딸기 주스", "스트로베리 스무디"]),
]


def normalize_text(text: str) -> str:
    """앞뒤 공백과 중복 공백을 정리한다."""
    return " ".join(text.strip().split())


def spaced_item_quantity(quantity: int) -> str:
    """원문의 '하나' 형식을 자연스러운 띄어쓰기 수량으로 확장한다."""
    return "하나" if quantity == 1 else f"{COUNTER[quantity]} 개"


QUANTITY_PATTERNS: list[tuple[str, Callable[[int], str]]] = [
    ("한 잔", lambda q: f"{COUNTER[q]} 잔"),
    ("한잔", lambda q: f"{COUNTER[q]}잔"),
    ("하나", spaced_item_quantity),
    ("한개", lambda q: f"{COUNTER[q]}개"),
]


def replace_quantity(template: str, quantity: int) -> str:
    matches = [(pattern, converter) for pattern, converter in QUANTITY_PATTERNS if pattern in template]
    if len(matches) != 1:
        found = [pattern for pattern, _ in matches]
        raise ValueError(f"수량 표현을 정확히 하나 찾지 못했습니다: {template!r}, matches={found}")

    pattern, converter = matches[0]
    return template.replace(pattern, converter(quantity), 1)


def convert_temperature(template: str, temperature: str) -> str:
    """ICE 원문을 유지하거나, 냉음료 표현을 충돌 없는 HOT 표현으로 변환한다."""
    if temperature == "ICE":
        return template
    if temperature != "HOT":
        raise ValueError(f"지원하지 않는 온도: {temperature}")

    converted = template
    # 서로 다른 원문 표현이 같은 HOT 문장으로 합쳐지지 않도록 표현을 구분한다.
    converted = converted.replace("아이스 {MENU}", "핫 {MENU}")
    converted = converted.replace("{MENU} 아이스로", "{MENU} 핫으로")
    converted = converted.replace("아이스로 {MENU}", "핫으로 {MENU}")
    converted = converted.replace("차가운 {MENU}", "따뜻한 {MENU}")
    converted = converted.replace("시원한 {MENU}", "뜨거운 {MENU}")
    converted = converted.replace("차갑게", "따뜻하게")
    converted = converted.replace("시원하게", "뜨겁게")

    if re.search(r"아이스|차갑|시원", converted):
        raise ValueError(f"HOT 변환 후 냉음료 표현이 남았습니다: {template!r} -> {converted!r}")
    return converted



def open_text_csv(path: Path):
    """일반 CSV, gzip CSV, base64로 저장한 gzip CSV를 동일하게 연다."""
    if path.suffix == ".b64":
        compressed = base64.b64decode(path.read_text(encoding="ascii"))
        text = gzip.decompress(compressed).decode("utf-8-sig")
        return io.StringIO(text, newline="")
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def load_and_clean_templates(source_path: Path) -> tuple[list[str], list[dict[str, object]]]:
    with open_text_csv(source_path) as file:
        reader = csv.DictReader(file)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"예상 열은 {COLUMNS}이지만 실제 열은 {reader.fieldnames}입니다.")
        rows = list(reader)

    templates: list[str] = []
    excluded: list[dict[str, object]] = []
    seen: set[str] = set()

    for line_number, row in enumerate(rows, start=2):
        text = normalize_text(row["text"])
        reason: str | None = None

        if "아아" in text:
            reason = "아메리카노 전용 축약어"
        elif "아메리카노" not in text:
            reason = "다른 메뉴로 치환할 수 없는 아메리카노 전용 표현"
        elif text in seen:
            reason = "정규화 후 중복"

        if reason is not None:
            excluded.append({"line": line_number, "text": text, "reason": reason})
            continue

        seen.add(text)
        templates.append(text)

    return templates, excluded


def generate_rows(templates: list[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    for menu_label, temperature, aliases in MENU_SPECS:
        for quantity in range(1, 21):
            for template_index, source_text in enumerate(templates):
                text = source_text.replace("아메리카노", "{MENU}")
                text = replace_quantity(text, quantity)
                text = convert_temperature(text, temperature)

                alias = aliases[(template_index + quantity - 1) % len(aliases)]
                text = normalize_text(text.replace("{MENU}", alias))

                rows.append(
                    {
                        "text": text,
                        "label": "ORDER",
                        "menu": menu_label,
                        "temperature": temperature,
                        "quantity": str(quantity),
                        "memo": "",
                    }
                )

    return rows


def validate(rows: list[dict[str, str]], template_count: int) -> None:
    expected_rows = template_count * 20 * len(MENU_SPECS)
    if len(rows) != expected_rows:
        raise ValueError(f"행 수 오류: expected={expected_rows}, actual={len(rows)}")

    texts = [row["text"] for row in rows]
    if len(texts) != len(set(texts)):
        duplicates = [text for text, count in collections.Counter(texts).items() if count > 1]
        raise ValueError(f"중복 문장이 있습니다: {duplicates[:10]}")

    if any("아아" in text for text in texts):
        raise ValueError("'아아' 표현이 출력에 남았습니다.")

    for row in rows:
        quantity = int(row["quantity"])
        if not 1 <= quantity <= 20:
            raise ValueError(f"수량 범위 오류: {row}")

        if row["temperature"] == "HOT" and re.search(r"아이스|차갑|시원", row["text"]):
            raise ValueError(f"HOT 라벨과 냉음료 표현 충돌: {row}")

        if row["menu"] in {"레몬에이드", "딸기스무디"} and row["temperature"] == "HOT":
            raise ValueError(f"정책상 허용되지 않는 HOT 메뉴: {row}")


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def build_statistics(
    source_path: Path,
    templates: list[str],
    excluded: list[dict[str, object]],
    rows: list[dict[str, str]],
    output_path: Path,
) -> dict[str, object]:
    with open_text_csv(source_path) as file:
        source_rows = sum(1 for _ in csv.DictReader(file))

    combo_counts = collections.Counter((row["menu"], row["temperature"]) for row in rows)
    quantity_counts = collections.Counter(int(row["quantity"]) for row in rows)

    alias_counts: dict[str, dict[str, int]] = {}
    for menu_label, temperature, aliases in MENU_SPECS:
        alias_counts[f"{menu_label}/{temperature}"] = {alias: 0 for alias in aliases}

    for row in rows:
        key = f"{row['menu']}/{row['temperature']}"
        for alias in sorted(alias_counts[key], key=len, reverse=True):
            if alias in row["text"]:
                alias_counts[key][alias] += 1
                break

    return {
        "source_rows": source_rows,
        "excluded_rows": len(excluded),
        "excluded_by_reason": dict(collections.Counter(item["reason"] for item in excluded)),
        "base_templates": len(templates),
        "generated_rows": len(rows),
        "unique_texts": len({row["text"] for row in rows}),
        "duplicate_texts": len(rows) - len({row["text"] for row in rows}),
        "columns": COLUMNS,
        "menu_temperature_counts": {
            f"{menu}/{temperature}": count
            for (menu, temperature), count in sorted(combo_counts.items())
        },
        "quantity_counts": {str(quantity): quantity_counts[quantity] for quantity in range(1, 21)},
        "rows_per_menu_temperature_quantity": len(templates),
        "menu_alias_counts": alias_counts,
        "validation": {
            "contains_아아": sum("아아" in row["text"] for row in rows),
            "hot_rows_with_cold_expression": sum(
                row["temperature"] == "HOT"
                and re.search(r"아이스|차갑|시원", row["text"]) is not None
                for row in rows
            ),
            "cold_only_menu_hot_rows": sum(
                row["temperature"] == "HOT"
                and row["menu"] in {"레몬에이드", "딸기스무디"}
                for row in rows
            ),
            "quantity_out_of_range": sum(not 1 <= int(row["quantity"]) <= 20 for row in rows),
        },
        "sha256": hashlib.sha256(output_path.read_bytes()).hexdigest(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("data/source_ice_americano_quantity_1.csv.gz.b64"),
        help="원본 아이스 아메리카노 1잔 CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/single_menu_quantity_1_20_augmented.csv"),
        help="생성 데이터 CSV",
    )
    parser.add_argument(
        "--excluded-output",
        type=Path,
        default=Path("data/single_menu_quantity_1_20_excluded.csv"),
        help="정제 과정 제외 행 CSV",
    )
    parser.add_argument(
        "--statistics-output",
        type=Path,
        default=Path("data/single_menu_quantity_1_20_statistics.json"),
        help="분포와 검증 결과 JSON",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    templates, excluded = load_and_clean_templates(args.source)
    rows = generate_rows(templates)
    validate(rows, len(templates))

    write_csv(args.output, rows, COLUMNS)
    write_csv(args.excluded_output, excluded, ["line", "text", "reason"])

    statistics = build_statistics(args.source, templates, excluded, rows, args.output)
    args.statistics_output.parent.mkdir(parents=True, exist_ok=True)
    args.statistics_output.write_text(
        json.dumps(statistics, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        f"완료: source={statistics['source_rows']}, "
        f"templates={statistics['base_templates']}, "
        f"generated={statistics['generated_rows']}, "
        f"duplicates={statistics['duplicate_texts']}"
    )


if __name__ == "__main__":
    main()
