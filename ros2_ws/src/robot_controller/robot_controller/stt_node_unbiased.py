from __future__ import annotations

import os
import re

import rclpy
from rclpy.executors import ExternalShutdownException

from .stt_node_safe import SafeSTTNode


class UnbiasedSTTNode(SafeSTTNode):
    """Production STT without lexical initial-prompt bias.

    The previous confirmation prompt contained menu names and instructional text
    such as ``메뉴를 고치면 ... 중 하나를 말합니다``. During a noisy/weak
    confirmation turn Faster-Whisper can emit prompt-like text that the customer
    never said. This runtime deliberately supplies no initial prompt at all.

    Korean decoding is still constrained with ``language='ko'`` by the parent
    runtime, while menu/temperature/quantity interpretation remains the NLU's job.
    """

    LEGACY_PROMPT_MENU_WORDS = (
        "아메리카노",
        "카페라떼",
        "바닐라라떼",
        "딸기스무디",
        "레몬에이드",
    )
    LEGACY_PROMPT_MARKERS = (
        "메뉴를고치면",
        "중하나를말합니다",
        "한국어카페주문",
        "짧은확인답변은",
        "온도표현은",
        "수량표현은",
        "메뉴는아메리카노",
    )
    CONFIRMATION_START_BLOCKS_ENV = "PUMPKIN_STT_CONFIRMATION_SPEECH_START_BLOCKS"

    def __init__(self) -> None:
        super().__init__()
        # Keep these empty for observability as well as decoding. select_initial_prompt
        # below returns None, so Faster-Whisper receives no prompt tokens.
        self.initial_prompt = ""
        self.confirmation_initial_prompt = ""

        # The parent node already separates normal and confirmation start-block
        # counts. The physical launcher can therefore make short yes/no replies
        # easier to trigger without weakening normal-order VAD equally.
        self.confirmation_speech_start_blocks = self._configured_confirmation_start_blocks(
            self.confirmation_speech_start_blocks
        )

        self.get_logger().info(
            "Whisper lexical initial prompts disabled; decoding uses audio + language only"
        )
        self.get_logger().info(
            "Physical VAD profile: "
            f"threshold={self.speech_threshold:.1f}, "
            f"normal_start_blocks={self.speech_start_blocks}, "
            f"confirmation_start_blocks={self.confirmation_speech_start_blocks}, "
            f"end_threshold={self.end_threshold:.1f}, "
            f"silence={self.silence_duration:.2f}s"
        )

    @classmethod
    def _configured_confirmation_start_blocks(cls, fallback: int) -> int:
        raw = os.getenv(cls.CONFIRMATION_START_BLOCKS_ENV, "").strip()
        if not raw:
            return max(1, int(fallback))
        try:
            return max(1, int(raw))
        except ValueError:
            return max(1, int(fallback))

    @staticmethod
    def select_initial_prompt(
        listen_mode: str,
        normal_prompt: str,
        confirmation_prompt: str,
    ) -> None:
        del listen_mode, normal_prompt, confirmation_prompt
        return None

    @classmethod
    def looks_like_legacy_prompt_leak(cls, text: str) -> bool:
        compact = re.sub(r"[^0-9A-Za-z가-힣]", "", str(text)).lower()
        if not compact:
            return False

        marker_hits = sum(marker in compact for marker in cls.LEGACY_PROMPT_MARKERS)
        menu_hits = sum(menu in compact for menu in cls.LEGACY_PROMPT_MENU_WORDS)

        # The exact live hallucination contained instructional prompt prose plus
        # several menu names. Require strong prompt-like evidence so ordinary
        # multi-menu orders are never rejected merely for naming several drinks.
        if marker_hits >= 2:
            return True
        if "중하나를말합니다" in compact and menu_hits >= 2:
            return True
        if "메뉴를고치면" in compact and menu_hits >= 2:
            return True
        return False

    def should_reject_text(self, text: str) -> bool:
        if super().should_reject_text(text):
            return True
        return self.looks_like_legacy_prompt_leak(text)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = UnbiasedSTTNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
