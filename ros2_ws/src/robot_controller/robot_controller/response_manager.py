from __future__ import annotations

import os
from typing import Any, Callable

from .response_payload_builder import ResponsePayloadBuilder


class ResponseManager:
    """Render user-facing speech and display text from structured decisions.

    This class is deliberately independent of ROS and dialogue state. It must not
    mutate the incoming decision payload or any FSM state. Response envelope
    construction is delegated to ResponsePayloadBuilder.
    """

    STATIC_SPEECH = {
        "start_order": "안녕하세요. 주문 도와드릴게요.",
        "ask_order": "무엇을 주문하시겠어요?",
        "modify_without_order": "변경할 주문이 아직 없어요. 새 주문을 말씀해 주세요.",
        "guide_customer": "매장 이용 안내를 도와드릴게요.",
        "payment_guide": "결제 관련 안내를 도와드릴게요.",
        "out_of_policy": "주문하실 메뉴와 옵션을 말씀해 주세요.",
        "invalid_order": "주문 정보를 이해하지 못했어요. 메뉴부터 다시 말씀해 주세요.",
        "group_scope_count_mismatch": "현재 주문은 두 메뉴가 아니에요. 적용할 메뉴를 말씀해 주세요.",
        "ask_correction_content": "어떤 부분이 다른가요? 메뉴, 온도 또는 수량을 말씀해 주세요.",
        "ask_correction_target": "어떤 메뉴를 변경할까요? 메뉴 이름과 변경 내용을 함께 말씀해 주세요.",
        "ask_correction_target_selection": "어떤 음료를 바꿀까요?",
        "ask_correction_target_not_found": "현재 주문에서 해당 음료를 찾지 못했어요. 바꿀 음료를 다시 말씀해 주세요.",
        "invalid_correction": "변경 내용을 이해하지 못했어요. 다시 말씀해 주세요.",
        "affirm_without_order": "먼저 주문을 말씀해 주세요.",
        "deny_without_order": "주문을 다시 말씀해 주세요.",
        "order_confirmed": "주문이 확정되었습니다. 감사합니다.",
        "ask_finish_order": "주문을 마치시겠어요?",
        # Legacy alias kept for historical logs/tests and older decision nodes.
        "ask_next_customer": "주문을 마치시겠어요?",
        "next_customer_ready": "주문이 완료되었습니다. 감사합니다.",
        "continue_order": "추가 주문을 말씀해 주세요.",
        "modify_order": "어떤 부분을 바꿀까요?",
        "restart_order": "주문을 처음부터 다시 말씀해 주세요.",
        "cancel_order": "주문을 취소했어요.",
        "no_active_order": "현재 진행 중인 주문이 없어요.",
        "slot_retry_exhausted": "같은 정보를 여러 번 확인하지 못했어요. 주문을 처음부터 다시 말씀해 주세요.",
        "nlu_retry_exhausted": "주문을 여러 번 이해하지 못했어요. 메뉴부터 다시 말씀해 주세요.",
        "nlu_reprompt": "죄송해요. 다시 한 번 말씀해 주시겠어요?",
        "stt_retry": "다시 말씀해 주세요.",
        "stt_failed": "주문을 잘 듣지 못했어요. 화면을 확인하거나 다시 시도해 주세요.",
        "unknown": "주문이나 매장 안내를 도와드릴 수 있어요.",
    }

    STATIC_DISPLAY = {
        "start_order": "주문을 말씀해 주세요",
        "ask_order": "무엇을 주문하시겠어요?",
        "order_confirmed": "주문이 확정되었습니다",
        "ask_finish_order": "주문을 마치시겠어요?",
        # Legacy alias kept for compatibility.
        "ask_next_customer": "주문을 마치시겠어요?",
        "next_customer_ready": "주문 완료",
        "continue_order": "추가 주문을 말씀해 주세요",
        "ask_correction_target_selection": "바꿀 음료를 말씀해 주세요",
        "ask_correction_target_not_found": "바꿀 음료를 다시 말씀해 주세요",
        "cancel_order": "주문이 취소되었습니다",
        "no_active_order": "진행 중인 주문이 없습니다",
        "restart_order": "새 주문을 말씀해 주세요",
        "stt_retry": "다시 말씀해 주세요",
        "stt_failed": "음성 인식 실패",
        "payment_guide": "결제 안내",
        "guide_customer": "매장 안내",
    }

    GUIDE_TARGET_RESTROOM = "RESTROOM"
    GUIDE_DIRECTION_ENV = "PUMPKIN_RESTROOM_DIRECTION"
    DEFAULT_RESTROOM_DIRECTION = "RIGHT"

    def __init__(self) -> None:
        self.payload_builder = ResponsePayloadBuilder()
        self._renderers: dict[str, Callable[[dict[str, Any]], str]] = {
            "ask_menu": self._render_ask_menu,
            "ask_quantity": self._render_ask_quantity,
            "ask_temperature": self._render_ask_temperature,
            "confirm_item": self._render_confirm_item,
            "confirm_order": self._render_confirm_order,
            "preferred_order_offer": self._render_preferred_order_offer,
            "preorder_pickup_ready": self._render_preorder_pickup_ready,
            "preorder_status": self._render_preorder_status,
            "ask_correction_replacement": self._render_ask_correction_replacement,
            "ask_correction_target_disambiguation": self._render_ask_correction_target_disambiguation,
            "guide_customer": self._render_guide_customer,
        }

    def render(
        self,
        decision_result: dict[str, Any],
        *,
        include_debug_context: bool = True,
    ) -> dict[str, Any]:
        context = dict(decision_result)
        response_key = str(context.get("response_key") or "unknown")
        if response_key == "guide_customer":
            context = self._enrich_guide_context(context)
        speech = self.render_speech(response_key, context)
        if response_key == "guide_customer":
            resume_prompt = context.get("resume_prompt")
            if isinstance(resume_prompt, dict):
                resume_key = str(resume_prompt.get("response_key") or "")
                resume_context = dict(context)
                resume_context["response_args"] = dict(
                    resume_prompt.get("response_args") or {}
                )
                resume_speech = self.render_speech(resume_key, resume_context)
                if resume_speech:
                    speech = f"{speech} {resume_speech}"
        display_text = self.render_display(response_key, context, speech)
        return self.payload_builder.build(
            context,
            response_key=response_key,
            speech=speech,
            display_text=display_text,
            include_debug_context=include_debug_context,
        )

    def render_speech(self, response_key: str, context: dict[str, Any]) -> str:
        renderer = self._renderers.get(response_key)
        if renderer is not None:
            return renderer(context)
        return self.STATIC_SPEECH.get(response_key, self.STATIC_SPEECH["unknown"])

    def render_display(
        self,
        response_key: str,
        context: dict[str, Any],
        speech: str,
    ) -> str:
        if response_key == "ask_menu":
            item_id = self._response_args(context).get("item_id")
            if isinstance(item_id, int):
                return f"{item_id + 1}번째 음료 메뉴를 선택해 주세요"
        if response_key == "ask_quantity":
            drink = self._waiting_item_label(context) or self._menu(context)
            return f"{drink} 수량을 선택해 주세요" if drink else "수량을 선택해 주세요"
        if response_key == "ask_temperature":
            menu = self._menu(context)
            return f"{menu} 온도를 선택해 주세요" if menu else "온도를 선택해 주세요"
        if response_key == "confirm_item":
            drink = self._waiting_item_label(context)
            return f"{drink} 맞으신가요?" if drink else "주문하신 음료가 맞으신가요?"
        if response_key == "confirm_order":
            return self._render_order_summary(context)
        if response_key in {"preorder_pickup_ready", "preorder_status"}:
            return speech
        if response_key == "ask_correction_replacement":
            target = self._response_args(context).get("target_item")
            if isinstance(target, dict):
                label = self._format_item_description(target)
                if label:
                    return f"{label} 변경"
        if response_key == "ask_correction_target_disambiguation":
            return "변경할 음료를 더 자세히 말씀해 주세요"
        if response_key == "guide_customer":
            args = self._response_args(context)
            target = str(args.get("target") or "").upper()
            direction = self._normalize_direction(args.get("direction"))
            if target == self.GUIDE_TARGET_RESTROOM:
                if direction == "LEFT":
                    return "화장실 ← 왼쪽"
                if direction == "RIGHT":
                    return "화장실 → 오른쪽"
                return "화장실 안내"
        return self.STATIC_DISPLAY.get(response_key, speech)

    def _render_preferred_order_offer(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        name = str(args.get("name") or "").strip()
        menu = str(args.get("menu") or "").strip()
        temperature = str(args.get("temperature") or "NONE").upper()
        try:
            quantity = int(args.get("quantity") or 1)
        except (TypeError, ValueError):
            quantity = 1

        customer = name if name.endswith("님") else f"{name}님"
        temperature_label = {
            "ICE": "아이스 ",
            "HOT": "따뜻한 ",
            "NONE": "",
        }.get(temperature, "")
        quantity_label = {
            1: "한 잔",
            2: "두 잔",
            3: "세 잔",
            4: "네 잔",
        }.get(quantity, f"{quantity}잔")
        return (
            f"{customer}, 평소 드시던 {temperature_label}{menu} "
            f"{quantity_label}으로 도와드릴까요?"
        )

    def _render_preorder_pickup_ready(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        customer = self._customer_label(args.get("customer_name"))
        summary = self._render_preorder_items(args.get("items"))
        return f"{customer}사전 주문하신 {summary}이 왼쪽 음료 수령대에 준비되어 있습니다."

    def _render_preorder_status(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        customer = self._customer_label(args.get("customer_name"))
        summary = self._render_preorder_items(args.get("items"))
        status = str(args.get("status") or "").upper()
        tail = "주문이 접수되었습니다." if status == "RECEIVED" else "주문을 준비하고 있습니다."
        return f"{customer}사전 주문하신 {summary} {tail}"

    @staticmethod
    def _customer_label(value: Any) -> str:
        name = str(value or "").strip()
        return "" if not name else f"{name if name.endswith('님') else name + '님'}, "

    @staticmethod
    def _render_preorder_items(value: Any) -> str:
        labels = []
        for item in value if isinstance(value, list) else []:
            if not isinstance(item, dict):
                continue
            menu = str(item.get("menu_name") or item.get("menu") or "음료").strip()
            temperature = {"ICE": "아이스 ", "HOT": "따뜻한 ", "NONE": ""}.get(
                str(item.get("temperature") or "NONE").upper(), ""
            )
            try:
                quantity = int(item.get("quantity") or 1)
            except (TypeError, ValueError):
                quantity = 1
            quantity_label = {1: "한 잔", 2: "두 잔", 3: "세 잔", 4: "네 잔"}.get(
                quantity, f"{quantity}잔"
            )
            labels.append(f"{temperature}{menu} {quantity_label}")
        return ", ".join(labels) if labels else "음료"

    def _render_ask_menu(self, context: dict[str, Any]) -> str:
        item_id = self._response_args(context).get("item_id")
        if isinstance(item_id, int):
            return f"{item_id + 1}번째 음료는 어떤 메뉴로 주문하시겠어요?"
        return "어떤 메뉴로 주문하시겠어요?"

    def _render_ask_quantity(self, context: dict[str, Any]) -> str:
        drink = self._waiting_item_label(context)
        if drink:
            return f"{drink}는 몇 잔 주문하시겠어요?"

        menu = self._menu(context)
        return f"{menu}는 몇 잔 주문하시겠어요?" if menu else "몇 잔 주문하시겠어요?"

    def _render_ask_temperature(self, context: dict[str, Any]) -> str:
        menu = self._menu(context)
        prefix = f"{menu}는 " if menu else ""
        return f"{prefix}아이스로 드릴까요, 따뜻하게 드릴까요?"

    def _render_confirm_item(self, context: dict[str, Any]) -> str:
        drink = self._waiting_item_label(context)
        return f"{drink} 맞으신가요?" if drink else "주문하신 음료가 맞으신가요?"

    def _render_confirm_order(self, context: dict[str, Any]) -> str:
        summary = self._render_order_summary(context)
        if not summary:
            return "주문 내용을 확인해 주세요."
        return f"{summary} 맞으신가요?"

    def _render_ask_correction_replacement(self, context: dict[str, Any]) -> str:
        target = self._response_args(context).get("target_item")
        if not isinstance(target, dict):
            return "어떤 메뉴로 변경할까요?"
        label = self._format_item_description(target)
        if not label:
            return "어떤 메뉴로 변경할까요?"
        particle = self._object_particle(label)
        return f"{label}{particle} 어떤 메뉴로 변경할까요?"

    def _render_ask_correction_target_disambiguation(
        self,
        context: dict[str, Any],
    ) -> str:
        args = self._response_args(context)
        candidates = [
            item
            for item in args.get("candidates", [])
            if isinstance(item, dict)
        ]
        requested_menu = str(args.get("requested_menu") or "").strip()
        if not candidates:
            return "어느 음료를 변경할까요? 더 자세히 말씀해 주세요."

        same_requested_menu = bool(requested_menu) and all(
            str(item.get("menu") or "").strip() == requested_menu
            for item in candidates
        )
        if same_requested_menu:
            prefix = f"어느 {requested_menu}를 변경할까요?"
            options = [
                self._format_item_option(item, include_menu=False)
                for item in candidates
            ]
        else:
            prefix = "어느 음료를 변경할까요?"
            options = [
                self._format_item_option(item, include_menu=True)
                for item in candidates
            ]

        options = [option for option in options if option]
        if not options:
            return f"{prefix} 더 자세히 말씀해 주세요."
        return f"{prefix} {' 또는 '.join(options)} 중에서 말씀해 주세요."

    def _render_guide_customer(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        target = str(args.get("target") or "").upper()
        direction = self._normalize_direction(args.get("direction"))
        if not direction:
            direction = self._normalize_direction(context.get("direction"))
        if not direction:
            direction = self._normalize_direction(
                context.get("nlu_result", {}).get("direction")
            )

        if target == self.GUIDE_TARGET_RESTROOM:
            if direction == "LEFT":
                return "화장실은 왼쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
            if direction == "RIGHT":
                return "화장실은 오른쪽에 있습니다. 제가 보는 방향으로 가시면 됩니다."
            return "화장실 위치를 안내해드릴게요."

        if direction == "LEFT":
            return "왼쪽 방향으로 안내해드릴게요."
        if direction == "RIGHT":
            return "오른쪽 방향으로 안내해드릴게요."
        return self.STATIC_SPEECH["guide_customer"]

    def _enrich_guide_context(self, context: dict[str, Any]) -> dict[str, Any]:
        args = dict(self._response_args(context))
        direction = self._normalize_direction(args.get("direction"))
        if not direction:
            direction = self._normalize_direction(context.get("direction"))
        if not direction:
            nlu_result = context.get("nlu_result")
            if isinstance(nlu_result, dict):
                direction = self._normalize_direction(nlu_result.get("direction"))

        target = str(args.get("target") or "").upper()
        nlu_result = context.get("nlu_result")
        text = ""
        if isinstance(nlu_result, dict):
            text = str(nlu_result.get("text") or "")
        compact_text = "".join(text.split())

        if not target and "화장실" in compact_text:
            target = self.GUIDE_TARGET_RESTROOM

        if target == self.GUIDE_TARGET_RESTROOM and not direction:
            direction = self._configured_direction(
                self.GUIDE_DIRECTION_ENV,
                self.DEFAULT_RESTROOM_DIRECTION,
            )

        if target:
            args["target"] = target
        if direction:
            args["direction"] = direction

        context["response_args"] = args
        return context

    @staticmethod
    def _normalize_direction(value: object) -> str | None:
        direction = str(value or "").strip().upper()
        return direction if direction in {"LEFT", "RIGHT"} else None

    @classmethod
    def _configured_direction(cls, env_name: str, default: str) -> str:
        fallback = cls._normalize_direction(default) or "RIGHT"
        configured = cls._normalize_direction(os.getenv(env_name, fallback))
        return configured or fallback

    @staticmethod
    def _temperature_prefix(item: dict[str, Any]) -> str:
        return {
            "ICE": "아이스 ",
            "HOT": "따뜻한 ",
        }.get(item.get("temperature"), "")

    @classmethod
    def _format_item_description(cls, item: dict[str, Any]) -> str:
        menu = str(item.get("menu") or "").strip()
        if not menu:
            return ""
        quantity = item.get("quantity")
        quantity_text = f" {quantity}잔" if quantity is not None else ""
        return f"{cls._temperature_prefix(item)}{menu}{quantity_text}"

    @classmethod
    def _format_item_option(
        cls,
        item: dict[str, Any],
        *,
        include_menu: bool,
    ) -> str:
        temperature = cls._temperature_prefix(item).strip()
        menu = str(item.get("menu") or "").strip() if include_menu else ""
        quantity = item.get("quantity")
        quantity_text = f"{quantity}잔" if quantity is not None else ""
        return " ".join(
            part for part in (temperature, menu, quantity_text) if part
        )

    @staticmethod
    def _object_particle(text: str) -> str:
        compact = str(text).rstrip()
        if not compact:
            return "를"
        last = compact[-1]
        codepoint = ord(last)
        if 0xAC00 <= codepoint <= 0xD7A3:
            return "을" if (codepoint - 0xAC00) % 28 else "를"
        # Item descriptions normally end in "잔" when quantity is known.
        return "을" if last.isdigit() else "를"

    def _render_order_summary(self, context: dict[str, Any]) -> str:
        order = context.get("order")
        items = order.get("items", []) if isinstance(order, dict) else []
        descriptions: list[str] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            description = self._format_item_description(item)
            if description:
                descriptions.append(description)
        return ", ".join(descriptions)

    def _waiting_item_label(self, context: dict[str, Any]) -> str:
        args = self._response_args(context)
        item_id = args.get("item_id")
        order = context.get("order")
        items = order.get("items", []) if isinstance(order, dict) else []

        if isinstance(item_id, int):
            for index, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                current_id = item.get("item_id", index)
                if current_id != item_id:
                    continue
                menu = str(item.get("menu") or "").strip()
                if not menu:
                    return ""
                return f"{self._temperature_prefix(item)}{menu}"

        return ""

    @staticmethod
    def _response_args(context: dict[str, Any]) -> dict[str, Any]:
        args = context.get("response_args")
        return args if isinstance(args, dict) else {}

    def _menu(self, context: dict[str, Any]) -> str:
        return str(self._response_args(context).get("menu") or "").strip()
