from __future__ import annotations

from typing import Any

from .response_manager import ResponseManager


class PickupAwareResponseManager(ResponseManager):
    """Extend store guidance with a drink-pickup target.

    The physical demo uses opposite sides for the restroom and the drink pickup
    counter. Restroom direction remains configurable through
    ``PUMPKIN_RESTROOM_DIRECTION``; pickup automatically resolves to the opposite
    side so the two guides cannot silently drift to the same direction.

    Pickup grounding is intentionally layered:
    1) exact Korean pickup synonyms are preferred,
    2) only inside GUIDE/location-question context, a narrow Hangul phonetic
       matcher can recover distorted Whisper forms of ``픽업``/``픽업대``.

    The fuzzy path never rewrites STT text and never runs for ordinary order
    utterances because this response manager only receives ``guide_customer``
    rendering requests for this branch of the dialogue.
    """

    GUIDE_TARGET_PICKUP = "PICKUP"

    PICKUP_STRONG_MARKERS = (
        "픽업",
        "픽업대",
        "수령",
        "수령대",
        "음료받는곳",
        "음료수받는곳",
        "음료받는곳",
        "음료찾는곳",
        "음료수찾는곳",
        "음료나오는곳",
        "음료수나오는곳",
        "주문한음료",
        "주문한거어디서받",
        "주문한것어디서받",
    )
    PICKUP_DRINK_MARKERS = (
        "음료",
        "음료수",
        "커피",
        "주문한거",
        "주문한것",
    )
    PICKUP_LOCATION_MARKERS = (
        "어디서받",
        "어디에서받",
        "받는곳",
        "받을곳",
        "어디서찾",
        "찾는곳",
        "나오는곳",
    )

    # Fuzzy recovery is deliberately restricted to short pickup words and only
    # when the same GUIDE utterance also looks like a location question.
    PICKUP_FUZZY_ALIASES = ("픽업대", "픽업")
    PICKUP_FUZZY_MIN_SCORE = 0.65
    PICKUP_FUZZY_LOCATION_CUES = (
        "어디",
        "위치",
        "어느쪽",
        "어느편",
        "어딨어",
        "어디있",
        "알려",
    )

    _SIMILAR_INITIAL_GROUPS = (
        frozenset({0, 1, 15}),   # ㄱ/ㄲ/ㅋ
        frozenset({3, 4, 16}),   # ㄷ/ㄸ/ㅌ
        frozenset({7, 8, 17}),   # ㅂ/ㅃ/ㅍ
        frozenset({9, 10}),      # ㅅ/ㅆ
        frozenset({12, 13, 14}), # ㅈ/ㅉ/ㅊ
    )
    _SIMILAR_VOWEL_GROUPS = (
        frozenset({1, 5}),
        frozenset({3, 7}),
        frozenset({9, 10, 11}),
        frozenset({14, 15}),
        frozenset({5, 15}),
        frozenset({10, 15}),
    )

    def render_display(
        self,
        response_key: str,
        context: dict[str, Any],
        speech: str,
    ) -> str:
        if response_key == "guide_customer":
            args = self._response_args(context)
            target = str(args.get("target") or "").upper()
            direction = self._normalize_direction(args.get("direction"))
            if target == self.GUIDE_TARGET_PICKUP:
                if direction == "LEFT":
                    return "음료 수령대 ← 왼쪽"
                if direction == "RIGHT":
                    return "음료 수령대 → 오른쪽"
                return "음료 수령대 안내"
        return super().render_display(response_key, context, speech)

    def _render_guide_customer(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        target = str(args.get("target") or "").upper()
        direction = self._normalize_direction(args.get("direction"))

        if target == self.GUIDE_TARGET_PICKUP:
            if direction == "LEFT":
                return "음료 수령대는 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
            if direction == "RIGHT":
                return "음료 수령대는 오른쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
            return "음료 수령대 위치를 안내해드릴게요."

        return super()._render_guide_customer(context)

    def _enrich_guide_context(self, context: dict[str, Any]) -> dict[str, Any]:
        context = super()._enrich_guide_context(context)
        args = dict(self._response_args(context))
        target = str(args.get("target") or "").upper()
        direction = self._normalize_direction(args.get("direction"))

        nlu_result = context.get("nlu_result")
        text = ""
        if isinstance(nlu_result, dict):
            text = str(nlu_result.get("text") or "")
        compact_text = "".join(text.split())

        if not target and self._looks_like_pickup_request(compact_text):
            target = self.GUIDE_TARGET_PICKUP

        if target == self.GUIDE_TARGET_PICKUP and not direction:
            restroom_direction = self._configured_direction(
                self.GUIDE_DIRECTION_ENV,
                self.DEFAULT_RESTROOM_DIRECTION,
            )
            direction = self._opposite_direction(restroom_direction)

        if target:
            args["target"] = target
        if direction:
            args["direction"] = direction
        context["response_args"] = args
        return context

    @classmethod
    def _looks_like_pickup_request(cls, compact_text: str) -> bool:
        text = str(compact_text or "")
        if not text:
            return False

        # 1) Exact/synonym path. This handles preferred user-facing expressions
        # such as "음료 수령대" and "음료 받는 곳" without fuzzy inference.
        if any(marker in text for marker in cls.PICKUP_STRONG_MARKERS):
            return True
        if (
            any(marker in text for marker in cls.PICKUP_DRINK_MARKERS)
            and any(marker in text for marker in cls.PICKUP_LOCATION_MARKERS)
        ):
            return True

        # 2) Conservative ASR recovery. Short words like 픽업 are too ambiguous to
        # fuzzy-match globally, so require an explicit location-question cue too.
        return cls._looks_like_fuzzy_pickup_request(text)

    @classmethod
    def _looks_like_fuzzy_pickup_request(cls, text: str) -> bool:
        if not any(cue in text for cue in cls.PICKUP_FUZZY_LOCATION_CUES):
            return False

        hangul_text = "".join(
            character
            for character in str(text)
            if 0xAC00 <= ord(character) <= 0xD7A3
        )
        if not hangul_text:
            return False

        best_score = 0.0
        for alias in cls.PICKUP_FUZZY_ALIASES:
            alias_length = len(alias)
            # Allow one inserted/deleted syllable because live Whisper often turns
            # 픽업대 into variants such as "피업데이" while preserving the sound.
            for window_length in range(
                max(1, alias_length - 1),
                alias_length + 2,
            ):
                if len(hangul_text) < window_length:
                    continue
                for start in range(len(hangul_text) - window_length + 1):
                    window = hangul_text[start:start + window_length]
                    score = cls._phonetic_edit_similarity(window, alias)
                    if score > best_score:
                        best_score = score
        return best_score >= cls.PICKUP_FUZZY_MIN_SCORE

    @classmethod
    def _phonetic_edit_similarity(cls, observed: str, expected: str) -> float:
        if not observed or not expected:
            return 0.0

        insertion_deletion_cost = 0.70
        rows = len(observed) + 1
        cols = len(expected) + 1
        dp = [[0.0] * cols for _ in range(rows)]

        for row in range(1, rows):
            dp[row][0] = row * insertion_deletion_cost
        for col in range(1, cols):
            dp[0][col] = col * insertion_deletion_cost

        for row in range(1, rows):
            for col in range(1, cols):
                substitution = (
                    dp[row - 1][col - 1]
                    + cls._phonetic_syllable_cost(
                        observed[row - 1],
                        expected[col - 1],
                    )
                )
                deletion = dp[row - 1][col] + insertion_deletion_cost
                insertion = dp[row][col - 1] + insertion_deletion_cost
                dp[row][col] = min(substitution, deletion, insertion)

        normalizer = max(len(observed), len(expected), 1)
        score = 1.0 - (dp[-1][-1] / normalizer)
        return max(0.0, min(1.0, score))

    @classmethod
    def _phonetic_syllable_cost(cls, observed: str, expected: str) -> float:
        if observed == expected:
            return 0.0

        observed_parts = cls._decompose_hangul_syllable(observed)
        expected_parts = cls._decompose_hangul_syllable(expected)
        if observed_parts is None or expected_parts is None:
            return 1.0

        observed_initial, observed_vowel, observed_final = observed_parts
        expected_initial, expected_vowel, expected_final = expected_parts

        if observed_initial == expected_initial:
            initial_cost = 0.0
        elif cls._same_confusion_group(
            observed_initial,
            expected_initial,
            cls._SIMILAR_INITIAL_GROUPS,
        ):
            initial_cost = 0.25
        else:
            initial_cost = 1.0

        if observed_vowel == expected_vowel:
            vowel_cost = 0.0
        elif cls._same_confusion_group(
            observed_vowel,
            expected_vowel,
            cls._SIMILAR_VOWEL_GROUPS,
        ):
            vowel_cost = 0.25
        else:
            vowel_cost = 1.0

        final_cost = 0.0 if observed_final == expected_final else 1.0
        return 0.45 * initial_cost + 0.45 * vowel_cost + 0.10 * final_cost

    @staticmethod
    def _decompose_hangul_syllable(character: str) -> tuple[int, int, int] | None:
        if len(character) != 1:
            return None
        codepoint = ord(character)
        if not 0xAC00 <= codepoint <= 0xD7A3:
            return None
        syllable_index = codepoint - 0xAC00
        return (
            syllable_index // 588,
            (syllable_index % 588) // 28,
            syllable_index % 28,
        )

    @staticmethod
    def _same_confusion_group(
        first: int,
        second: int,
        groups: tuple[frozenset[int], ...],
    ) -> bool:
        return any(first in group and second in group for group in groups)

    @classmethod
    def _opposite_direction(cls, direction: object) -> str:
        normalized = cls._normalize_direction(direction)
        return "LEFT" if normalized == "RIGHT" else "RIGHT"
