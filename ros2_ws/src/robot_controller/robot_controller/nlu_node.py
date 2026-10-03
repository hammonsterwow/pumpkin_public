import json
import os
import re
import sys
from pathlib import Path

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import String


PROJECT_ROOT = Path(os.getenv("PUMPKIN_PROJECT_ROOT", Path.home() / "pumpkin"))
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from nlu import StructureBNLUPredictor  # noqa: E402
from nlu.config import (  # noqa: E402
    DEFAULT_CONFIDENCE_THRESHOLD,
    DEFAULT_MODEL_DIR,
    MODEL_NAME,
)

from .dialogue_slots import extract_explicit_slots, has_explicit_slots
from .menu_policy import QUANTITY_WORDS, validate_nlu_label_maps
from .multi_item_span_grounding import recover_multi_item_span_evidence
from .nlu_postprocess import (
    clear_unexpressed_quantity_predictions,
    clear_unexpressed_temperature_predictions,
    reconcile_explicit_order_evidence,
    recover_fuzzy_menu_evidence,
)


READY_FILE = Path(os.getenv("PUMPKIN_NLU_READY_FILE", "/tmp/pumpkin_nlu_ready"))

_STANDALONE_AFFIRMATIONS = frozenset({
    "네",
    "예",
    "응",
    "맞아",
    "맞아요",
    "맞습니다",
    "그래",
    "그래요",
})
_STANDALONE_DENIALS = frozenset({
    "아니",
    "아니요",
    "아뇨",
    "아닙니다",
})

_QUANTITY_HOMOPHONE_TOKENS = sorted(QUANTITY_WORDS, key=len, reverse=True)
_QUANTITY_HOMOPHONE_TOKEN_PATTERN = "|".join(
    [r"\d+", *(re.escape(token) for token in _QUANTITY_HOMOPHONE_TOKENS)]
)
_LIVE_JJAN_QUANTITY_PATTERN = re.compile(
    rf"(?P<number>{_QUANTITY_HOMOPHONE_TOKEN_PATTERN})\s*짠"
    rf"(?=(?:이요|이에요|요|주세요)?(?:\s|[.!?,]|$))"
)


def _compact_confirmation_text(text: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣]", "", str(text)).lower()


def normalize_quantity_homophone(text: str) -> str:
    """Recover narrow quantity-unit artifacts before model/slot grounding.

    Physical Faster-Whisper runs have produced ``짠`` for the unit ``잔``
    (for example ``여덟 짠`` and ``아홉 짠이요``). Rewrite only when ``짠``
    is immediately attached to a supported Korean quantity word or digits, so
    an unrelated standalone ``짠`` is never treated as an order quantity.

    The older ``세 전`` recovery remains deliberately stricter because ``세전``
    is an ordinary Korean word in unrelated contexts such as ``세전 소득``.
    """

    original = str(text).strip()
    normalized = _LIVE_JJAN_QUANTITY_PATTERN.sub(
        lambda match: f"{match.group('number')} 잔",
        original,
    )

    compact = _compact_confirmation_text(normalized)
    if not re.fullmatch(r"(?:세전(?:이요|요)?)+(?:주세요)?", compact):
        return normalized
    return re.sub(
        r"세\s*전(?=(?:이요|요)?(?:\s|[.!?,]|$))",
        "세 잔",
        normalized,
    )


def normalize_standalone_confirmation_result(
    text: str,
    result: dict,
) -> bool:
    """Make isolated yes/no words deterministic before slot grounding.

    Korean ``네`` is both an affirmation and the native-number form used in
    ``네 잔``. A bare ``네`` must never be grounded as quantity=4. Full quantity
    phrases such as ``네 잔 주세요`` are unaffected because the compact text is
    not an isolated confirmation token.
    """

    compact = _compact_confirmation_text(text)
    if compact in _STANDALONE_AFFIRMATIONS:
        intent = "AFFIRM"
    elif compact in _STANDALONE_DENIALS:
        intent = "DENY"
    else:
        return False

    result["intent"] = intent
    result["intent_confidence"] = max(
        0.999,
        float(result.get("intent_confidence") or 0.0),
    )
    result["order_status"] = "NONE"
    result["items"] = []
    result["needs_reprompt"] = False
    result.pop("explicit_slots", None)
    result["standalone_confirmation_grounded"] = True
    return True


class NLUNode(Node):
    def __init__(self):
        READY_FILE.unlink(missing_ok=True)
        super().__init__("nlu_node")

        self.declare_parameter("model_dir", str(DEFAULT_MODEL_DIR))
        self.declare_parameter("device", os.getenv("PUMPKIN_NLU_DEVICE", "auto"))
        self.declare_parameter(
            "confidence_threshold",
            DEFAULT_CONFIDENCE_THRESHOLD,
        )

        model_dir = str(self.get_parameter("model_dir").value)
        device = str(self.get_parameter("device").value)
        self.confidence_threshold = float(
            self.get_parameter("confidence_threshold").value
        )

        self.get_logger().info(
            f"Loading NLU model: model={MODEL_NAME}, device={device}, dir={model_dir}"
        )
        self.predictor = StructureBNLUPredictor(
            model_dir=model_dir,
            device=device,
        )
        self.validate_model_policy()

        self.subscriber = self.create_subscription(
            String,
            "/voice_text",
            self.voice_callback,
            10,
        )
        self.publisher = self.create_publisher(
            String,
            "/intent_result",
            10,
        )

        READY_FILE.write_text(
            f"model={MODEL_NAME}\ndevice={self.predictor.device}\n",
            encoding="utf-8",
        )
        self.get_logger().info(
            f"NLU node ready: model={MODEL_NAME}, device={self.predictor.device}"
        )

    def validate_model_policy(self):
        errors = validate_nlu_label_maps(self.predictor.label_maps)
        if not errors:
            self.get_logger().info("NLU label maps match the shared menu policy")
            return

        details = "; ".join(errors)
        raise RuntimeError(
            "NLU checkpoint labels do not match robot_controller/menu_policy.py: "
            f"{details}"
        )

    def voice_callback(self, msg: String):
        raw_text = msg.data.strip()
        text = normalize_quantity_homophone(raw_text)
        if not text:
            self.get_logger().warning("Empty /voice_text message ignored")
            return

        if text != raw_text:
            self.get_logger().info(
                f"Normalized quantity homophone before NLU grounding: {raw_text} -> {text}"
            )

        try:
            result = self.predictor.predict(
                text,
                confidence_threshold=self.confidence_threshold,
            )
        except Exception as error:
            self.get_logger().error(f"NLU prediction failed: {error}")
            return

        standalone_confirmation = normalize_standalone_confirmation_result(
            text,
            result,
        )

        if standalone_confirmation:
            explicit_slots = {}
            self.get_logger().info(
                "Grounded standalone confirmation before quantity/menu extraction"
            )
        else:
            explicit_slots = extract_explicit_slots(text)

            # Multi-item audio often preserves each quantity/temperature even when
            # Whisper distorts one menu name. Split only simple conjunction-based
            # orders into quantity-anchored spans. Each missing menu then uses the
            # same strict fuzzy policy as the single-item path; if it still cannot
            # be recovered, keep a partial item so the FSM asks for that menu.
            multi_item_span_recovery = recover_multi_item_span_evidence(
                text,
                result,
                explicit_slots,
            )
            if multi_item_span_recovery is not None:
                result["multi_item_span_recovery"] = multi_item_span_recovery
                self.get_logger().info(
                    "Recovered multi-item span evidence: "
                    f"items={multi_item_span_recovery['item_count']}, "
                    f"fuzzy={len(multi_item_span_recovery['fuzzy_recoveries'])}, "
                    f"partial={multi_item_span_recovery['partial_item_indexes']}"
                )

            # Keep Whisper decoding unbiased. When exact menu spelling was lost by
            # ASR, recover menu evidence only if a high-confidence NLU prediction
            # and a clearly separated jamo/phonetic match independently agree.
            fuzzy_menu_recovery = recover_fuzzy_menu_evidence(
                text,
                result,
                explicit_slots,
            )
            if fuzzy_menu_recovery is not None:
                result["fuzzy_menu_recovery"] = fuzzy_menu_recovery
                self.get_logger().info(
                    "Recovered fuzzy menu evidence: "
                    f"menu={fuzzy_menu_recovery['menu']}, "
                    f"matched={fuzzy_menu_recovery['matched_text']}, "
                    f"score={fuzzy_menu_recovery['score']:.4f}, "
                    f"margin={fuzzy_menu_recovery['margin']:.4f}, "
                    f"model_conf={fuzzy_menu_recovery['model_menu_confidence']:.4f}"
                )

            evidence_reconciled = reconcile_explicit_order_evidence(
                result,
                explicit_slots,
            )
            if evidence_reconciled:
                self.get_logger().info(
                    "Grounded NLU item predictions with explicit text evidence"
                )

            temperature_guarded = clear_unexpressed_temperature_predictions(
                result,
                explicit_slots,
            )
            if temperature_guarded:
                self.get_logger().info(
                    "Ignored NLU temperature prediction without explicit text evidence"
                )

            quantity_guarded = clear_unexpressed_quantity_predictions(
                result,
                explicit_slots,
            )
            if quantity_guarded:
                self.get_logger().info(
                    "Ignored NLU quantity prediction without explicit text evidence"
                )

            if has_explicit_slots(explicit_slots):
                result["explicit_slots"] = explicit_slots

        result["confidence"] = result["intent_confidence"]

        out = String()
        out.data = json.dumps(result, ensure_ascii=False)
        self.publisher.publish(out)

        item_summary = [
            f"{item.get('menu')}/{item.get('temperature')}/{item.get('quantity')}"
            for item in result.get("items", [])
        ]
        self.get_logger().info(
            f"NLU result: intent={result.get('intent')}, "
            f"status={result.get('order_status')}, "
            f"items={item_summary}, "
            f"explicit_slots={result.get('explicit_slots')}, "
            f"confidence={result.get('intent_confidence')}, "
            f"latency_ms={result.get('latency_ms')}"
        )

    def destroy_node(self):
        READY_FILE.unlink(missing_ok=True)
        return super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = NLUNode()
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
