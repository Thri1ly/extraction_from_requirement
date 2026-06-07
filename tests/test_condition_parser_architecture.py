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
            "condition_text": "S_VEHICLE_SPEED > 10kph\nAND\nDEM_COLUMN_TORQUE_IMPLAUSIBLE is Active",
            "condition_lines": ["S_VEHICLE_SPEED > 10kph", "DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"],
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

    assert block["logic_hint"] is None
    assert block["condition_lines"] == ["S_VEHICLE_SPEED > 10kph", "OR", "DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active"]


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
