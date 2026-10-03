#!/usr/bin/env python3
"""Local review UI server for Pumpkin TOD generated samples.

No third-party packages are required. The server reads the generated 200-row
review sample and stores human judgements in a separate JSONL file so source
training data is never edited by the reviewer.
"""

from __future__ import annotations

import argparse
import json
import threading
import webbrowser
from collections import Counter, defaultdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INPUT = PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_multiturn_review_sample.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "data" / "tod" / "pumpkin_tod_v1_review_results.jsonl"
INDEX_HTML = Path(__file__).resolve().with_name("index.html")

VALID_ERROR_TYPES = {
    "CONTEXT",
    "STATE_BEFORE",
    "STATE_AFTER",
    "DECISION",
    "RESPONSE",
    "OTHER",
}
REQUIRED_SAMPLE_FIELDS = {
    "id",
    "source_scenario",
    "history",
    "fsm_state_before",
    "state_before",
    "user_text",
    "state_after",
    "decision",
    "response_key",
    "fsm_state_after",
    "response",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found: {path}")

    rows: list[dict[str, Any]] = []
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
                raise ValueError(f"{path}:{line_number}: expected a JSON object")
            rows.append(value)
    return rows


def validate_samples(rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("review sample is empty")

    seen: set[str] = set()
    scenario_counts: Counter[str] = Counter()
    for index, row in enumerate(rows):
        missing = REQUIRED_SAMPLE_FIELDS - set(row)
        if missing:
            raise ValueError(f"row {index} is missing fields: {sorted(missing)}")

        sample_id = str(row.get("id") or "").strip()
        if not sample_id:
            raise ValueError(f"row {index} has an empty id")
        if sample_id in seen:
            raise ValueError(f"duplicate review sample id: {sample_id}")
        seen.add(sample_id)

        scenario = str(row.get("source_scenario") or "unknown")
        scenario_counts[scenario] += 1

    # The current builder intentionally creates 40 examples for each of five
    # scenario families. Do not fail on a future dataset shape, but surface it.
    if len(rows) != 200:
        print(f"warning: expected the current 200-row review sample, got {len(rows)}")
    print(
        json.dumps(
            {
                "review_sample_count": len(rows),
                "scenario_counts": dict(sorted(scenario_counts.items())),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


class ReviewStore:
    def __init__(self, input_path: Path, output_path: Path) -> None:
        self.input_path = input_path
        self.output_path = output_path
        self.items = read_jsonl(input_path)
        validate_samples(self.items)
        self.item_by_id = {str(item["id"]): item for item in self.items}
        self.item_order = {str(item["id"]): index for index, item in enumerate(self.items)}
        self.lock = threading.Lock()
        self.reviews: dict[str, dict[str, Any]] = {}
        self._load_reviews()

    def _load_reviews(self) -> None:
        if not self.output_path.exists():
            return
        for row in read_jsonl(self.output_path):
            sample_id = str(row.get("id") or "")
            if sample_id in self.item_by_id:
                self.reviews[sample_id] = row

    def _write_reviews(self) -> None:
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.output_path.with_suffix(self.output_path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            for item in self.items:
                sample_id = str(item["id"])
                review = self.reviews.get(sample_id)
                if review is not None:
                    handle.write(
                        json.dumps(review, ensure_ascii=False, separators=(",", ":")) + "\n"
                    )
        temp_path.replace(self.output_path)

    def save_review(
        self,
        *,
        sample_id: str,
        verdict: str,
        error_type: str | None,
        note: str,
    ) -> dict[str, Any]:
        if sample_id not in self.item_by_id:
            raise ValueError(f"unknown sample id: {sample_id}")

        verdict = verdict.upper().strip()
        if verdict not in {"PASS", "FAIL"}:
            raise ValueError("verdict must be PASS or FAIL")

        normalized_error: str | None = None
        if verdict == "FAIL":
            normalized_error = str(error_type or "").upper().strip()
            if normalized_error not in VALID_ERROR_TYPES:
                raise ValueError(
                    "FAIL review requires one of: " + ", ".join(sorted(VALID_ERROR_TYPES))
                )

        note = str(note or "").strip()
        if len(note) > 1000:
            raise ValueError("note must be 1000 characters or fewer")

        source = self.item_by_id[sample_id]
        review = {
            "id": sample_id,
            "source_scenario": source.get("source_scenario"),
            "verdict": verdict,
            "error_type": normalized_error,
            "note": note,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.lock:
            self.reviews[sample_id] = review
            self._write_reviews()
        return review

    def stats(self) -> dict[str, Any]:
        scenario_total: Counter[str] = Counter()
        scenario_reviewed: Counter[str] = Counter()
        scenario_fail: Counter[str] = Counter()
        errors: Counter[str] = Counter()

        for item in self.items:
            scenario_total[str(item.get("source_scenario") or "unknown")] += 1

        for review in self.reviews.values():
            scenario = str(review.get("source_scenario") or "unknown")
            scenario_reviewed[scenario] += 1
            if review.get("verdict") == "FAIL":
                scenario_fail[scenario] += 1
                if review.get("error_type"):
                    errors[str(review["error_type"])] += 1

        reviewed = len(self.reviews)
        passed = sum(1 for row in self.reviews.values() if row.get("verdict") == "PASS")
        failed = sum(1 for row in self.reviews.values() if row.get("verdict") == "FAIL")
        scenario_stats: dict[str, dict[str, int]] = {}
        for scenario in sorted(scenario_total):
            scenario_stats[scenario] = {
                "total": scenario_total[scenario],
                "reviewed": scenario_reviewed[scenario],
                "failed": scenario_fail[scenario],
            }

        return {
            "total": len(self.items),
            "reviewed": reviewed,
            "passed": passed,
            "failed": failed,
            "remaining": len(self.items) - reviewed,
            "error_counts": dict(sorted(errors.items())),
            "scenarios": scenario_stats,
        }

    def state_payload(self) -> dict[str, Any]:
        first_unreviewed = next(
            (
                index
                for index, item in enumerate(self.items)
                if str(item["id"]) not in self.reviews
            ),
            0,
        )
        return {
            "items": self.items,
            "reviews": self.reviews,
            "stats": self.stats(),
            "first_unreviewed_index": first_unreviewed,
            "input_file": str(self.input_path.relative_to(PROJECT_ROOT)),
            "output_file": str(self.output_path.relative_to(PROJECT_ROOT)),
        }


def make_handler(store: ReviewStore) -> type[BaseHTTPRequestHandler]:
    class ReviewHandler(BaseHTTPRequestHandler):
        server_version = "PumpkinTODReview/1.0"

        def log_message(self, fmt: str, *args: Any) -> None:
            print(f"[review-web] {self.address_string()} - {fmt % args}")

        def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _send_text(
            self,
            body: str,
            *,
            content_type: str,
            status: HTTPStatus = HTTPStatus.OK,
        ) -> None:
            encoded = body.encode("utf-8")
            self.send_response(status.value)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(encoded)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(encoded)

        def do_GET(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path in {"/", "/index.html"}:
                if not INDEX_HTML.exists():
                    self._send_text(
                        "index.html not found",
                        content_type="text/plain; charset=utf-8",
                        status=HTTPStatus.NOT_FOUND,
                    )
                    return
                self._send_text(
                    INDEX_HTML.read_text(encoding="utf-8"),
                    content_type="text/html; charset=utf-8",
                )
                return

            if path == "/api/state":
                self._send_json(store.state_payload())
                return

            if path == "/api/stats":
                self._send_json(store.stats())
                return

            if path == "/api/health":
                self._send_json({"ok": True, "items": len(store.items)})
                return

            self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:  # noqa: N802
            path = urlparse(self.path).path
            if path != "/api/review":
                self._send_json({"error": "not found"}, HTTPStatus.NOT_FOUND)
                return

            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                length = 0
            if length <= 0 or length > 64 * 1024:
                self._send_json({"error": "invalid request body"}, HTTPStatus.BAD_REQUEST)
                return

            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("request body must be a JSON object")
                review = store.save_review(
                    sample_id=str(payload.get("id") or ""),
                    verdict=str(payload.get("verdict") or ""),
                    error_type=payload.get("error_type"),
                    note=str(payload.get("note") or ""),
                )
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
                self._send_json({"error": str(error)}, HTTPStatus.BAD_REQUEST)
                return

            self._send_json({"review": review, "stats": store.stats()})

    return ReviewHandler


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Pumpkin TOD review web server")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument(
        "--check",
        action="store_true",
        help="validate the review sample and exit without starting the server",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = args.input.resolve()
    output_path = args.output.resolve()

    if args.check:
        validate_samples(read_jsonl(input_path))
        print(f"review sample OK: {input_path}")
        return

    store = ReviewStore(input_path, output_path)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(store))
    display_host = "127.0.0.1" if args.host in {"0.0.0.0", "::"} else args.host
    url = f"http://{display_host}:{args.port}/"

    print("\nPumpkin TOD 검수 웹")
    print(f"- 입력: {input_path}")
    print(f"- 결과: {output_path}")
    print(f"- 주소: {url}")
    print("- 종료: Ctrl+C\n")

    if not args.no_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n검수 웹을 종료합니다.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
