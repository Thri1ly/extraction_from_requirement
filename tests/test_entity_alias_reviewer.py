import json

from src.entity_alias_reviewer import filter_approved, review_candidates, review_candidates_resumable


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
    assert reviewed[0]["type"] == "SIGNAL"
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
    assert reviewed[0]["type"] == "SIGNAL"
    assert reviewed[0]["status"] == "approved"


def test_filter_approved_returns_only_approved_items():
    reviewed = [
        {"mention": "vehicle speed", "status": "approved"},
        {"mention": "bad candidate", "status": "rejected"},
        {"mention": "needs review", "status": "pending"},
    ]

    approved = filter_approved(reviewed)

    assert approved == [{"mention": "vehicle speed", "status": "approved"}]


def test_resumable_review_saves_after_each_candidate(tmp_path):
    candidates = [
        {"mention": "vehicle speed", "suggested_canonical": "S_VEHICLE_SPEED", "type": "SIGNAL", "status": "pending"},
        {"mention": "MIL", "suggested_canonical": "MIL", "type": "INDICATOR", "status": "pending"},
    ]
    reviewed_path = tmp_path / "reviewed.jsonl"
    approved_path = tmp_path / "approved.jsonl"
    answers = iter(["", "", "approved"])

    def stop_after_first(_prompt):
        return next(answers)

    try:
        review_candidates_resumable(
            candidates,
            reviewed_output=reviewed_path,
            approved_output=approved_path,
            input_func=stop_after_first,
            print_func=lambda _: None,
        )
    except StopIteration:
        pass

    reviewed_rows = [json.loads(line) for line in reviewed_path.read_text(encoding="utf-8").splitlines()]
    approved_rows = [json.loads(line) for line in approved_path.read_text(encoding="utf-8").splitlines()]
    assert len(reviewed_rows) == 1
    assert reviewed_rows[0]["mention"] == "vehicle speed"
    assert approved_rows == reviewed_rows


def test_resumable_review_skips_previously_reviewed_candidates(tmp_path):
    candidates = [
        {"mention": "vehicle speed", "suggested_canonical": "S_VEHICLE_SPEED", "type": "SIGNAL", "status": "pending"},
        {"mention": "MIL", "suggested_canonical": "MIL", "type": "INDICATOR", "status": "pending"},
    ]
    reviewed_path = tmp_path / "reviewed.jsonl"
    approved_path = tmp_path / "approved.jsonl"
    reviewed_path.write_text(
        json.dumps(
            {
                "mention": "vehicle speed",
                "suggested_canonical": "S_VEHICLE_SPEED",
                "canonical_name": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "status": "approved",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    answers = iter(["", "", "rejected"])

    reviewed, approved = review_candidates_resumable(
        candidates,
        reviewed_output=reviewed_path,
        approved_output=approved_path,
        input_func=lambda _: next(answers),
        print_func=lambda _: None,
    )

    assert [item["mention"] for item in reviewed] == ["vehicle speed", "MIL"]
    assert [item["mention"] for item in approved] == ["vehicle speed"]
    reviewed_rows = [json.loads(line) for line in reviewed_path.read_text(encoding="utf-8").splitlines()]
    assert [item["mention"] for item in reviewed_rows] == ["vehicle speed", "MIL"]
