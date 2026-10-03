from __future__ import annotations

from typing import Any

from .response_manager_pickup import PickupAwareResponseManager


class OrderExceptionAwareResponseManager(PickupAwareResponseManager):
    """Add user-facing responses for unsupported S8 order requests."""

    def render_speech(self, response_key: str, context: dict[str, Any]) -> str:
        if response_key == "unsupported_menu":
            return "현재 주문 가능한 메뉴 중에서 골라 말씀해 주세요."

        if response_key == "unsupported_temperature_for_menu":
            args = self._response_args(context)
            menu = str(args.get("menu") or "").strip()
            if menu:
                return f"{menu}는 아이스로만 제공돼요. 다시 주문해 주세요."
            return "해당 메뉴는 아이스로만 제공돼요. 다시 주문해 주세요."

        return super().render_speech(response_key, context)

    def render_display(
        self,
        response_key: str,
        context: dict[str, Any],
        speech: str,
    ) -> str:
        if response_key == "unsupported_menu":
            return "주문 가능한 메뉴를 선택해 주세요"
        if response_key == "unsupported_temperature_for_menu":
            args = self._response_args(context)
            menu = str(args.get("menu") or "").strip()
            return f"{menu}는 아이스만 가능" if menu else "아이스만 가능한 메뉴"
        return super().render_display(response_key, context, speech)
