from robot_controller.face_identity import parse_face_recognition_payload


def test_matched_payload_is_normalized():
    identity = parse_face_recognition_payload(
        {
            "matched": True,
            "customer_id": "customer_1",
            "name": "사쿠야",
            "similarity": 0.769173,
            "threshold": 0.45,
            "reason": "matched",
            "customer": {
                "preferred_menu": "아메리카노",
                "preferred_temperature": "ICE",
                "preferred_quantity": 1,
            },
        }
    )

    assert identity.recognized is True
    assert identity.customer_id == "customer_1"
    assert identity.name == "사쿠야"
    assert identity.similarity == 0.769173
    assert identity.preferred_menu == "아메리카노"
    assert identity.preferred_temperature == "ICE"
    assert identity.preferred_quantity == 1


def test_unmatched_payload_becomes_anonymous():
    identity = parse_face_recognition_payload(
        {
            "matched": False,
            "similarity": 0.31,
            "threshold": 0.45,
            "reason": "below_threshold",
        }
    )

    assert identity.recognized is False
    assert identity.customer_id is None
    assert identity.name is None
    assert identity.reason == "below_threshold"


def test_invalid_json_does_not_raise():
    identity = parse_face_recognition_payload("not-json")

    assert identity.recognized is False
    assert identity.reason == "invalid_json"
