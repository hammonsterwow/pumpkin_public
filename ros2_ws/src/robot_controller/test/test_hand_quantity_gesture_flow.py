from __future__ import annotations

from robot_controller.decision_node_hand_quantity import HandQuantityDecisionNode


def make_node(state="ASK_QUANTITY", waiting_slot="quantity"):
    node = HandQuantityDecisionNode.__new__(HandQuantityDecisionNode)
    node.state = state
    node.session_id = "session-hand-quantity-test"
    node.current_order = {
        "items": [
            {
                "item_id": 0,
                "menu": "아메리카노",
                "temperature": "ICE",
                "quantity": None,
                "missing_slots": ["quantity"],
                "validation_errors": [],
            }
        ],
        "order_status": "INCOMPLETE",
    }
    node.waiting_for = {"item_id": 0, "slot": waiting_slot}
    node.nlu_reprompt_count = 0
    node.slot_retry_count = 0
    node.max_nlu_reprompts = 2
    node.max_slot_retries = 2
    node.human_presence_initialized = True
    node.last_human_presence = True
    node._customer_exit_seen = False
    node.correction_target_item_id = None
    return node


def test_one_to_five_fingers_fill_the_active_quantity_slot():
    gesture_to_quantity = {
        "ONE_FINGER": 1,
        "TWO_FINGERS": 2,
        "THREE_FINGERS": 3,
        "FOUR_FINGERS": 4,
        "FIVE_FINGERS": 5,
    }

    for gesture, quantity in gesture_to_quantity.items():
        node = make_node()
        decision = node.make_user_hand_gesture_decision(gesture)

        assert decision is not None
        assert decision["order"]["items"][0]["quantity"] == quantity
        assert decision["input_modality"] == "VISION_HAND_GESTURE"
        assert decision["user_hand_gesture"] == gesture
        assert decision["vision_quantity"] == quantity
        assert node.current_order["items"][0]["quantity"] == quantity


def test_two_fingers_are_ignored_outside_quantity_question():
    node = make_node(state="ORDER_CONFIRM")

    assert node.make_user_hand_gesture_decision("TWO_FINGERS") is None
    assert node.current_order["items"][0]["quantity"] is None


def test_two_fingers_do_not_fill_a_different_waiting_slot():
    node = make_node(state="ASK_QUANTITY", waiting_slot="temperature")

    assert node.make_user_hand_gesture_decision("TWO_FINGERS") is None
    assert node.current_order["items"][0]["quantity"] is None


def test_unknown_hand_gesture_is_ignored():
    node = make_node()

    assert node.make_user_hand_gesture_decision("OPEN_PALM") is None
