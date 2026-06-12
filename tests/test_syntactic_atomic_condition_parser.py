from src.parser.syntactic_atomic_condition_parser import build_syntax_analysis, parse_condition_line


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


def test_syntactic_parser_treats_is_not_as_not_equal_for_state_value_and_parameter():
    state_condition = parse_condition_line(
        "S_STATUS is not valid",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )
    value_condition = parse_condition_line(
        "S_MODE is not 0x1",
        normalized_entities=[
            {"mention": "S_MODE", "type": "SIGNAL", "canonical_name": "S_MODE"},
            {"mention": "0x1", "type": "VALUE", "canonical_name": "0x1"},
        ],
    )
    parameter_condition = parse_condition_line(
        "S_SPEED is not P_SPEED_LIMIT",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "P_SPEED_LIMIT", "type": "PARAMETER", "canonical_name": "P_SPEED_LIMIT"},
        ],
    )

    assert state_condition["operator"] == "!="
    assert state_condition["required_state"] == "valid"
    assert value_condition["operator"] == "!="
    assert value_condition["value"] == "0x1"
    assert parameter_condition["operator"] == "!="
    assert parameter_condition["parameter"] == "P_SPEED_LIMIT"


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


def test_syntactic_parser_parses_value_signal_value_range_condition():
    parsed = parse_condition_line(
        "0 < S_SPEED < 100",
        normalized_entities=[
            {"mention": "0", "type": "VALUE", "canonical_name": "0"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "100", "type": "VALUE", "canonical_name": "100"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "0 < S_SPEED < 100",
        "signal": "S_SPEED",
        "lower_operator": ">",
        "lower_value": 0,
        "upper_operator": "<",
        "upper_value": 100,
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_parameter_signal_parameter_range_condition():
    parsed = parse_condition_line(
        "P_MIN <= S_SPEED <= P_MAX",
        normalized_entities=[
            {"mention": "P_MIN", "type": "PARAMETER", "canonical_name": "P_MIN"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "P_MAX", "type": "PARAMETER", "canonical_name": "P_MAX"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "P_MIN <= S_SPEED <= P_MAX",
        "signal": "S_SPEED",
        "lower_operator": ">=",
        "lower_parameter": "P_MIN",
        "upper_operator": "<=",
        "upper_parameter": "P_MAX",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_reversed_value_signal_value_range_condition():
    parsed = parse_condition_line(
        "100 >= S_SPEED >= 0",
        normalized_entities=[
            {"mention": "100", "type": "VALUE", "canonical_name": "100"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "0", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "100 >= S_SPEED >= 0",
        "signal": "S_SPEED",
        "lower_operator": ">=",
        "lower_value": 0,
        "upper_operator": "<=",
        "upper_value": 100,
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_reversed_parameter_signal_parameter_range_condition():
    parsed = parse_condition_line(
        "P_MAX > S_SPEED > P_MIN",
        normalized_entities=[
            {"mention": "P_MAX", "type": "PARAMETER", "canonical_name": "P_MAX"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "P_MIN", "type": "PARAMETER", "canonical_name": "P_MIN"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "P_MAX > S_SPEED > P_MIN",
        "signal": "S_SPEED",
        "lower_operator": ">",
        "lower_parameter": "P_MIN",
        "upper_operator": "<",
        "upper_parameter": "P_MAX",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_mixed_reversed_range_condition():
    parsed = parse_condition_line(
        "P_MAX >= S_SPEED > 0",
        normalized_entities=[
            {"mention": "P_MAX", "type": "PARAMETER", "canonical_name": "P_MAX"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "0", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "P_MAX >= S_SPEED > 0",
        "signal": "S_SPEED",
        "lower_operator": ">",
        "lower_value": 0,
        "upper_operator": "<=",
        "upper_parameter": "P_MAX",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_placeholderizes_repeated_same_value_mentions():
    analysis = build_syntax_analysis(
        "assist capability is zero (S_ASSIST_CAPABILITY is equal to zero)",
        [
            {"mention": "assist capability", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "S_ASSIST_CAPABILITY", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "zero", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert analysis["placeholder_text"] == "SIGNAL_1 is VALUE_1 (SIGNAL_2 is equal to VALUE_2)"


def test_syntactic_parser_prefers_explicit_parenthesized_signal_value_definition():
    parsed = parse_condition_line(
        "assist capability is zero (S_ASSIST_CAPABILITY is equal to zero)",
        normalized_entities=[
            {"mention": "assist capability", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "S_ASSIST_CAPABILITY", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "zero", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert parsed == {
        "type": "threshold_condition",
        "mention": "S_ASSIST_CAPABILITY == 0",
        "signal": "S_ASSIST_CAPABILITY",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": None,
        "parser": "syntactic",
        "confidence": {
            "overall": 0.95,
            "structure": 0.95,
            "normalization": 0.95,
        },
        "need_review": False,
    }


def test_syntactic_parser_placeholderizes_repeated_same_state_mentions():
    analysis = build_syntax_analysis(
        "column torque quality is invalid (S_COLUMN_TORQUE_QF is invalid)",
        [
            {"mention": "column torque quality", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert analysis["placeholder_text"] == "SIGNAL_1 is STATE_1 (SIGNAL_2 is STATE_2)"


def test_syntactic_parser_prefers_explicit_parenthesized_signal_state_definition():
    parsed = parse_condition_line(
        "column torque quality is invalid (S_COLUMN_TORQUE_QF is invalid)",
        normalized_entities=[
            {"mention": "column torque quality", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_COLUMN_TORQUE_QF == invalid",
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "invalid",
        "parser": "syntactic",
        "confidence": {
            "overall": 0.95,
            "structure": 0.95,
            "normalization": 0.95,
        },
        "need_review": False,
    }


def test_syntactic_parser_parses_predicateless_signal_state_condition():
    parsed = parse_condition_line(
        "S_COLUMN_TORQUE_QF invalid",
        normalized_entities=[
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_COLUMN_TORQUE_QF == invalid",
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "invalid",
        "parser": "syntactic",
        "confidence": {
            "overall": 0.8,
            "structure": 0.8,
            "normalization": 0.9,
        },
        "need_review": False,
    }


def test_syntactic_parser_parses_parenthesized_signal_state_without_predicate():
    parsed = parse_condition_line(
        "Column Torque QF (S_COLUMN_TORQUE_QF) invalid",
        normalized_entities=[
            {"mention": "Column Torque QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_COLUMN_TORQUE_QF == invalid",
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "invalid",
        "parser": "syntactic",
        "confidence": {
            "overall": 0.9,
            "structure": 0.9,
            "normalization": 0.95,
        },
        "need_review": False,
    }


def test_syntactic_parser_parses_parenthesized_signal_state_with_predicate():
    parsed = parse_condition_line(
        "LDW request (S_LDW_HAPTIC_AVL) is Available",
        normalized_entities=[
            {"mention": "LDW request", "type": "SIGNAL", "canonical_name": "S_LDW_HAPTIC_AVL"},
            {"mention": "S_LDW_HAPTIC_AVL", "type": "SIGNAL", "canonical_name": "S_LDW_HAPTIC_AVL"},
            {"mention": "Available", "type": "STATE", "canonical_name": "Available"},
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": "S_LDW_HAPTIC_AVL == Available",
        "signal": "S_LDW_HAPTIC_AVL",
        "operator": "==",
        "required_state": "Available",
        "parser": "syntactic",
        "confidence": {
            "overall": 0.93,
            "structure": 0.93,
            "normalization": 0.95,
        },
        "need_review": False,
    }


def test_syntactic_parser_parses_component_state_condition():
    parsed = parse_condition_line(
        "EPS is in Degraded",
        normalized_entities=[
            {"mention": "EPS", "type": "COMPONENT", "canonical_name": "EPS"},
            {"mention": "Degraded", "type": "STATE", "canonical_name": "Degraded"},
        ],
    )

    assert parsed == {
        "type": "component_state_condition",
        "mention": "EPS == Degraded",
        "component": "EPS",
        "operator": "==",
        "required_state": "Degraded",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_expands_quantified_component_members_state_condition():
    parsed = parse_condition_line(
        "one of the steering channels is Active",
        normalized_entities=[
            {
                "mention": "steering channels",
                "type": "COMPONENT",
                "canonical_name": "STEERING_CHANNEL",
                "members": ["LEFT_STEERING_CHANNEL", "RIGHT_STEERING_CHANNEL"],
            },
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "OR",
        "quantifier": "ANY_ONE",
        "mention": "one of the steering channels is Active",
        "source_component": "STEERING_CHANNEL",
        "children": [
            {
                "type": "component_state_condition",
                "mention": "LEFT_STEERING_CHANNEL == Active",
                "component": "LEFT_STEERING_CHANNEL",
                "operator": "==",
                "required_state": "Active",
                "need_review": False,
            },
            {
                "type": "component_state_condition",
                "mention": "RIGHT_STEERING_CHANNEL == Active",
                "component": "RIGHT_STEERING_CHANNEL",
                "operator": "==",
                "required_state": "Active",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_fault_in_component_condition():
    parsed = parse_condition_line(
        "DEM_COLUMN_TORQUE_IMPLAUSIBLE in EPS",
        normalized_entities=[
            {
                "mention": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
                "type": "FAULT",
                "canonical_name": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
            },
            {"mention": "EPS", "type": "COMPONENT", "canonical_name": "EPS"},
        ],
    )

    assert parsed == {
        "type": "fault_component_condition",
        "mention": "DEM_COLUMN_TORQUE_IMPLAUSIBLE in EPS",
        "fault": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
        "component": "EPS",
        "relation": "in",
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
