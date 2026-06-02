from src.entity_alias_reviewer import filter_approved, review_candidates


def test_review_candidates_keeps_defaults_on_blank_inputs():
    candidates = [
        {
            "mention": "vehicle speed",
            "suggested_canonical": "S_VEHICLE_SPEED",
            "type": "signal",
            "status": "pending",
        }
    ]
    answers = iter(["", "", "approved"])

    reviewed = review_candidates(candidates, input_func=lambda _: next(answers), print_func=lambda _: None)

    assert reviewed[0]["canonical_name"] == "S_VEHICLE_SPEED"
    assert reviewed[0]["type"] == "signal"
    assert reviewed[0]["status"] == "approved"


def test_review_candidates_allows_field_changes():
    candidates = [
        {
            "mention": "driver input torque",
            "suggested_canonical": "S_DRIVER_TORQUE",
            "type": "unknown",
            "status": "pending",
        }
    ]
    answers = iter(["S_DRIVER_INPUT_TORQUE", "signal", "approved"])

    reviewed = review_candidates(candidates, input_func=lambda _: next(answers), print_func=lambda _: None)

    assert reviewed[0]["canonical_name"] == "S_DRIVER_INPUT_TORQUE"
    assert reviewed[0]["type"] == "signal"
    assert reviewed[0]["status"] == "approved"


def test_filter_approved_returns_only_approved_items():
    reviewed = [
        {"mention": "vehicle speed", "status": "approved"},
        {"mention": "bad candidate", "status": "rejected"},
        {"mention": "needs review", "status": "pending"},
    ]

    approved = filter_approved(reviewed)

    assert approved == [{"mention": "vehicle speed", "status": "approved"}]
