from src.parser.condition_block_extractor import extract_condition_blocks
from src.parser.condition_logic_parser import parse_condition_logic
from src.parser.condition_parser import parse_conditions
from src.parser.atomic_condition_parser import parse_atomic_conditions, parse_condition_line


def by_type(items, condition_type):
    return [item for item in items if item["type"] == condition_type]


def test_parse_signal_state_condition_from_normalized_entities():
    parsed = parse_condition_line(
        'S_COLUMN_TORQUE_QF is equal to "FULL"',
        normalized_entities=[
            {
                "mention": "S_COLUMN_TORQUE_QF",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_TORQUE_QF",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "EQUAL TO",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "FULL",
                "type": "STATE",
                "canonical_name": "FULL",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed == {
        "type": "signal_state_condition",
        "mention": 'S_COLUMN_TORQUE_QF is equal to "FULL"',
        "signal": "S_COLUMN_TORQUE_QF",
        "operator": "==",
        "required_state": "FULL",
        "need_review": False,
    }


def test_parse_multi_signal_shared_zero_value_condition():
    parsed = parse_condition_line(
        "{Column Torque} and {Column Velocity} are equal to zero",
        normalized_entities=[
            {
                "mention": "Column Torque",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_TORQUE",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "Column Velocity",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_VELOCITY",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "EQUAL TO",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "zero",
                "type": "VALUE",
                "canonical_name": "0",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": "{Column Torque} and {Column Velocity} are equal to zero",
        "children": [
            {
                "type": "threshold_condition",
                "mention": "Column Torque == 0",
                "signal": "S_COLUMN_TORQUE",
                "transform": None,
                "operator": "==",
                "value": 0,
                "unit": None,
                "need_review": False,
            },
            {
                "type": "threshold_condition",
                "mention": "Column Velocity == 0",
                "signal": "S_COLUMN_VELOCITY",
                "transform": None,
                "operator": "==",
                "value": 0,
                "unit": None,
                "need_review": False,
            },
        ],
        "need_review": False,
    }


def test_parse_multi_signal_shared_value_state_label_condition():
    parsed = parse_condition_line(
        'S_DSR_VDC_REQUEST1 AND S_DSR_VDC_REQUEST2 are equal to "0x1: Valid"',
        normalized_entities=[
            {
                "mention": "S_DSR_VDC_REQUEST1",
                "type": "SIGNAL",
                "canonical_name": "S_DSR_VDC_REQUEST1",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "S_DSR_VDC_REQUEST2",
                "type": "SIGNAL",
                "canonical_name": "S_DSR_VDC_REQUEST2",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "==",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "0x1",
                "type": "VALUE",
                "canonical_name": "0x1",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Valid",
                "type": "STATE",
                "canonical_name": "Valid",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": 'S_DSR_VDC_REQUEST1 AND S_DSR_VDC_REQUEST2 are equal to "0x1: Valid"',
        "children": [
            {
                "type": "threshold_condition",
                "mention": "S_DSR_VDC_REQUEST1 == 0x1",
                "signal": "S_DSR_VDC_REQUEST1",
                "transform": None,
                "operator": "==",
                "value": "0x1",
                "unit": None,
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "S_DSR_VDC_REQUEST1 == Valid",
                "signal": "S_DSR_VDC_REQUEST1",
                "operator": "==",
                "required_state": "Valid",
                "need_review": False,
            },
            {
                "type": "threshold_condition",
                "mention": "S_DSR_VDC_REQUEST2 == 0x1",
                "signal": "S_DSR_VDC_REQUEST2",
                "transform": None,
                "operator": "==",
                "value": "0x1",
                "unit": None,
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "S_DSR_VDC_REQUEST2 == Valid",
                "signal": "S_DSR_VDC_REQUEST2",
                "operator": "==",
                "required_state": "Valid",
                "need_review": False,
            },
        ],
        "need_review": False,
    }


def test_parse_multi_signal_shared_value_state_label_condition_with_not_equal_operator():
    parsed = parse_condition_line(
        'LDW request (S_LDW_HAPTIC_AVL) is not equal to "0x1: Available"',
        normalized_entities=[
            {
                "mention": "LDW request",
                "type": "SIGNAL",
                "canonical_name": "S_LDW_REQUEST",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "S_LDW_HAPTIC_AVL",
                "type": "SIGNAL",
                "canonical_name": "S_LDW_HAPTIC_AVL",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "not equal to",
                "type": "OPERATOR",
                "canonical_name": "NOT EQUAL TO",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "0x1",
                "type": "VALUE",
                "canonical_name": "0x1",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Available",
                "type": "STATE",
                "canonical_name": "Available",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed["type"] == "condition_group"
    assert [child["operator"] for child in parsed["children"]] == ["!=", "!=", "!=", "!="]
    assert parsed["children"][0]["signal"] == "S_LDW_REQUEST"
    assert parsed["children"][1]["required_state"] == "Available"
    assert parsed["children"][2]["signal"] == "S_LDW_HAPTIC_AVL"
    assert parsed["children"][3]["required_state"] == "Available"


def test_parse_single_signal_value_state_label_condition():
    parsed = parse_condition_line(
        'S_DRIVER_OVERRIDE_STATUS is equal to "0x1: Override"',
        normalized_entities=[
            {
                "mention": "S_DRIVER_OVERRIDE_STATUS",
                "type": "SIGNAL",
                "canonical_name": "S_DRIVER_OVERRIDE_STATUS",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "==",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "0x1",
                "type": "VALUE",
                "canonical_name": "0x1",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Override",
                "type": "STATE",
                "canonical_name": "Override",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": 'S_DRIVER_OVERRIDE_STATUS is equal to "0x1: Override"',
        "children": [
            {
                "type": "threshold_condition",
                "mention": "S_DRIVER_OVERRIDE_STATUS == 0x1",
                "signal": "S_DRIVER_OVERRIDE_STATUS",
                "transform": None,
                "operator": "==",
                "value": "0x1",
                "unit": None,
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": "S_DRIVER_OVERRIDE_STATUS == Override",
                "signal": "S_DRIVER_OVERRIDE_STATUS",
                "operator": "==",
                "required_state": "Override",
                "need_review": False,
            },
        ],
        "need_review": False,
    }


def test_parse_bracketed_definition_does_not_expand_unclear_outer_signals_to_zero():
    conditions = parse_atomic_conditions(
        "no input torque and no column movement condition ({Column Torque} and {Column Velocity} are equal to zero)",
        normalized_entities=[
            {
                "mention": "input torque",
                "type": "SIGNAL",
                "canonical_name": "S_INPUT_TORQUE",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "column movement condition",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_MOVEMENT_CONDITION",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Column Torque",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_TORQUE",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "Column Velocity",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_VELOCITY",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "==",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "zero",
                "type": "VALUE",
                "canonical_name": "0",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert len(conditions) == 1
    definition_children = conditions[0]["definition"]["children"]
    assert [child["signal"] for child in definition_children] == ["S_COLUMN_TORQUE", "S_COLUMN_VELOCITY"]


def test_parse_static_condition_uses_bracketed_numeric_definition_not_outer_state():
    parsed = parse_condition_line(
        "static condition({Column Velocity} is equal to 0rev/s)",
        normalized_entities=[
            {
                "mention": "static condition",
                "type": "STATE",
                "canonical_name": "StaticCondition",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Column Velocity",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_VELOCITY",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "EQUAL TO",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "0rev/s",
                "type": "VALUE",
                "canonical_name": "0rev/s",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed["type"] == "state_definition_condition"
    assert parsed["state_name"] == "StaticCondition"
    assert parsed["state_source"] == "dictionary"
    assert parsed["definition"] == {
        "type": "threshold_condition",
        "mention": "Column Velocity == 0rev/s",
        "signal": "S_COLUMN_VELOCITY",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": "rev/s",
        "need_review": False,
    }
    assert parsed["confidence"] == {
        "overall": 0.93,
        "structure": 0.95,
        "state_name": 0.9,
        "definition": 0.95,
    }
    assert parsed["need_review"] is False


def test_parse_static_condition_with_zero_value_uses_bracketed_value_entity():
    parsed = parse_condition_line(
        "static condition({Column Velocity} is equal to zero)",
        normalized_entities=[
            {
                "mention": "static condition",
                "type": "STATE",
                "canonical_name": "StaticCondition",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "Column Velocity",
                "type": "SIGNAL",
                "canonical_name": "S_COLUMN_VELOCITY",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "==",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "zero",
                "type": "VALUE",
                "canonical_name": "0",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed["type"] == "state_definition_condition"
    assert parsed["state_name"] == "StaticCondition"
    assert parsed["definition"] == {
        "type": "threshold_condition",
        "mention": "Column Velocity == 0",
        "signal": "S_COLUMN_VELOCITY",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": None,
        "need_review": False,
    }


def test_parse_bracketed_signal_parameter_threshold_definition():
    parsed = parse_condition_line(
        "vehicle is moving at pre-defined minimum vehicle speed (S_VEHICLE_SPEED >= P_FD_MIN_VEH_SPD)",
        normalized_entities=[
            {
                "mention": "vehicle",
                "type": "COMPONENT",
                "canonical_name": "VEHICLE",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "moving",
                "type": "STATE",
                "canonical_name": "Moving",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "minimum vehicle speed",
                "type": "PARAMETER",
                "canonical_name": "P_FD_MIN_VEH_SPD",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "P_FD_MIN_VEH_SPD",
                "type": "PARAMETER",
                "canonical_name": "P_FD_MIN_VEH_SPD",
                "members": [],
                "source": "rule",
            },
        ],
    )

    assert parsed["type"] == "state_definition_condition"
    assert parsed["state_name"] == "Moving"
    assert parsed["definition"] == {
        "type": "parameter_threshold_condition",
        "mention": "S_VEHICLE_SPEED >= P_FD_MIN_VEH_SPD",
        "signal": "S_VEHICLE_SPEED",
        "operator": ">=",
        "parameter": "P_FD_MIN_VEH_SPD",
        "need_review": False,
    }


def test_signal_state_condition_does_not_accept_threshold_operator():
    parsed = parse_condition_line(
        "S_VEHICLE_SPEED >= moving",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": [],
                "source": "rule",
            },
            {
                "mention": ">=",
                "type": "OPERATOR",
                "canonical_name": ">=",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "moving",
                "type": "STATE",
                "canonical_name": "Moving",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed["type"] == "unparsed_condition"
    assert parsed["need_review"] is True


def test_parse_bracketed_signal_state_and_parameter_threshold_condition():
    parsed = parse_condition_line(
        "K Factor(S_SPC_K_FACTOR_REQUEST) is valid and greater than P_K_FACTOR_THERSHOLD",
        normalized_entities=[
            {
                "mention": "S_SPC_K_FACTOR_REQUEST",
                "type": "SIGNAL",
                "canonical_name": "S_SPC_K_FACTOR_REQUEST",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "valid",
                "type": "STATE",
                "canonical_name": "valid",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "greater than",
                "type": "OPERATOR",
                "canonical_name": "greater than",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "P_K_FACTOR_THERSHOLD",
                "type": "PARAMETER",
                "canonical_name": "P_K_FACTOR_THERSHOLD",
                "members": [],
                "source": "rule",
            },
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "mention": "K Factor(S_SPC_K_FACTOR_REQUEST) is valid and greater than P_K_FACTOR_THERSHOLD",
        "children": [
            {
                "type": "signal_state_condition",
                "mention": "S_SPC_K_FACTOR_REQUEST == valid",
                "signal": "S_SPC_K_FACTOR_REQUEST",
                "operator": "==",
                "required_state": "valid",
                "need_review": False,
            },
            {
                "type": "parameter_threshold_condition",
                "mention": "S_SPC_K_FACTOR_REQUEST > P_K_FACTOR_THERSHOLD",
                "signal": "S_SPC_K_FACTOR_REQUEST",
                "operator": ">",
                "parameter": "P_K_FACTOR_THERSHOLD",
                "need_review": False,
            },
        ],
        "need_review": False,
    }


def test_parse_threshold_condition_with_c_deg_unit():
    parsed = parse_condition_line("S_STEER_ANGLE = 0 c-deg")

    assert parsed == {
        "type": "threshold_condition",
        "mention": "S_STEER_ANGLE = 0 c-deg",
        "signal": "S_STEER_ANGLE",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": "c-deg",
        "need_review": False,
    }


def test_parse_entity_value_condition_with_c_deg_unit():
    parsed = parse_condition_line(
        "S_STEER_ANGLE is equal to 0 c-deg",
        normalized_entities=[
            {
                "mention": "S_STEER_ANGLE",
                "type": "SIGNAL",
                "canonical_name": "S_STEER_ANGLE",
                "members": [],
                "source": "rule",
            },
            {
                "mention": "equal to",
                "type": "OPERATOR",
                "canonical_name": "equal to",
                "members": [],
                "source": "ner",
            },
            {
                "mention": "0 c-deg",
                "type": "VALUE",
                "canonical_name": "0 c-deg",
                "members": [],
                "source": "ner",
            },
        ],
    )

    assert parsed == {
        "type": "threshold_condition",
        "mention": "S_STEER_ANGLE == 0c-deg",
        "signal": "S_STEER_ANGLE",
        "transform": None,
        "operator": "==",
        "value": 0,
        "unit": "c-deg",
        "need_review": False,
    }


def test_parse_both_of_signal_members_are_valid():
    parsed = parse_condition_line(
        "both of S_VEHICLE_SPEED are valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "quantifier": "ALL",
        "mention": "both of S_VEHICLE_SPEED are valid",
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
        "need_review": False,
    }


def test_parse_both_lanes_of_signal_members_are_valid():
    parsed = parse_condition_line(
        "both lanes of S_VEHICLE_SPEED are valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["quantifier"] == "ALL"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_parse_both_lane_signal_members_are_valid_without_of():
    parsed = parse_condition_line(
        "both lane S_VEHICLE_SPEED are valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["quantifier"] == "ALL"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_parse_both_lanes_signal_members_are_valid_without_of():
    parsed = parse_condition_line(
        "both lanes S_VEHICLE_SPEED are valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "AND"
    assert parsed["quantifier"] == "ALL"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_parse_both_signal_members_are_invalid():
    parsed = parse_condition_line(
        "both S_VEHICLE_SPEED are invalid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["logic"] == "AND"
    assert parsed["quantifier"] == "ALL"
    assert [child["required_state"] for child in parsed["children"]] == ["invalid", "invalid"]


def test_parse_one_lane_of_signal_member_is_valid():
    parsed = parse_condition_line(
        "one lane of S_VEHICLE_SPEED is valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert parsed["quantifier"] == "ANY_ONE"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_parse_one_lane_signal_member_is_valid_without_of():
    parsed = parse_condition_line(
        "one lane S_VEHICLE_SPEED is valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
                "source": "rule",
            }
        ],
    )

    assert parsed["type"] == "condition_group"
    assert parsed["logic"] == "OR"
    assert parsed["quantifier"] == "ANY_ONE"
    assert [child["signal"] for child in parsed["children"]] == ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"]


def test_quantified_signal_without_members_needs_review():
    parsed = parse_condition_line(
        "both of S_VEHICLE_SPEED are valid",
        normalized_entities=[
            {
                "mention": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "canonical_name": "S_VEHICLE_SPEED",
                "members": [],
                "source": "rule",
            }
        ],
    )

    assert parsed == {
        "type": "condition_group",
        "logic": "AND",
        "quantifier": "ALL",
        "mention": "both of S_VEHICLE_SPEED are valid",
        "source_signal": "S_VEHICLE_SPEED",
        "children": [],
        "need_review": True,
        "review_reason": "quantified signal has no members to expand",
    }


def test_extract_condition_block_for_below_all_conditions():
    text = """EPS shall transition from Normal state to Degraded state if below ALL conditions are met:
S_VEHICLE_SPEED > 10kph
AND
DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"""

    blocks = extract_condition_blocks(text)

    assert blocks == [
        {
            "block_id": "cond_block_1",
            "trigger": "if below ALL conditions are met",
            "logic_hint": "ALL",
            "action_text": "EPS shall transition from Normal state to Degraded state",
            "condition_text": "S_VEHICLE_SPEED > 10kph\nDEM_COLUMN_TORQUE_IMPLAUSIBLE is Active",
            "condition_lines": ["S_VEHICLE_SPEED > 10kph", "DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"],
            "logic_markers": ["AND"],
        }
    ]


def test_extract_condition_block_uses_configurable_raw_logic_header():
    text = """EPS shall notify driver when following ANY condition is satisfied:
ConditionA
OR
ConditionB"""

    blocks = extract_condition_blocks(text)

    assert blocks == [
        {
            "block_id": "cond_block_1",
            "trigger": "when following ANY condition is satisfied",
            "logic_hint": "ANY",
            "action_text": "EPS shall notify driver",
            "condition_text": "ConditionA\nConditionB",
            "condition_lines": ["ConditionA", "ConditionB"],
            "logic_markers": ["OR"],
        }
    ]


def test_extract_pure_condition_header_before_raw_requirement_compatibility():
    text = """when the following conditions:
ConditionA
AND
ConditionB"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "when the following conditions:"
    assert block["logic_hint"] == "AND"
    assert block["condition_lines"] == ["ConditionA", "ConditionB"]
    assert block["logic_markers"] == ["AND"]


def test_parse_condition_logic_uses_explicit_and_marker():
    block = {
        "block_id": "cond_block_1",
        "logic_hint": None,
        "condition_lines": ["S_VEHICLE_SPEED > 10kph", "AND", "DEM_X is Active"],
    }

    group = parse_condition_logic(block)

    assert group["type"] == "condition_group"
    assert group["logic"] == "AND"
    assert group["children"] == [
        {"type": "condition_line", "text": "S_VEHICLE_SPEED > 10kph"},
        {"type": "condition_line", "text": "DEM_X is Active"},
    ]


def test_parse_conditions_outputs_condition_group_with_atomic_children():
    text = """EPS shall transition from Normal state to Degraded state if below ALL conditions are met:
S_VEHICLE_SPEED > 10kph
AND
DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"""

    conditions = parse_conditions(text)

    group = by_type(conditions, "condition_group")[0]
    assert group["logic"] == "ALL"
    assert group["children"][0]["type"] == "threshold_condition"
    assert group["children"][0]["signal"] == "S_VEHICLE_SPEED"
    assert group["children"][0]["operator"] == ">"
    assert group["children"][0]["value"] == 10
    assert group["children"][0]["unit"] == "kph"
    assert group["children"][1]["type"] == "fault_state_condition"
    assert group["children"][1]["fault_signal"] == "DEM_COLUMN_TORQUE_IMPLAUSIBLE"
    assert group["children"][1]["required_state"] == "Active"


def test_parse_conditions_preserves_flat_conditions_for_existing_consumers():
    conditions = parse_conditions("If S_VEHICLE_SPEED is less than 10kph, EPS shall transition.")

    threshold = by_type(conditions, "threshold_condition")[0]
    assert threshold["signal"] == "S_VEHICLE_SPEED"
    assert threshold["operator"] == "<"
    assert threshold["value"] == 10


def test_extract_single_processed_condition_strips_trigger_keyword():
    blocks = extract_condition_blocks("If S_VEHICLE_SPEED is less than 10kph")

    assert blocks == [
        {
            "block_id": "cond_block_1",
            "trigger": "if",
            "logic_hint": "ALL",
            "action_text": "",
            "condition_text": "S_VEHICLE_SPEED is less than 10kph",
            "condition_lines": ["S_VEHICLE_SPEED is less than 10kph"],
            "logic_markers": [],
            "skipped_lines": [],
        }
    ]


def test_extract_multiline_processed_conditions_uses_header_logic():
    text = """When ANY of the following conditions are met:
Normal Exit
S_VEHICLE_SPEED > 10kph
Fault Exit
DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"""

    blocks = extract_condition_blocks(text)

    assert blocks == [
        {
            "block_id": "cond_block_1",
            "trigger": "When ANY of the following conditions are met:",
            "logic_hint": "ANY",
            "action_text": "",
            "condition_text": "S_VEHICLE_SPEED > 10kph\nDEM_COLUMN_TORQUE_IMPLAUSIBLE is Active",
            "condition_lines": ["S_VEHICLE_SPEED > 10kph", "DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"],
            "logic_markers": [],
            "skipped_lines": [
                {"line": "Normal Exit", "reason": "invalid_condition_line"},
                {"line": "Fault Exit", "reason": "invalid_condition_line"},
            ],
        }
    ]


def test_extract_processed_header_uses_configurable_logic_header():
    text = """while ALL below conditions are fulfilled:
ConditionA
ConditionB"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "while ALL below conditions are fulfilled:"
    assert block["logic_hint"] == "ALL"
    assert block["condition_lines"] == ["ConditionA", "ConditionB"]


def test_extract_multiline_processed_conditions_keeps_logic_markers_without_header_hint():
    text = """S_VEHICLE_SPEED > 10kph
OR
DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"""

    block = extract_condition_blocks(text)[0]

    assert block["logic_hint"] == "OR"
    assert block["logic_markers"] == ["OR"]
    assert block["condition_lines"] == ["S_VEHICLE_SPEED > 10kph", "DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"]


def test_extract_multiline_processed_conditions_strips_line_trigger_and_excludes_markers():
    text = """When ABC is active
AND
column torque is greater than 5Nm"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "when"
    assert block["logic_hint"] == "AND"
    assert block["logic_markers"] == ["AND"]
    assert block["condition_lines"] == ["ABC is active", "column torque is greater than 5Nm"]


def test_extract_header_conditions_preserves_inline_child_logic_inside_condition_line():
    text = """when any of below conditions are met:
one of vehicle speed is invalid
s_vehicle_speed1 is invalid or s_vehicle_speed2 is invalid"""

    block = extract_condition_blocks(text)[0]

    assert block["logic_hint"] == "ANY"
    assert block["condition_lines"] == [
        "one of vehicle speed is invalid",
        "s_vehicle_speed1 is invalid or s_vehicle_speed2 is invalid",
    ]
    assert block["logic_markers"] == []


def test_extract_trigger_only_header_does_not_emit_colon_condition():
    text = """if:
conditionA
OR
ConditionB"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "if"
    assert block["logic_hint"] == "OR"
    assert block["condition_lines"] == ["conditionA", "ConditionB"]
    assert block["logic_markers"] == ["OR"]


def test_extract_single_processed_condition_uses_configured_temporal_trigger_prefixes():
    during_block = extract_condition_blocks("during ABC is active")[0]
    after_block = extract_condition_blocks("after DEF is inactive")[0]

    assert during_block["trigger"] == "during"
    assert during_block["condition_lines"] == ["ABC is active"]
    assert after_block["trigger"] == "after"
    assert after_block["condition_lines"] == ["DEF is inactive"]


def test_extract_configured_condition_header_prefix_is_not_condition_line():
    text = """under following conditions:
Condition1
AND
Condition2"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "under following conditions:"
    assert block["logic_hint"] == "AND"
    assert block["condition_lines"] == ["Condition1", "Condition2"]
    assert block["logic_markers"] == ["AND"]


def test_extract_condition_list_header_patterns_are_not_condition_lines():
    samples = [
        "if/when the following conditions are met:",
        "when the following condition is met:",
        "while the following conditions are satisfied:",
        "if the following condition is satisfied:",
        "when below conditions are met:",
        "if following condition is satisfied:",
        "when/if below conditions are fullfilled:",
        "when following conditions are fulfilled:",
        "when the below conditions are met:",
        "when the below conditions is met:",
        "when the below condition is satiafied:",
        "in case of error conditions are fulfilled:",
        "while blow condition is satisfied:",
    ]

    for header in samples:
        block = extract_condition_blocks(f"{header}\nCONDITIONA\nAND\nCONDITIONB")[0]

        assert block["trigger"] == header
        assert block["logic_hint"] == "AND"
        assert block["condition_lines"] == ["CONDITIONA", "CONDITIONB"]
        assert block["logic_markers"] == ["AND"]


def test_extract_condition_list_header_quantifier_sets_logic_hint():
    samples = [
        ("if any of error conditions are met:", "ANY"),
        ("when all error condition is fulfilled:", "ALL"),
        ("in case of any blow conditions are satisfied:", "ANY"),
        ("while all of the following conditions are met:", "ALL"),
    ]

    for header, expected_logic in samples:
        block = extract_condition_blocks(f"{header}\nCONDITIONA\nCONDITIONB")[0]

        assert block["trigger"] == header
        assert block["logic_hint"] == expected_logic
        assert block["condition_lines"] == ["CONDITIONA", "CONDITIONB"]


def test_extract_condition_headers_accept_period_terminator():
    samples = [
        ("when any of error conditions are met.", "ANY"),
        ("if the following conditions are satisfied.", "AND"),
        ("under following conditions.", "AND"),
    ]

    for header, expected_logic in samples:
        block = extract_condition_blocks(f"{header}\nCONDITIONA\nAND\nCONDITIONB")[0]

        assert block["trigger"] == header
        assert block["logic_hint"] == expected_logic
        assert block["condition_lines"] == ["CONDITIONA", "CONDITIONB"]
        assert block["logic_markers"] == ["AND"]


def test_extract_condition_list_header_one_of_sets_any_logic_hint():
    text = """if one of following conditions is fulfilled:
ConditionA
AND
ConditionB"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "if one of following conditions is fulfilled:"
    assert block["logic_hint"] == "ANY"
    assert block["condition_lines"] == ["ConditionA", "ConditionB"]
    assert block["logic_markers"] == ["AND"]


def test_extract_multiline_conditions_prefers_processed_parser_over_inline_comma_cutoff():
    text = """when A,
AND
B"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "when"
    assert block["logic_hint"] == "AND"
    assert block["condition_lines"] == ["A", "B"]
    assert block["logic_markers"] == ["AND"]


def test_extract_nested_below_condition_block_preserves_parent_and_child_logic():
    text = """when conditionA
AND conditionB
AND any of below conditions is met:
condition1
condition2"""

    block = extract_condition_blocks(text)[0]

    assert block["trigger"] == "when"
    assert block["logic_hint"] == "AND"
    assert block["condition_lines"] == ["conditionA", "conditionB"]
    assert block["logic_markers"] == ["AND", "AND"]
    assert block["nested_condition_blocks"] == [
        {
            "block_id": "cond_block_1_nested_1",
            "trigger": "any of below conditions is met:",
            "logic_hint": "ANY",
            "condition_text": "condition1\ncondition2",
            "condition_lines": ["condition1", "condition2"],
            "logic_markers": [],
            "skipped_lines": [],
        }
    ]


def test_extract_nested_condition_header_uses_configured_lists():
    text = """when conditionA
AND all of the below condition is fulfilled:
condition1
condition2"""

    block = extract_condition_blocks(text)[0]

    assert block["logic_markers"] == ["AND"]
    assert block["nested_condition_blocks"] == [
        {
            "block_id": "cond_block_1_nested_1",
            "trigger": "all of the below condition is fulfilled:",
            "logic_hint": "ALL",
            "condition_text": "condition1\ncondition2",
            "condition_lines": ["condition1", "condition2"],
            "logic_markers": [],
            "skipped_lines": [],
        }
    ]


def test_extract_nested_condition_header_allows_free_descriptor():
    text = """conditionA
AND any of error conditions are met:
condition1
condition2"""

    block = extract_condition_blocks(text)[0]

    assert block["nested_condition_blocks"][0]["trigger"] == "any of error conditions are met:"
    assert block["nested_condition_blocks"][0]["logic_hint"] == "ANY"
    assert block["nested_condition_blocks"][0]["condition_lines"] == ["condition1", "condition2"]


def test_extract_nested_condition_header_without_quantifier_defaults_to_parent_logic():
    text = """conditionA
AND below conditions are met.
condition1
condition2"""

    block = extract_condition_blocks(text)[0]

    assert block["nested_condition_blocks"][0]["trigger"] == "below conditions are met."
    assert block["nested_condition_blocks"][0]["logic_hint"] is None
    assert block["nested_condition_blocks"][0]["condition_lines"] == ["condition1", "condition2"]


def test_extract_bracketed_multiline_logic_group_as_nested_condition_block():
    text = """condition1
AND
(condition2
OR
condition3)"""

    block = extract_condition_blocks(text)[0]

    assert block["logic_hint"] == "AND"
    assert block["condition_lines"] == ["condition1"]
    assert block["logic_markers"] == ["AND"]
    assert block["nested_condition_blocks"] == [
        {
            "block_id": "cond_block_1_nested_1",
            "trigger": "bracketed_group",
            "logic_hint": "OR",
            "condition_text": "condition2\ncondition3",
            "condition_lines": ["condition2", "condition3"],
            "logic_markers": ["OR"],
            "skipped_lines": [],
            "source_wrapper": "()",
        }
    ]


def test_extract_square_and_curly_bracketed_multiline_logic_groups():
    square = extract_condition_blocks("condition1\nAND\n[condition2\nOR\ncondition3]")[0]
    curly = extract_condition_blocks("condition1\nAND\n{condition2\nAND\ncondition3}")[0]

    assert square["nested_condition_blocks"][0]["source_wrapper"] == "[]"
    assert square["nested_condition_blocks"][0]["logic_hint"] == "OR"
    assert curly["nested_condition_blocks"][0]["source_wrapper"] == "{}"
    assert curly["nested_condition_blocks"][0]["logic_hint"] == "AND"


def test_extract_does_not_treat_single_line_parentheses_as_nested_condition_block():
    block = extract_condition_blocks("when (condition1 AND condition2)")[0]

    assert "nested_condition_blocks" not in block
    assert block["condition_lines"] == ["(condition1 AND condition2)"]


def test_parse_condition_logic_outputs_nested_condition_group():
    block = extract_condition_blocks(
        """when conditionA
AND conditionB
AND any of below conditions is met:
condition1
condition2"""
    )[0]

    group = parse_condition_logic(block)

    assert group["logic"] == "AND"
    assert group["children"] == [
        {"type": "condition_line", "text": "conditionA"},
        {"type": "condition_line", "text": "conditionB"},
        {
            "type": "condition_group",
            "block_id": "cond_block_1_nested_1",
            "logic": "ANY",
            "trigger": "any of below conditions is met:",
            "children": [
                {"type": "condition_line", "text": "condition1"},
                {"type": "condition_line", "text": "condition2"},
            ],
            "need_review": False,
        },
    ]


def test_parse_conditions_parses_nested_condition_group_children():
    conditions = parse_conditions(
        """when DEM_PARENT_FAULT is Active
AND any of below conditions is met:
S_VEHICLE_SPEED > 10kph
S_COLUMN_TORQUE > 5Nm"""
    )

    group = by_type(conditions, "condition_group")[0]
    nested_group = by_type(group["children"], "condition_group")[0]

    assert nested_group["logic"] == "ANY"
    assert nested_group["children"][0]["type"] == "threshold_condition"
    assert nested_group["children"][0]["signal"] == "S_VEHICLE_SPEED"
    assert nested_group["children"][1]["type"] == "threshold_condition"
    assert nested_group["children"][1]["signal"] == "S_COLUMN_TORQUE"


def test_fusion_builder_parses_conditions_field_instead_of_raw_text():
    from src.fusion_builder import build_enhanced_requirement

    req = build_enhanced_requirement(
        {
            "requirement_id": "REQ_COND_FIELD",
            "raw_text": "EPS shall transition from Normal state to Degraded state.",
            "conditions": "If S_VEHICLE_SPEED is less than 10kph",
            "rule_entities": [],
            "ner_entities": [],
        }
    )

    threshold = by_type(req["parsed_conditions"], "threshold_condition")[0]
    assert threshold["signal"] == "S_VEHICLE_SPEED"
    assert threshold["operator"] == "<"
    assert threshold["value"] == 10
