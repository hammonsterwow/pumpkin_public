from robot_controller.response_manager import ResponseManager


def test_preferred_order_offer_avoids_duplicate_greeting():
    manager = ResponseManager()
    speech = manager.render_speech(
        "preferred_order_offer",
        {
            "response_args": {
                "name": "율리",
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": 1,
            }
        },
    )

    assert speech == "율리님, 평소 드시던 아이스 아메리카노 한 잔으로 도와드릴까요?"
    assert "안녕하세요" not in speech
