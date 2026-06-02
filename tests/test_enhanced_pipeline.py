from src.fusion_builder import build_enhanced_requirement


SAMPLES = {
    "REQ_101": "When vehicle is moving (S_VEHICLE_SPEED is greater than 3kph) and both vehicle speed signals are valid, EPS shall calculate the torque demand and limit it to 2Nm.",
    "REQ_102": "If vehicle speed is in range of 50kph and 100kph (50kph <= S_VEHICLE_SPEED <= 100kph), EPS shall reduce the assist torque with increasing Driver Torque.",
    "REQ_103": "When |{Column Torque}| is greater than 5Nm and one of the vehicle speed signals is valid, EPS shall raise the fault DEM_COLUMN_TORQUE_IMPLAUSIBLE and set the MIL on.",
    "REQ_104": "If DEM_COLUMN_TORQUE_IMPLAUSIBLE is Active and S_VEHICLE_SPEED is less than 10kph, EPS shall transition from Normal state to Degraded state.",
    "REQ_105": "When both vehicle speed signals are valid again and DEM_VEHICLE_SPEED_INVALID is Inactive, EPS shall return from Degraded state to Normal state and clear the MIL.",
}


def enhanced(req_id):
    return build_enhanced_requirement(
        {
            "requirement_id": req_id,
            "function": "EPS",
            "requirement_type": "system",
            "component": "EPS",
            "raw_text": SAMPLES[req_id],
            "rule_entities": [],
            "ner_entities": [],
        }
    )


def by_type(items, item_type):
    return [item for item in items if item["type"] == item_type]


def test_req_101_state_validity_calculate_limit_and_it_coreference():
    req = enhanced("REQ_101")

    state = by_type(req["parsed_conditions"], "state_definition_condition")[0]
    assert state["state_name"] == "VehicleMoving"
    assert state["signal"] == "S_VEHICLE_SPEED"
    assert state["operator"] == ">"
    assert state["value"] == 3
    assert state["unit"] == "kph"

    validity = by_type(req["parsed_conditions"], "redundant_signal_validity")[0]
    assert validity["signal_group"] == "VehicleSpeedGroup"
    assert validity["quantifier"] == "ALL"

    calculate = by_type(req["parsed_actions"], "calculate_signal")[0]
    assert calculate["target"] == "S_TORQUE_DEMAND"

    limit = by_type(req["parsed_actions"], "limit_value")[0]
    assert limit["target"] == "S_TORQUE_DEMAND"
    assert limit["value"] == 2
    assert limit["unit"] == "Nm"

    resolution = req["coreference"]["resolutions"][0]
    assert resolution["pronoun"] == "it"
    assert resolution["resolved_to"] == "torque demand"
    assert resolution["canonical_target"] == "S_TORQUE_DEMAND"
    assert resolution["need_review"] is False


def test_req_102_range_adjust_and_trend_dependency():
    req = enhanced("REQ_102")

    condition = by_type(req["parsed_conditions"], "range_condition")[0]
    assert condition["signal"] == "S_VEHICLE_SPEED"
    assert condition["lower_operator"] == ">="
    assert condition["lower_value"] == 50
    assert condition["upper_operator"] == "<="
    assert condition["upper_value"] == 100
    assert condition["unit"] == "kph"

    action = by_type(req["parsed_actions"], "adjust_signal")[0]
    assert action["target"] == "S_ASSIST_TORQUE"
    assert action["target_trend"] == "decrease"

    dependency = by_type(req["parsed_conditions"], "trend_dependency")[0]
    assert dependency["source_signal"] == "S_DRIVER_TORQUE"
    assert dependency["source_trend"] == "increase"
    assert dependency["correlation"] == "negative"


def test_req_103_abs_threshold_validity_fault_and_mil_on():
    req = enhanced("REQ_103")

    threshold = by_type(req["parsed_conditions"], "threshold_condition")[0]
    assert threshold["signal"] == "S_COLUMN_TORQUE"
    assert threshold["transform"] == "ABS"
    assert threshold["operator"] == ">"
    assert threshold["value"] == 5
    assert threshold["unit"] == "Nm"

    validity = by_type(req["parsed_conditions"], "redundant_signal_validity")[0]
    assert validity["quantifier"] == "ANY_ONE"

    fault = by_type(req["parsed_actions"], "set_fault")[0]
    assert fault["target"] == "DEM_COLUMN_TORQUE_IMPLAUSIBLE"
    assert fault["expected_state"] == "Active"

    indicator = by_type(req["parsed_actions"], "set_indicator")[0]
    assert indicator["target"] == "MIL"
    assert indicator["expected_state"] == "On"


def test_req_104_fault_speed_threshold_and_state_transition():
    req = enhanced("REQ_104")

    fault_condition = by_type(req["parsed_conditions"], "fault_state_condition")[0]
    assert fault_condition["fault_signal"] == "DEM_COLUMN_TORQUE_IMPLAUSIBLE"
    assert fault_condition["required_state"] == "Active"

    threshold = by_type(req["parsed_conditions"], "threshold_condition")[0]
    assert threshold["signal"] == "S_VEHICLE_SPEED"
    assert threshold["operator"] == "<"
    assert threshold["value"] == 10
    assert threshold["unit"] == "kph"

    transition = by_type(req["parsed_actions"], "state_transition")[0]
    assert transition["from_state"] == "Normal"
    assert transition["to_state"] == "Degraded"


def test_req_105_validity_inactive_fault_return_and_clear_mil():
    req = enhanced("REQ_105")

    validity = by_type(req["parsed_conditions"], "redundant_signal_validity")[0]
    assert validity["quantifier"] == "ALL"

    fault_condition = by_type(req["parsed_conditions"], "fault_state_condition")[0]
    assert fault_condition["fault_signal"] == "DEM_VEHICLE_SPEED_INVALID"
    assert fault_condition["required_state"] == "Inactive"

    transition = by_type(req["parsed_actions"], "state_transition")[0]
    assert transition["from_state"] == "Degraded"
    assert transition["to_state"] == "Normal"

    indicator = by_type(req["parsed_actions"], "clear_indicator")[0]
    assert indicator["target"] == "MIL"
    assert indicator["expected_state"] == "Off"


def test_embedding_text_contains_stable_sections():
    req = enhanced("REQ_101")

    assert "Requirement ID: REQ_101" in req["embedding_text"]
    assert "Conditions:" in req["embedding_text"]
    assert "Actions:" in req["embedding_text"]
    assert "Coreference:" in req["embedding_text"]
    assert "Original Requirement:" in req["embedding_text"]
