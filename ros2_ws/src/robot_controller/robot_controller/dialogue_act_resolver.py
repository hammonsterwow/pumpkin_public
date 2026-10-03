from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Collection


@dataclass(frozen=True)
class DialogueAct:
    """State-aware interpretation of one NLU result.

    This object describes what the user is doing in the dialogue. It does not
    mutate the FSM, order, session, ROS topics, or hardware actions.
    """

    command: str | None = None
    confirmation: str | None = None
    additional_order: bool = False
    correction_request: bool = False


class DialogueActResolver:
    """Resolve text-level dialogue acts without owning dialogue state.

    The learned NLU model remains the primary source for intent and slots. This
    resolver handles short, state-dependent expressions that are difficult to
    interpret without dialogue context, such as ``네``, ``아니요``,
    ``하나 더 주문할게요`` and ``3잔이라고``.
    """

    # If the text itself contains a correction cue, trust that literal evidence
    # regardless of the learned intent score. A model-only MODIFY prediction is
    # deliberately held to a much higher bar because background speech can
    # otherwise push the FSM into correction mode (for example a live false
    # positive such as "수업도 기록해서" -> MODIFY 0.621).
    MODIFY_MIN_CONFIDENCE_WITHOUT_CUE = 0.90
    CONFIRMATION_MIN_MODEL_CONFIDENCE = 0.90

    AFFIRM_WORDS = frozenset({
        "네",
        "넵",
        "넹",
        "예",
        "응",
        "맞아",
        "맞아요",
        "맞습니다",
        "네맞아요",
        "좋아요",
        "확인",
        "확인했어요",
        "그렇게주세요",
        "그대로주세요",
        "yes",
        "ok",
        "okay",
    })

    DENY_WORDS = frozenset({
        "아니",
        "아니요",
        "아뇨",
        "아니에요",
        "틀려요",
        "틀렸어요",
        "다시",
        "다시할게요",
        "변경",
        "바꿀게요",
        "수정할게요",
        "no",
        "nope",
    })

    CANCEL_WORDS = frozenset({
        "취소",
        "취소할게요",
        "주문취소",
        "그만",
        "그만할게요",
    })

    # Natural negative-order phrases observed in the physical microphone test.
    # Keep them specific to ordering so generic conversational negatives do not
    # cancel a session accidentally.
    CANCEL_PATTERNS = (
        "주문안할",
        "주문안해",
        "주문하지않",
        "주문하지말",
        "주문그만",
        "주문취소",
        "안시킬",
        "안시켜",
    )

    ADDITIONAL_ORDER_WORDS = frozenset({
        "하나더주문할게요",
        "하나더주문할래요",
        "하나더주세요",
        "하나추가요",
        "추가주문할게요",
        "추가주문할래요",
        "추가할게요",
        "더주문할게요",
        "더주문할래요",
        "더시킬게요",
        "더할게요",
        "음료좀더시킬래요",
    })

    CORRECTION_CUES = (
        "아니",
        "아니고",
        "바꿔",
        "바꿀",
        "변경",
        "수정",
        "말고",
        "대신",
        "이라고",
    )

    # When the robot has just asked a yes/no confirmation, Whisper may append a
    # harmless extra token to a very short answer (for example ``아니요 야호``).
    # Prefix matching in that narrow dialogue state is more robust than requiring
    # an exact whole-string match. Slot-bearing corrections are routed before this
    # resolver by DecisionNode, so ``아니요, 바닐라라떼요`` still becomes a direct
    # order correction instead of a bare denial.
    AFFIRM_PREFIXES = (
        "네",
        "넵",
        "넹",
        "예",
        "응",
        "맞아",
        "좋아",
        "확인",
        "yes",
        "ok",
        "okay",
    )
    DENY_PREFIXES = (
        "아니요",
        "아뇨",
        "아니",
        "틀려",
        "틀렸",
        "nope",
        "no",
    )
    # Whisper often keeps a filler before a clear answer ("어 맞아요 맞아요",
    # "그렇게... 아니요"). Suffix matching is limited to unambiguous answer
    # phrases; short tokens such as "네" are deliberately excluded.
    AFFIRM_SUFFIXES = (
        "맞아요",
        "맞습니다",
        "그렇게주세요",
        "그대로주세요",
    )
    DENY_SUFFIXES = (
        "아니요",
        "아뇨",
        "아니에요",
        "아닙니다",
        "틀려요",
        "틀렸어요",
    )

    @staticmethod
    def compact_text(text: Any) -> str:
        return re.sub(r"[^0-9A-Za-z가-힣]", "", str(text)).lower()

    def resolve_command(self, nlu_result: dict[str, Any]) -> str | None:
        compact = self.compact_text(nlu_result.get("text", ""))

        # Restart is semantically stronger than a cancel word embedded inside a
        # restart request. For example "주문 취소하고 다시 고를게요" means clear
        # the current cart and immediately return to ordering, not end service.
        restart_patterns = (
            "다시주문",
            "주문다시",
            "처음부터",
            "새로주문",
            "다시고르",
            "다시고를",
            "다시선택",
        )
        if any(pattern in compact for pattern in restart_patterns):
            return "RESTART"

        if (
            compact in self.CANCEL_WORDS
            or any(pattern in compact for pattern in self.CANCEL_PATTERNS)
            or any(
                cue in compact
                for cue in ("취소할", "취소해", "취소하겠", "전부취소", "전체취소")
            )
        ):
            return "CANCEL"
        return None

    def resolve_confirmation(
        self,
        nlu_result: dict[str, Any],
        *,
        state: str,
        confirmation_states: Collection[str],
        additional_order_as_deny: bool = False,
    ) -> str | None:
        if state not in confirmation_states:
            return None

        compact = self.compact_text(nlu_result.get("text", ""))
        if additional_order_as_deny and self.is_additional_order_request(nlu_result):
            return "DENY"
        if compact in self.AFFIRM_WORDS:
            return "AFFIRM"
        if compact in self.DENY_WORDS:
            return "DENY"

        if any(compact.startswith(prefix) for prefix in self.AFFIRM_PREFIXES):
            return "AFFIRM"
        if any(compact.startswith(prefix) for prefix in self.DENY_PREFIXES):
            return "DENY"

        # Clear answer words remain authoritative even when Whisper prepends a
        # short filler. Check denial first so a phrase containing negation can
        # never be accepted merely because it ends in "맞아요".
        if any(compact.endswith(suffix) for suffix in self.DENY_SUFFIXES):
            return "DENY"
        if (
            not any(marker in compact for marker in ("아니", "안맞"))
            and any(compact.endswith(suffix) for suffix in self.AFFIRM_SUFFIXES)
        ):
            return "AFFIRM"

        # The NLU already classifies full utterances. Use that result only at a
        # deliberately high confidence so arbitrary background speech still
        # cannot confirm or reject an order.
        intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
        try:
            confidence = float(
                nlu_result.get("confidence")
                or nlu_result.get("intent_confidence")
                or 0.0
            )
        except (TypeError, ValueError):
            confidence = 0.0
        if (
            intent in {"AFFIRM", "DENY"}
            and confidence >= self.CONFIRMATION_MIN_MODEL_CONFIDENCE
        ):
            return intent
        return None

    def is_additional_order_request(self, nlu_result: dict[str, Any]) -> bool:
        compact = self.compact_text(nlu_result.get("text", ""))
        return compact in self.ADDITIONAL_ORDER_WORDS

    def has_correction_cue(self, nlu_result: dict[str, Any]) -> bool:
        compact = self.compact_text(nlu_result.get("text", ""))
        return any(cue in compact for cue in self.CORRECTION_CUES)

    def is_correction_request(
        self,
        nlu_result: dict[str, Any],
        *,
        correction_context: bool = False,
    ) -> bool:
        if correction_context:
            return True

        # Literal correction language is the strongest evidence and remains
        # accepted even when the learned intent confidence is mediocre.
        if self.has_correction_cue(nlu_result):
            return True

        intent = str(nlu_result.get("intent", "UNKNOWN")).upper()
        if intent != "MODIFY":
            return False

        # Model-only MODIFY predictions must be highly confident. Prefer the
        # normalized `confidence` field used by the runtime and fall back to the
        # raw intent confidence for compatibility with lightweight tests/tools.
        confidence = float(
            nlu_result.get("confidence")
            or nlu_result.get("intent_confidence")
            or 0.0
        )
        return confidence >= self.MODIFY_MIN_CONFIDENCE_WITHOUT_CUE

    def resolve(
        self,
        nlu_result: dict[str, Any],
        *,
        state: str,
        confirmation_states: Collection[str],
        correction_context: bool = False,
        additional_order_as_deny: bool = False,
    ) -> DialogueAct:
        return DialogueAct(
            command=self.resolve_command(nlu_result),
            confirmation=self.resolve_confirmation(
                nlu_result,
                state=state,
                confirmation_states=confirmation_states,
                additional_order_as_deny=additional_order_as_deny,
            ),
            additional_order=self.is_additional_order_request(nlu_result),
            correction_request=self.is_correction_request(
                nlu_result,
                correction_context=correction_context,
            ),
        )
