from src.condition_block_extractor import extract_condition_blocks
from src.condition_logic_parser import parse_condition_logic
from src.condition_parser import parse_conditions


def by_type(items, condition_type):
    return [item for item in items if item["type"] == condition_type]


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
