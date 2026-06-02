from src.entity_dictionary_builder import (
    build_signal_dictionary,
    extract_alias_candidates,
    humanize_signal_name,
    suggest_canonical,
)


def test_humanize_signal_name_turns_s_code_into_alias():
    assert humanize_signal_name("S_VEHICLE_SPEED") == "vehicle speed"
    assert humanize_signal_name("S_COLUMN_TORQUE") == "column torque"


def test_build_signal_dictionary_from_signal_rows():
    rows = [
        {"Signal": "S_VEHICLE_SPEED", "Unit": "kph", "Component": "Vehicle"},
        {"Signal": "S_TORQUE_DEMAND", "Unit": "Nm", "Component": "EPS"},
    ]

    entities = build_signal_dictionary(rows, signal_column="Signal")

    speed = entities[0]
    assert speed["canonical_name"] == "S_VEHICLE_SPEED"
    assert speed["type"] == "signal"
    assert speed["unit"] == "kph"
    assert speed["component"] == "Vehicle"
    assert "S_VEHICLE_SPEED" in speed["aliases"]
    assert "vehicle speed" in speed["aliases"]
    assert "vehicle speed signal" in speed["aliases"]


def test_suggest_canonical_matches_humanized_alias():
    dictionary = build_signal_dictionary([{"Signal": "S_VEHICLE_SPEED"}], signal_column="Signal")

    suggestion = suggest_canonical("vehicle speed", dictionary)

    assert suggestion["canonical_name"] == "S_VEHICLE_SPEED"
    assert suggestion["confidence"] >= 0.8


def test_extract_alias_candidates_from_requirement_rows():
    dictionary = build_signal_dictionary(
        [
            {"Signal": "S_VEHICLE_SPEED"},
            {"Signal": "S_DRIVER_TORQUE"},
            {"Signal": "S_TORQUE_DEMAND"},
        ],
        signal_column="Signal",
    )
    requirements = [
        {
            "Req ID": "REQ_101",
            "Requirement": "When vehicle speed is greater than 3kph, EPS shall calculate the torque demand.",
        },
        {
            "Req ID": "REQ_102",
            "Requirement": "With increasing Driver Torque, EPS shall limit S_TORQUE_DEMAND to 2Nm.",
        },
    ]

    candidates = extract_alias_candidates(
        requirements,
        dictionary,
        text_column="Requirement",
        id_column="Req ID",
    )

    by_mention = {candidate["mention"]: candidate for candidate in candidates}
    assert "EPS shall calculate the torque" not in by_mention
    assert by_mention["vehicle speed"]["suggested_canonical"] == "S_VEHICLE_SPEED"
    assert by_mention["vehicle speed"]["status"] == "pending"
    assert by_mention["vehicle speed"]["evidence"] == ["REQ_101"]
    assert by_mention["torque demand"]["suggested_canonical"] == "S_TORQUE_DEMAND"
    assert by_mention["Driver Torque"]["suggested_canonical"] == "S_DRIVER_TORQUE"
    assert by_mention["S_TORQUE_DEMAND"]["suggested_canonical"] == "S_TORQUE_DEMAND"
