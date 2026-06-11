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
