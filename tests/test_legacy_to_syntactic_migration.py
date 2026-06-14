from src.parser.syntactic_atomic_condition_parser import parse_condition_line


def test_migrates_signal_state_and_parameter_threshold_rule_to_syntactic():
    parsed = parse_condition_line(
        "K Factor (S_K_FACTOR_REQUEST) is valid and greater than P_LIMIT",
        normalized_entities=[
            {"mention": "S_K_FACTOR_REQUEST", "type": "SIGNAL", "canonical_name": "S_K_FACTOR_REQUEST"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
            {"mention": "greater than", "type": "OPERATOR", "canonical_name": ">"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed["parser"] == "syntactic"
    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert [(child["type"], child["operator"]) for child in parsed["children"]] == [
        ("signal_state_condition", "=="),
        ("parameter_threshold_condition", ">"),
    ]
    assert parsed["children"][0]["required_state"] == "valid"
    assert parsed["children"][1]["parameter"] == "P_LIMIT"


def test_migrates_single_signal_value_state_rule_to_syntactic_state_only_output():
    parsed = parse_condition_line(
        'S_MODE is equal to "0x1: Valid"',
        normalized_entities=[
            {"mention": "S_MODE", "type": "SIGNAL", "canonical_name": "S_MODE"},
            {"mention": "0x1: Valid", "type": "STATE", "canonical_name": "Valid"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_MODE == Valid",
        "signal": "S_MODE",
        "operator": "==",
        "required_state": "Valid",
        "parser": "syntactic",
        "need_review": False,
    }


def test_migrates_multi_signal_value_rule_to_syntactic():
    parsed = parse_condition_line(
        "{Column Torque} and {Column Velocity} are equal to zero",
        normalized_entities=[
            {"mention": "Column Torque", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE"},
            {"mention": "Column Velocity", "type": "SIGNAL", "canonical_name": "S_COLUMN_VELOCITY"},
            {"mention": "zero", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert parsed["parser"] == "syntactic"
    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert [child["signal"] for child in parsed["children"]] == ["S_COLUMN_TORQUE", "S_COLUMN_VELOCITY"]
    assert all(child["type"] == "threshold_condition" for child in parsed["children"])
    assert all(child["operator"] == "==" for child in parsed["children"])
    assert all(child["value"] == 0 for child in parsed["children"])


def test_migrates_single_signal_multi_state_rule_to_syntactic():
    parsed = parse_condition_line(
        "EPS system state shall be LIMP HOME or LIMP ASIDE",
        normalized_entities=[
            {"mention": "EPS system state", "type": "SIGNAL", "canonical_name": "S_EPS_SYSTEM_STATE"},
            {"mention": "LIMP HOME", "type": "STATE", "canonical_name": "LIMP_HOME"},
            {"mention": "LIMP ASIDE", "type": "STATE", "canonical_name": "LIMP_ASIDE"},
        ],
    )

    assert parsed["parser"] == "syntactic"
    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert [child["required_state"] for child in parsed["children"]] == ["LIMP_HOME", "LIMP_ASIDE"]


def test_migrates_multi_signal_single_state_rule_to_syntactic():
    parsed = parse_condition_line(
        "S_SIG_1, S_SIG_2 and S_SIG_3 shall be invalid",
        normalized_entities=[
            {"mention": "S_SIG_1", "type": "SIGNAL", "canonical_name": "S_SIG_1"},
            {"mention": "S_SIG_2", "type": "SIGNAL", "canonical_name": "S_SIG_2"},
            {"mention": "S_SIG_3", "type": "SIGNAL", "canonical_name": "S_SIG_3"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed["parser"] == "syntactic"
    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert [child["signal"] for child in parsed["children"]] == ["S_SIG_1", "S_SIG_2", "S_SIG_3"]
    assert all(child["required_state"] == "invalid" for child in parsed["children"])


def test_migrates_signal_state_rule_to_syntactic():
    parsed = parse_condition_line(
        "S_STATUS is not valid",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_STATUS != valid",
        "signal": "S_STATUS",
        "operator": "!=",
        "required_state": "valid",
        "parser": "syntactic",
        "need_review": False,
    }


def test_migrates_signal_state_duration_qualifier_to_syntactic():
    parsed = parse_condition_line(
        "S_STATUS is equal to valid for a period of P_DURATION_TIME",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
            {"mention": "P_DURATION_TIME", "type": "PARAMETER", "canonical_name": "P_DURATION_TIME"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_STATUS == valid",
        "signal": "S_STATUS",
        "operator": "==",
        "required_state": "valid",
        "need_review": False,
        "qualifiers": [
            {"type": "duration", "mention": "for a period of P_DURATION_TIME", "parameter": "P_DURATION_TIME"}
        ],
        "parser": "syntactic",
    }


def test_migrates_signal_value_duration_qualifier_to_syntactic():
    parsed = parse_condition_line(
        "S_STATUS is zero within P_DURATION_TIME",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "zero", "type": "VALUE", "canonical_name": "0"},
            {"mention": "P_DURATION_TIME", "type": "PARAMETER", "canonical_name": "P_DURATION_TIME"},
        ],
    )

    assert parsed == {
        "type": "threshold_condition",
        "mention": "S_STATUS == 0",
        "signal": "S_STATUS",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": None,
        "need_review": False,
        "qualifiers": [
            {
                "type": "duration",
                "mention": "within P_DURATION_TIME",
                "parameter": "P_DURATION_TIME",
                "operator": "<=",
            }
        ],
        "parser": "syntactic",
    }


def test_migrates_signal_parameter_duration_qualifier_to_syntactic():
    parsed = parse_condition_line(
        "S_SPEED > P_SPEED_LIMIT for >= P_DURATION_TIME",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "P_SPEED_LIMIT", "type": "PARAMETER", "canonical_name": "P_SPEED_LIMIT"},
            {"mention": "P_DURATION_TIME", "type": "PARAMETER", "canonical_name": "P_DURATION_TIME"},
        ],
    )

    assert parsed == {
        "type": "parameter_threshold_condition",
        "mention": "S_SPEED > P_SPEED_LIMIT",
        "signal": "S_SPEED",
        "operator": ">",
        "parameter": "P_SPEED_LIMIT",
        "need_review": False,
        "qualifiers": [
            {
                "type": "duration",
                "mention": "for >= P_DURATION_TIME",
                "parameter": "P_DURATION_TIME",
                "operator": ">=",
            }
        ],
        "parser": "syntactic",
    }


def test_migrates_duration_qualifier_phrase_variants_to_syntactic():
    samples = [
        ("within P_DURATION_TIME", "<="),
        ("for more than P_DURATION_TIME", ">"),
        ("for longer than P_DURATION_TIME", ">"),
        ("exceeds the duration time", ">"),
        ("exceeding debounce time", ">"),
        ("for a duration of P_DURATION_TIME", None),
        ("for the duration time of P_DURATION_TIME", None),
        ("for a duration greater than P_DURATION_TIME", ">"),
        ("for the duration time less than P_DURATION_TIME", "<"),
        ("for >= P_DURATION_TIME", ">="),
        ("for > P_DURATION_TIME", ">"),
        ("for < P_DURATION_TIME", "<"),
        ("for <= P_DURATION_TIME", "<="),
    ]

    for phrase, expected_operator in samples:
        parameter_mention = "duration time" if "duration time" in phrase and "P_DURATION_TIME" not in phrase else (
            "debounce time" if "debounce time" in phrase and "P_DURATION_TIME" not in phrase else "P_DURATION_TIME"
        )
        parsed = parse_condition_line(
            f"S_STATUS is valid {phrase}",
            normalized_entities=[
                {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
                {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
                {"mention": parameter_mention, "type": "PARAMETER", "canonical_name": "P_DURATION_TIME"},
            ],
        )

        assert parsed["parser"] == "syntactic", phrase
        assert parsed["type"] == "signal_state_condition", phrase
        assert parsed["qualifiers"][0]["type"] == "duration", phrase
        assert parsed["qualifiers"][0]["mention"] == phrase, phrase
        assert parsed["qualifiers"][0]["parameter"] == "P_DURATION_TIME", phrase
        if expected_operator:
            assert parsed["qualifiers"][0]["operator"] == expected_operator, phrase
        else:
            assert "operator" not in parsed["qualifiers"][0], phrase
