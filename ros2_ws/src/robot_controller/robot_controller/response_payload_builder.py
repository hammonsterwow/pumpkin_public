from __future__ import annotations

from typing import Any


class ResponsePayloadBuilder:
    """Build response payloads without changing dialogue or hardware behavior.

    The default compatibility mode preserves the full decision context expected
    by existing logs, web tools and Action Node. Compact mode is opt-in and keeps
    all fields required for TTS, LCD, face, head and arm action selection while
    omitting the duplicated raw NLU payload.
    """

    COMPACT_CONTEXT_FIELDS = (
        "decision",
        "response_args",
        "reason",
        "state",
        "session_id",
        "waiting_for",
        "next_state",
        "semantic_state",
        "semantic_event",
    )

    def build(
        self,
        context: dict[str, Any],
        *,
        response_key: str,
        speech: str,
        display_text: str,
        include_debug_context: bool = True,
    ) -> dict[str, Any]:
        if include_debug_context:
            return {
                **context,
                "response_key": response_key,
                "speech": speech,
                "display_text": display_text,
            }

        payload = {
            field: context[field]
            for field in self.COMPACT_CONTEXT_FIELDS
            if field in context
        }
        payload.update({
            "response_key": response_key,
            "speech": speech,
            "display_text": display_text,
        })

        order = context.get("order")
        if isinstance(order, dict):
            payload["order_summary"] = {
                key: order[key]
                for key in (
                    "schema_version",
                    "session_id",
                    "items",
                    "order_status",
                    "needs_reprompt",
                    "waiting_for",
                )
                if key in order
            }
        return payload
