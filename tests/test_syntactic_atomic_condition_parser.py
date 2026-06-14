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


def test_syntactic_parser_infers_missing_state_in_single_signal_multi_state_list():
    parsed = parse_condition_line(
        "S_STATUS shall be Active or Degraded or fail operation",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
            {"mention": "Degraded", "type": "STATE", "canonical_name": "Degraded"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert parsed["need_review"] is True
    assert [child["required_state"] for child in parsed["children"]] == ["Active", "Degraded", "fail operation"]
    assert parsed["children"][2]["need_review"] is True
    assert parsed["children"][2]["review_reason"] == "state inferred from syntax"


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


def test_syntactic_parser_expands_at_least_one_signal_members_state_condition_without_of():
    parsed = parse_condition_line(
        "at least one steering channel is Active",
        normalized_entities=[
            {
                "mention": "steering channel",
                "type": "SIGNAL",
                "canonical_name": "S_STEERING_CHANNEL",
                "members": ["S_STEERING_CHANNEL_1", "S_STEERING_CHANNEL_2"],
            },
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert parsed["quantifier"] == "ANY_ONE"
    assert parsed["source_signal"] == "S_STEERING_CHANNEL"
    assert [child["signal"] for child in parsed["children"]] == ["S_STEERING_CHANNEL_1", "S_STEERING_CHANNEL_2"]
    assert [child["required_state"] for child in parsed["children"]] == ["Active", "Active"]


def test_syntactic_parser_keeps_parenthesized_independent_signal_conditions_separate():
    parsed = parse_condition_line(
        "SIGNAL1 is STATE1(SIGNAL2 == FULL)",
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            {"mention": "SIGNAL2", "type": "SIGNAL", "canonical_name": "SIGNAL2"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["need_review"] is True
    assert "nlp_condition" not in parsed
    assert parsed["outer_condition"] == {
        "type": "signal_state_condition",
        "mention": "SIGNAL1 == STATE1",
        "signal": "SIGNAL1",
        "operator": "==",
        "required_state": "STATE1",
        "need_review": False,
        "parser": "syntactic",
    }
    assert parsed["expression_condition"]["type"] == "signal_state_condition"
    assert parsed["expression_condition"]["signal"] == "SIGNAL2"
    assert parsed["expression_condition"]["required_state"] == "FULL"
    assert parsed["expression_condition"]["need_review"] is True
    assert parsed["expression_condition"]["review_reason"] == "state inferred from syntax"
    assert parsed["children"] == [parsed["outer_condition"], parsed["expression_condition"]]


def test_syntactic_parser_keeps_detected_event_with_parenthesized_signal_comparison_duration():
    parsed = parse_condition_line(
        "a xxx is detected in ECU1 (SIGNAL1 < SIGNAL2 for a xxx period of at least P_TIME)",
        normalized_entities=[
            {"mention": "xxx", "type": "FAULT", "canonical_name": "xxx"},
            {"mention": "ECU1", "type": "COMPONENT", "canonical_name": "ECU1"},
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "SIGNAL2", "type": "SIGNAL", "canonical_name": "SIGNAL2"},
            {"mention": "P_TIME", "type": "PARAMETER", "canonical_name": "P_TIME"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["need_review"] is False
    assert "nlp_condition" in parsed
    assert "expression_condition" in parsed
    outer = parsed["nlp_condition"]
    assert outer["type"] == "nlp_condition"
    assert outer["mention"] == "a xxx is detected in ECU1"
    assert outer["predicate"] == "detect"
    assert outer["voice"] == "passive"
    assert outer["subject"] == "xxx"
    assert outer["locations"] == [{"relation": "in", "text": "ECU1", "entity_type": "COMPONENT", "canonical_name": "ECU1"}]
    assert outer["semantic_chunks"] == [
        {"role": "determiner", "text": "a"},
        {"role": "subject", "text": "xxx", "entity_type": "FAULT", "canonical_name": "xxx"},
        {"role": "predicate", "text": "is detected", "lemma": "detect", "voice": "passive"},
        {"role": "location", "relation": "in", "text": "ECU1", "entity_type": "COMPONENT", "canonical_name": "ECU1"},
    ]
    inner = parsed["expression_condition"]
    assert inner == {
        "type": "signal_comparison_condition",
        "mention": "SIGNAL1 < SIGNAL2",
        "left_signal": "SIGNAL1",
        "operator": "<",
        "right_signal": "SIGNAL2",
        "qualifiers": [
            {
                "type": "duration",
                "mention": "for a xxx period of at least P_TIME",
                "parameter": "P_TIME",
                "operator": ">=",
            }
        ],
        "need_review": False,
    }
    assert parsed["children"] == [outer, inner]


def test_syntactic_parser_replaces_state_definition_with_independent_parenthesized_parts():
    parsed = parse_condition_line(
        "Static condition (S_SPEED > P_SPEED_LIMIT)",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "P_SPEED_LIMIT", "type": "PARAMETER", "canonical_name": "P_SPEED_LIMIT"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert "state_definition_condition" not in str(parsed)
    assert parsed["outer_condition"] == parsed["nlp_condition"]
    assert parsed["nlp_condition"] == {
        "type": "nlp_condition",
        "mention": "Static condition",
        "text": "Static condition",
        "predicate": "unknown_relation",
        "semantic_chunks": [{"role": "raw_text", "text": "Static condition"}],
        "known_entities": [],
        "syntax_source": "placeholder",
        "parser": "syntactic",
        "need_review": True,
        "review_reason": "natural-language condition parsed by nlp fallback",
    }
    assert parsed["expression_condition"] == {
        "type": "parameter_threshold_condition",
        "mention": "S_SPEED > P_SPEED_LIMIT",
        "signal": "S_SPEED",
        "operator": ">",
        "parameter": "P_SPEED_LIMIT",
        "need_review": False,
        "parser": "syntactic",
    }
    assert parsed["children"] == [parsed["nlp_condition"], parsed["expression_condition"]]


def test_syntactic_parser_preserves_incomplete_nlp_fragment_as_itself():
    parsed = parse_condition_line(
        "in ECU1",
        normalized_entities=[
            {"mention": "ECU1", "type": "COMPONENT", "canonical_name": "ECU1"},
        ],
    )

    assert parsed["type"] == "nlp_condition"
    assert parsed["mention"] == "in ECU1"
    assert parsed["text"] == "in ECU1"
    assert parsed["predicate"] == "unknown_relation"
    assert parsed["semantic_chunks"] == [
        {"role": "raw_text", "text": "in ECU1"},
    ]
    assert parsed["known_entities"] == [{"mention": "ECU1", "type": "COMPONENT", "canonical_name": "ECU1"}]
    assert parsed["need_review"] is True
    assert parsed["review_reason"] == "incomplete natural-language condition"


def test_syntactic_parser_keeps_signal_alias_parentheses_out_of_nlp_segment_composer():
    parsed = parse_condition_line(
        "Driver torque (S_COLUMN_TORQUE) invalid",
        normalized_entities=[
            {"mention": "Driver torque", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE"},
            {"mention": "S_COLUMN_TORQUE", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed["type"] == "signal_state_condition"
    assert parsed["signal"] == "S_COLUMN_TORQUE"
    assert parsed["required_state"] == "invalid"


def test_syntactic_parser_groups_complete_and_or_clauses_without_cross_pairing():
    parsed_and = parse_condition_line(
        "S_STATUS is Active and EPS is Degraded",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
            {"mention": "EPS", "type": "COMPONENT", "canonical_name": "EPS"},
            {"mention": "Degraded", "type": "STATE", "canonical_name": "Degraded"},
        ],
    )
    parsed_or = parse_condition_line(
        "S_STATUS is Active or EPS is Degraded",
        normalized_entities=[
            {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
            {"mention": "EPS", "type": "COMPONENT", "canonical_name": "EPS"},
            {"mention": "Degraded", "type": "STATE", "canonical_name": "Degraded"},
        ],
    )

    assert parsed_and["type"] == "condition_group"
    assert parsed_and["logic"] == "AND"
    assert parsed_and["children"][0]["type"] == "signal_state_condition"
    assert parsed_and["children"][0]["signal"] == "S_STATUS"
    assert parsed_and["children"][0]["required_state"] == "Active"
    assert parsed_and["children"][1]["type"] == "component_state_condition"
    assert parsed_and["children"][1]["component"] == "EPS"
    assert parsed_and["children"][1]["required_state"] == "Degraded"
    assert parsed_or["type"] == "condition_group"
    assert parsed_or["logic"] == "OR"
    assert [child["type"] for child in parsed_or["children"]] == ["signal_state_condition", "component_state_condition"]


def test_syntactic_parser_combines_adjacent_parameter_tokens_as_p_parameter():
    parsed = parse_condition_line(
        "S_SPEED > speed threshold",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "speed", "type": "PARAMETER", "canonical_name": "speed"},
            {"mention": "threshold", "type": "PARAMETER", "canonical_name": "threshold"},
        ],
    )

    assert parsed == {
        "type": "parameter_threshold_condition",
        "mention": "S_SPEED > P_SPEED_THRESHOLD",
        "signal": "S_SPEED",
        "operator": ">",
        "parameter": "P_SPEED_THRESHOLD",
        "need_review": False,
        "parser": "syntactic",
    }


def test_syntactic_parser_parses_range_between_parameters_as_range_condition():
    parsed = parse_condition_line(
        "S_SPEED is in range between the low speed limit and the high speed limit",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "low speed limit", "type": "PARAMETER", "canonical_name": "low speed limit"},
            {"mention": "high speed limit", "type": "PARAMETER", "canonical_name": "high speed limit"},
        ],
    )

    assert parsed == {
        "type": "range_condition",
        "mention": "S_SPEED is in range between the low speed limit and the high speed limit",
        "signal": "S_SPEED",
        "relation": "in_range",
        "lower_operator": ">=",
        "lower_parameter": "P_LOW_SPEED_LIMIT",
        "upper_operator": "<=",
        "upper_parameter": "P_HIGH_SPEED_LIMIT",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_preserves_action_tail_and_parses_target_range():
    parsed = parse_condition_line(
        "S_SPEED increases to the range between P_SPEED_MIN and P_SPEED_MAX",
        normalized_entities=[
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "increases", "type": "ACTION", "canonical_name": "increase"},
            {"mention": "P_SPEED_MIN", "type": "PARAMETER", "canonical_name": "P_SPEED_MIN"},
            {"mention": "P_SPEED_MAX", "type": "PARAMETER", "canonical_name": "P_SPEED_MAX"},
        ],
    )

    assert parsed == {
        "type": "signal_action_condition",
        "mention": "S_SPEED increases to the range between P_SPEED_MIN and P_SPEED_MAX",
        "signal": "S_SPEED",
        "action": "increase",
        "target_relation": "to",
        "target": {
            "type": "range_condition",
            "mention": "the range between P_SPEED_MIN and P_SPEED_MAX",
            "relation": "in_range",
            "lower_operator": ">=",
            "lower_parameter": "P_SPEED_MIN",
            "upper_operator": "<=",
            "upper_parameter": "P_SPEED_MAX",
            "parser": "syntactic",
            "need_review": False,
        },
        "parser": "syntactic",
        "need_review": False,
    }


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
                "type": "signal_state_condition",
                "mention": "S_REQUEST_1 == Valid",
                "signal": "S_REQUEST_1",
                "operator": "==",
                "required_state": "Valid",
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
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_value_state_clause_as_state_when_value_is_not_separate():
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


def test_syntactic_parser_composes_parenthesized_signal_value_expression_with_outer_formal_condition():
    parsed = parse_condition_line(
        "assist capability is zero (S_ASSIST_CAPABILITY is equal to zero)",
        normalized_entities=[
            {"mention": "assist capability", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "S_ASSIST_CAPABILITY", "type": "SIGNAL", "canonical_name": "S_ASSIST_CAPABILITY"},
            {"mention": "zero", "type": "VALUE", "canonical_name": "0"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert "nlp_condition" not in parsed
    assert parsed["outer_condition"] == {
        "type": "threshold_condition",
        "mention": "assist capability == 0",
        "signal": "S_ASSIST_CAPABILITY",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": None,
        "parser": "syntactic",
        "need_review": False,
    }
    assert parsed["expression_condition"] == {
        "type": "threshold_condition",
        "mention": "S_ASSIST_CAPABILITY == 0",
        "signal": "S_ASSIST_CAPABILITY",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": None,
        "parser": "syntactic",
        "need_review": False,
    }
    assert parsed["children"] == [parsed["outer_condition"], parsed["expression_condition"]]


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


def test_syntactic_parser_composes_parenthesized_signal_state_expression_with_outer_formal_condition():
    parsed = parse_condition_line(
        "column torque quality is invalid (S_COLUMN_TORQUE_QF is invalid)",
        normalized_entities=[
            {"mention": "column torque quality", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert "nlp_condition" not in parsed
    assert parsed["outer_condition"] == {
        "type": "signal_state_condition",
        "mention": "column torque quality == invalid",
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "invalid",
        "parser": "syntactic",
        "need_review": False,
    }
    assert parsed["expression_condition"] == {
        "type": "signal_state_condition",
        "mention": "S_COLUMN_TORQUE_QF == invalid",
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "invalid",
        "parser": "syntactic",
        "need_review": False,
    }
    assert parsed["children"] == [parsed["outer_condition"], parsed["expression_condition"]]


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


def test_syntactic_parser_preserves_component_state_modifier():
    parsed = parse_condition_line(
        "EPS Initialization is completely finished",
        normalized_entities=[
            {"mention": "EPS Initialization", "type": "COMPONENT", "canonical_name": "EPS_INITIALIZATION"},
            {"mention": "finished", "type": "STATE", "canonical_name": "finished"},
        ],
    )

    assert parsed == {
        "type": "component_state_condition",
        "mention": "EPS Initialization == completely finished",
        "component": "EPS_INITIALIZATION",
        "operator": "==",
        "required_state": "finished",
        "state_phrase": "completely finished",
        "state_modifier": "completely",
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


def test_syntactic_parser_ignores_entity_wrapper_braces_in_placeholder_rules():
    fault = parse_condition_line(
        "{DEM_COLUMN_TORQUE_IMPLAUSIBLE} in {EPS}",
        normalized_entities=[
            {
                "mention": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
                "type": "FAULT",
                "canonical_name": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
            },
            {"mention": "EPS", "type": "COMPONENT", "canonical_name": "EPS"},
        ],
    )
    range_condition = parse_condition_line(
        "0 < {S_SPEED} < 100",
        normalized_entities=[
            {"mention": "0", "type": "VALUE", "canonical_name": "0"},
            {"mention": "S_SPEED", "type": "SIGNAL", "canonical_name": "S_SPEED"},
            {"mention": "100", "type": "VALUE", "canonical_name": "100"},
        ],
    )
    bare_state = parse_condition_line(
        "{S_COLUMN_TORQUE_QF} invalid",
        normalized_entities=[
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )
    quantified_component = parse_condition_line(
        "one of the {steering channels} is Active",
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
    analysis = build_syntax_analysis(
        "{S_COLUMN_TORQUE_QF} invalid",
        [
            {"mention": "S_COLUMN_TORQUE_QF", "type": "SIGNAL", "canonical_name": "S_COLUMN_TORQUE_QF"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "invalid"},
        ],
    )

    assert analysis["placeholder_text"] == "SIGNAL_1 STATE_1"
    assert fault["type"] == "fault_component_condition"
    assert range_condition["type"] == "range_condition"
    assert bare_state["type"] == "signal_state_condition"
    assert quantified_component["type"] == "condition_group"
    assert quantified_component["quantifier"] == "ANY_ONE"


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


def test_syntactic_parser_parses_feature_state_condition():
    parsed = parse_condition_line(
        "ADS torque control is Active",
        normalized_entities=[
            {"mention": "ADS torque control", "type": "FEATURE", "canonical_name": "F_ADS_TORQUE_CONTROL"},
            {"mention": "Active", "type": "STATE", "canonical_name": "Active"},
        ],
    )

    assert parsed == {
        "type": "feature_state_condition",
        "mention": "ADS torque control == Active",
        "feature": "F_ADS_TORQUE_CONTROL",
        "operator": "==",
        "required_state": "Active",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_feature_action_condition():
    parsed = parse_condition_line(
        "ADS torque control exits",
        normalized_entities=[
            {"mention": "ADS torque control", "type": "FEATURE", "canonical_name": "F_ADS_TORQUE_CONTROL"},
            {"mention": "exits", "type": "ACTION", "canonical_name": "exit"},
        ],
    )

    assert parsed == {
        "type": "feature_action_condition",
        "mention": "ADS torque control -> exit",
        "feature": "F_ADS_TORQUE_CONTROL",
        "action": "exit",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_cleans_unbalanced_entity_parenthesis_before_placeholderizing():
    parsed = parse_condition_line(
        "vehicle speed is valid",
        normalized_entities=[
            {"mention": "(vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "valid)", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert parsed["type"] == "signal_state_condition"
    assert parsed["signal"] == "S_VEHICLE_SPEED"
    assert parsed["required_state"] == "valid"


def test_syntactic_parser_splits_value_state_enum_when_entities_are_missing():
    parsed = parse_condition_line(
        'S_MODE is equal to "0x1: Valid"',
        normalized_entities=[
            {"mention": "S_MODE", "type": "SIGNAL", "canonical_name": "S_MODE"},
        ],
    )

    assert parsed["type"] == "signal_state_condition"
    assert parsed["signal"] == "S_MODE"
    assert parsed["required_state"] == "Valid"
    assert parsed["need_review"] is True
    assert parsed["review_reason"] == "state inferred from enum label"
    assert parsed["enum_value"] == "0x1"


def test_syntactic_parser_parses_symbol_state_equality_and_inequality():
    for text, operator in (
        ("SIGNAL1 != STATE1", "!="),
        ("SIGNAL1 = STATE1", "=="),
        ('SIGNAL1 = "STATE1"', "=="),
    ):
        parsed = parse_condition_line(
            text,
            normalized_entities=[
                {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
                {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            ],
        )

        assert parsed["type"] == "signal_state_condition"
        assert parsed["signal"] == "SIGNAL1"
        assert parsed["operator"] == operator
        assert parsed["required_state"] == "STATE1"
        assert parsed["need_review"] is False


def test_syntactic_parser_keeps_shared_enum_value_state_as_enum_conditions_for_multiple_signals():
    parsed = parse_condition_line(
        'SIGNAL1 and SIGNAL2 are equal to "VALUE1:STATE1"',
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "SIGNAL2", "type": "SIGNAL", "canonical_name": "SIGNAL2"},
            {"mention": "VALUE1", "type": "VALUE", "canonical_name": "VALUE1"},
            {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": 'SIGNAL1 and SIGNAL2 are equal to "VALUE1:STATE1"',
        "children": [
            {
                "type": "signal_enum_condition",
                "mention": 'SIGNAL1 == "VALUE1:STATE1"',
                "signal": "SIGNAL1",
                "operator": "==",
                "value": "VALUE1",
                "required_state": "STATE1",
                "need_review": False,
            },
            {
                "type": "signal_enum_condition",
                "mention": 'SIGNAL2 == "VALUE1:STATE1"',
                "signal": "SIGNAL2",
                "operator": "==",
                "value": "VALUE1",
                "required_state": "STATE1",
                "need_review": False,
            },
        ],
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_keeps_enum_value_state_options_as_enum_conditions_for_one_signal():
    parsed = parse_condition_line(
        'SIGNAL1 is equal to "VALUE1:STATE1" or "VALUE2:STATE2"',
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "VALUE1", "type": "VALUE", "canonical_name": "VALUE1"},
            {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            {"mention": "VALUE2", "type": "VALUE", "canonical_name": "VALUE2"},
            {"mention": "STATE2", "type": "STATE", "canonical_name": "STATE2"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert [child["type"] for child in parsed["children"]] == ["signal_enum_condition", "signal_enum_condition"]
    assert [(child["value"], child["required_state"]) for child in parsed["children"]] == [
        ("VALUE1", "STATE1"),
        ("VALUE2", "STATE2"),
    ]
    assert [child["signal"] for child in parsed["children"]] == ["SIGNAL1", "SIGNAL1"]


def test_syntactic_parser_keeps_malformed_quoted_enum_option_as_enum_condition():
    parsed = parse_condition_line(
        'SIGNAL1 is equal to "VALUE1:STATE1" or "0x1:"STATE2',
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "VALUE1", "type": "VALUE", "canonical_name": "VALUE1"},
            {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            {"mention": "0x1", "type": "VALUE", "canonical_name": "0x1"},
            {"mention": "STATE2", "type": "STATE", "canonical_name": "STATE2"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert [(child["value"], child["required_state"]) for child in parsed["children"]] == [
        ("VALUE1", "STATE1"),
        ("0x1", "STATE2"),
    ]


def test_syntactic_parser_preserves_left_signal_phrase_for_state_conditions():
    for text, expected_mention in (
        ("SIGNAL1 control is STATE1", "SIGNAL1 control == STATE1"),
        ("redundant SIGNAL1 = STATE1", "redundant SIGNAL1 == STATE1"),
    ):
        parsed = parse_condition_line(
            text,
            normalized_entities=[
                {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
                {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            ],
        )

        assert parsed["type"] == "signal_state_condition"
        assert parsed["mention"] == expected_mention
        assert parsed["signal"] == "SIGNAL1"
        assert parsed["required_state"] == "STATE1"


def test_syntactic_parser_preserves_abs_transform_for_parenthesized_signal_parameter_condition():
    parsed = parse_condition_line(
        "abs(SIGNAL1) <= PARAMETER1",
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL1"},
            {"mention": "PARAMETER1", "type": "PARAMETER", "canonical_name": "PARAMETER1"},
        ],
    )

    assert parsed == {
        "type": "parameter_threshold_condition",
        "mention": "ABS(SIGNAL1) <= P_PARAMETER1",
        "signal": "SIGNAL1",
        "operator": "<=",
        "parameter": "P_PARAMETER1",
        "transform": "ABS",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_parses_parenthesized_same_canonical_signal_value_condition():
    parsed = parse_condition_line(
        "SIGNAL1(SIGNAL2) is equal to VALUE1",
        normalized_entities=[
            {"mention": "SIGNAL1", "type": "SIGNAL", "canonical_name": "SIGNAL_CANON"},
            {"mention": "SIGNAL2", "type": "SIGNAL", "canonical_name": "SIGNAL_CANON"},
            {"mention": "VALUE1", "type": "VALUE", "canonical_name": "VALUE1"},
        ],
    )

    assert parsed["type"] == "threshold_condition"
    assert parsed["mention"] == "SIGNAL2 == VALUE1"
    assert parsed["signal"] == "SIGNAL_CANON"
    assert parsed["operator"] == "=="
    assert parsed["value"] == "VALUE1"
    assert parsed["parser"] == "syntactic"
    assert parsed["need_review"] is False


def test_syntactic_parser_parses_complete_component_and_clause_group():
    parsed = parse_condition_line(
        "COMPONENT1 is STATE1 and COMPONENT2 is STATE2",
        normalized_entities=[
            {"mention": "COMPONENT1", "type": "COMPONENT", "canonical_name": "COMPONENT1"},
            {"mention": "STATE1", "type": "STATE", "canonical_name": "STATE1"},
            {"mention": "COMPONENT2", "type": "COMPONENT", "canonical_name": "COMPONENT2"},
            {"mention": "STATE2", "type": "STATE", "canonical_name": "STATE2"},
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert [child["type"] for child in parsed["children"]] == ["component_state_condition", "component_state_condition"]
    assert [child["component"] for child in parsed["children"]] == ["COMPONENT1", "COMPONENT2"]
    assert [child["required_state"] for child in parsed["children"]] == ["STATE1", "STATE2"]


def test_syntactic_parser_parses_parenthesized_signal_trend_condition():
    parsed = parse_condition_line(
        "request torque (actual torque) increases",
        normalized_entities=[
            {"mention": "request torque", "type": "SIGNAL", "canonical_name": "S_REQUEST_TORQUE"},
            {"mention": "actual torque", "type": "SIGNAL", "canonical_name": "S_ACTUAL_TORQUE"},
        ],
    )

    assert parsed == {
        "type": "signal_trend_condition",
        "mention": "actual torque increases",
        "signal": "S_ACTUAL_TORQUE",
        "trend": "increase",
        "context_signal": "S_REQUEST_TORQUE",
        "parser": "syntactic",
        "need_review": False,
    }


def test_syntactic_parser_returns_nlp_condition_for_complete_sentence_without_entities():
    parsed = parse_condition_line("Both steer torque request send valid value", normalized_entities=[])

    assert parsed["type"] == "nlp_condition"
    assert parsed["mention"] == "Both steer torque request send valid value"
    assert parsed["quantifier"] == "ALL"
    assert parsed["predicate"] == "send"
    assert parsed["need_review"] is True
    assert parsed["semantic_chunks"] == [{"role": "raw_text", "text": "Both steer torque request send valid value"}]
    assert parsed["review_reason"] == "natural-language condition parsed by nlp fallback"


def test_syntactic_parser_returns_review_fallback_for_partial_entity_sentence():
    parsed = parse_condition_line(
        "SIGNAL is less than the threshold",
        normalized_entities=[
            {"mention": "SIGNAL", "type": "SIGNAL", "canonical_name": "SIGNAL"},
        ],
    )

    assert parsed["type"] == "syntactic_fallback_condition"
    assert parsed["predicate"] == "<"
    assert parsed["known_entities"][0]["canonical_name"] == "SIGNAL"
    assert "threshold" in parsed["unknown_candidates"]
