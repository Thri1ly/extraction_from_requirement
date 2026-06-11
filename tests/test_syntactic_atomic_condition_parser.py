from src.parser.syntactic_atomic_condition_parser import parse_condition_line


def test_syntactic_parser_expands_single_signal_multi_state_with_shall_be():
    parsed = parse_condition_line(
        "EPS system state shall be LIMP HOME or LIMP ASIDE",
        normalized_entities=[
            {"mention": "EPS system state", "type": "SIGNAL", "canonical_name": "S_EPS_SYSTEM_STATE"},
            {"mention": "LIMP HOME", "type": "STATE", "canonical_name": "LIMP_HOME"},
            {"mention": "LIMP ASIDE", "type": "STATE", "canonical_name": "LIMP_ASIDE"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "OR",
        "mention": "EPS system state shall be LIMP HOME or LIMP ASIDE",
        "children": [
            {
                "type": "signal_state_condition",
                "mention": "EPS system state == LIMP_HOME",
                "signal": "S_EPS_SYSTEM_STATE",
                "operator": "==",
                "required_state": "LIMP_HOME",
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "EPS system state == LIMP_ASIDE",
                "signal": "S_EPS_SYSTEM_STATE",
                "operator": "==",
                "required_state": "LIMP_ASIDE",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_expands_multi_signal_single_state_with_shall_be():
    parsed = parse_condition_line(
        "S_SIG_1, S_SIG_2 and S_SIG_3 shall be invalid",
        normalized_entities=[
            {"mention": "S_SIG_1", "type": "SIGNAL", "canonical_name": "S_SIG_1"},
            {"mention": "S_SIG_2", "type": "SIGNAL", "canonical_name": "S_SIG_2"},
            {"mention": "S_SIG_3", "type": "SIGNAL", "canonical_name": "S_SIG_3"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["parser"] == "syntactic"
    assert [child["signal"] for child in parsed["children"]] == ["S_SIG_1", "S_SIG_2", "S_SIG_3"]
    assert all(child["required_state"] == "invalid" for child in parsed["children"])


def test_syntactic_parser_uses_local_operator_for_state_and_parameter_condition():
    parsed = parse_condition_line(
        "K Factor (S_K_FACTOR_REQUEST) is valid and greater than P_LIMIT",
        normalized_entities=[
            {"mention": "S_K_FACTOR_REQUEST", "type": "SIGNAL", "canonical_name": "S_K_FACTOR_REQUEST"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
            {"mention": "greater than", "type": "OPERATOR", "canonical_name": ">"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": "K Factor (S_K_FACTOR_REQUEST) is valid and greater than P_LIMIT",
        "children": [
            {
                "type": "signal_state_condition",
                "mention": "S_K_FACTOR_REQUEST == valid",
                "signal": "S_K_FACTOR_REQUEST",
                "operator": "==",
                "required_state": "valid",
                "need_review": False,
            },
            {
                "type": "parameter_threshold_condition",
                "mention": "S_K_FACTOR_REQUEST > P_LIMIT",
                "signal": "S_K_FACTOR_REQUEST",
                "operator": ">",
                "parameter": "P_LIMIT",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_expands_at_least_one_signal_members_state_condition():
    parsed = parse_condition_line(
        "At least one of the vehicle speed signal is valid",
        normalized_entities=[
            {
                "mention": "vehicle speed signal",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
            },
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "OR",
        "quantifier": "ANY_ONE",
        "mention": "At least one of the vehicle speed signal is valid",
        "source_signal": "S_VEHICLE_SPEED",
        "children": [
            {
                "type": "signal_state_condition",
                "mention": "S_VEHICLE_SPEED_1 == valid",
                "signal": "S_VEHICLE_SPEED_1",
                "operator": "==",
                "required_state": "valid",
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "S_VEHICLE_SPEED_2 == valid",
                "signal": "S_VEHICLE_SPEED_2",
                "operator": "==",
                "required_state": "valid",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }

    compact = parse_condition_line(
        "Atleast one of vehicle speed signal is valid",
        normalized_entities=[
            {
                "mention": "vehicle speed signal",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
            },
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert compact["type"] == "condition_group"
    assert compact["quantifier"] == "ANY_ONE"
    assert compact["logic"] == "OR"
    assert [child["signal"] for child in compact["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_syntactic_parser_expands_one_of_signal_members_state_condition():
    parsed = parse_condition_line(
        "one of the vehicle speed signal is valid",
        normalized_entities=[
            {
                "mention": "vehicle speed signal",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
            },
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["quantifier"] == "ANY_ONE"
    assert parsed["logic"] == "OR"
    assert parsed["source_signal"] == "S_VEHICLE_SPEED"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_syntactic_parser_expands_both_signal_members_state_condition():
    parsed = parse_condition_line(
        "Both vehicle speed signal are invalid",
        normalized_entities=[
            {
                "mention": "vehicle speed signal",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
            },
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "quantifier": "ALL",
        "mention": "Both vehicle speed signal are invalid",
        "source_signal": "S_VEHICLE_SPEED",
        "children": [
            {
                "type": "signal_state_condition",
                "mention": "S_VEHICLE_SPEED_1 == invalid",
                "signal": "S_VEHICLE_SPEED_1",
                "operator": "==",
                "required_state": "invalid",
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "S_VEHICLE_SPEED_2 == invalid",
                "signal": "S_VEHICLE_SPEED_2",
                "operator": "==",
                "required_state": "invalid",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_treats_equal_to_greater_than_as_greater_or_equal():
    parsed = parse_condition_line(
        "S_K_FACTOR_REQUEST is equal to greater than P_LIMIT",
        normalized_entities=[
            {"mention": "S_K_FACTOR_REQUEST", "type": "SIGNAL", "canonical_name": "S_K_FACTOR_REQUEST"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed == {
        "type": "parameter_threshold_condition",
        "mention": "S_K_FACTOR_REQUEST >= P_LIMIT",
        "signal": "S_K_FACTOR_REQUEST",
        "operator": ">=",
        "parameter": "P_LIMIT",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_treats_equal_to_or_greater_than_as_greater_or_equal():
    parsed = parse_condition_line(
        "S_K_FACTOR_REQUEST is equal to or greater than P_LIMIT",
        normalized_entities=[
            {"mention": "S_K_FACTOR_REQUEST", "type": "SIGNAL", "canonical_name": "S_K_FACTOR_REQUEST"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed == {
        "type": "parameter_threshold_condition",
        "mention": "S_K_FACTOR_REQUEST >= P_LIMIT",
        "signal": "S_K_FACTOR_REQUEST",
        "operator": ">=",
        "parameter": "P_LIMIT",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_treats_equal_or_greater_than_as_greater_or_equal():
    parsed = parse_condition_line(
        "S_K_FACTOR_REQUEST is equal or greater than P_LIMIT",
        normalized_entities=[
            {"mention": "S_K_FACTOR_REQUEST", "type": "SIGNAL", "canonical_name": "S_K_FACTOR_REQUEST"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed["operator"] == ">="
    assert parsed["mention"] == "S_K_FACTOR_REQUEST >= P_LIMIT"


def test_syntactic_parser_parses_or_signal_value_state_clauses():
    parsed = parse_condition_line(
        '(receiving) S_REQUEST_1 is equal to "0x1: Valid" or '
        '(indicate internal signal) S_REQUEST_2 is equal to "0x2: Invalid"',
        normalized_entities=[
            {"mention": "S_REQUEST_1", "type": "SIGNAL", "canonical_name": "S_REQUEST_1"},
            {"mention": "0x1", "type": "VALUE", "canonical_name": "0x1"},
            {"mention": "Valid", "type": "STATE", "canonical_name": "Valid"},
            {"mention": "S_REQUEST_2", "type": "SIGNAL", "canonical_name": "S_REQUEST_2"},
            {"mention": "0x2", "type": "VALUE", "canonical_name": "0x2"},
            {"mention": "Invalid", "type": "STATE", "canonical_name": "Invalid"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "OR",
        "mention": '(receiving) S_REQUEST_1 is equal to "0x1: Valid" or '
        '(indicate internal signal) S_REQUEST_2 is equal to "0x2: Invalid"',
        "children": [
            {
                "type": "condition_group",
                "logic": "AND",
                "mention": "S_REQUEST_1 == 0x1:Valid",
                "children": [
                    {
                        "type": "threshold_condition",
                        "mention": "S_REQUEST_1 == 0x1",
                        "signal": "S_REQUEST_1",
                        "transform": None,
                        "operator": "==",
                        "value": "0x1",
                        "unit": None,
                        "need_review": False,
                    },
                    {
                        "type": "signal_state_condition",
                        "mention": "S_REQUEST_1 == Valid",
                        "signal": "S_REQUEST_1",
                        "operator": "==",
                        "required_state": "Valid",
                        "need_review": False,
                    },
                ],
                "need_review": False,
            },
            {
                "type": "condition_group",
                "logic": "AND",
                "mention": "S_REQUEST_2 == 0x2:Invalid",
                "children": [
                    {
                        "type": "threshold_condition",
                        "mention": "S_REQUEST_2 == 0x2",
                        "signal": "S_REQUEST_2",
                        "transform": None,
                        "operator": "==",
                        "value": "0x2",
                        "unit": None,
                        "need_review": False,
                    },
                    {
                        "type": "signal_state_condition",
                        "mention": "S_REQUEST_2 == Invalid",
                        "signal": "S_REQUEST_2",
                        "operator": "==",
                        "required_state": "Invalid",
                        "need_review": False,
                    },
                ],
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_falls_back_to_legacy_threshold_parser():
    parsed = parse_condition_line(
        "S_SPEED > 10kph",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "10kph", "type": "VALUE", "canonical_name": "10kph"},
        ],
    )

    assert parsed["type"] == "threshold_condition"
    assert parsed["signal"] == "S_SPEED"
    assert parsed["operator"] == ">"
    assert parsed["value"] == 10
