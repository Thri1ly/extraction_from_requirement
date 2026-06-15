import json

from src.parser.chunked_condition_parser import (
    classify_timing_relation,
    extract_duration_value,
    normalize_duration_operator,
    parse_atomic_chunk,
    parse_chunked_condition,
    parse_duration_constraint,
)


def test_parse_chunked_condition_merges_chunks_duration_and_equivalence_relation():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT"
    parsed = parse_chunked_condition(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert parsed["condition_type"] == "condition_group"
    assert parsed["raw_text"] == text
    assert parsed["logic"] == "AND"
    assert parsed["need_review"] is False
    assert parsed["debug_info"]["chunk_rules"] == [
        {"chunk_id": "CHUNK_1", "source": "pre_parenthesis", "chunk_type": "natural_language_condition"},
        {"chunk_id": "CHUNK_2", "source": "parenthesis", "chunk_type": "explicit_signal_definition"},
        {"chunk_id": "CHUNK_3", "source": "temporal_phrase", "chunk_type": "duration_constraint"},
    ]
    assert parsed["relations"] == [
        {
            "relation": "equivalent_to",
            "source_chunk": "CHUNK_1",
            "target_chunk": "CHUNK_2",
            "reason": "parenthesized_explicit_definition",
        }
    ]

    assert [chunk["chunk_type"] for chunk in parsed["chunks"]] == [
        "natural_language_condition",
        "explicit_signal_definition",
        "duration_constraint",
    ]
    assert [chunk["chunk_id"] for chunk in parsed["parsed_chunks"]] == ["CHUNK_1", "CHUNK_2", "CHUNK_3"]
    assert parsed["parsed_chunks"][0]["parse_result"]["type"] == "signal_state_condition"
    assert parsed["parsed_chunks"][0]["parse_result"]["signal"] == "S_VEHICLE_SPEED"
    assert parsed["parsed_chunks"][0]["parse_result"]["required_state"] == "INVALID"
    assert parsed["parsed_chunks"][1]["parse_result"]["type"] == "signal_state_condition"
    assert parsed["parsed_chunks"][1]["parse_result"]["signal"] == "S_VEHICLE_SPEED"
    assert parsed["parsed_chunks"][1]["parse_result"]["required_state"] == "INVALID"
    assert parsed["parsed_chunks"][2]["parse_result"]["condition_type"] == "duration_constraint"
    assert parsed["parsed_chunks"][2]["parse_result"]["duration"] == "P_LIMIT"
    assert parsed["parsed_chunks"][2]["parse_result"]["unit"] is None
    assert parsed["parsed_chunks"][2]["parse_result"]["operator"] == "for_duration"
    assert parsed["parsed_chunks"][2]["parse_result"]["timing_relation"] == "sustain_for"
    assert parsed["parsed_chunks"][2]["parse_result"]["confidence"] == 0.9
    json.dumps(parsed)


def test_parse_chunked_condition_returns_new_condition_group_contract_for_atomic_condition():
    parsed = parse_chunked_condition(
        "S_VEHICLE_SPEED is valid",
        normalized_entities=[
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert parsed["condition_type"] == "condition_group"
    assert parsed["raw_text"] == "S_VEHICLE_SPEED is valid"
    assert parsed["logic"] == "AND"
    assert parsed["relations"] == []
    assert parsed["need_review"] is False
    assert len(parsed["parsed_chunks"]) >= 1
    assert parsed["parsed_chunks"][0]["parse_result"].get("condition_type") not in {
        "natural_language_event",
        "unparsed_chunk",
    }
    assert parsed["parsed_chunks"] == [
        {
            "chunk_id": "CHUNK_1",
            "chunk_type": "atomic_condition",
            "text": "S_VEHICLE_SPEED is valid",
            "parse_result": {
                "type": "signal_state_condition",
                "mention": "S_VEHICLE_SPEED == valid",
                "signal": "S_VEHICLE_SPEED",
                "operator": "==",
                "required_state": "valid",
                "need_review": False,
                "parser": "syntactic",
            },
        }
    ]
    json.dumps(parsed)


def test_parse_chunked_condition_uses_natural_language_event_fallback():
    parsed = parse_chunked_condition("driver turns the wheel")

    assert parsed["need_review"] is True
    assert parsed["parsed_chunks"] == [
        {
            "chunk_id": "CHUNK_1",
            "chunk_type": "natural_language_event",
            "text": "driver turns the wheel",
            "parse_result": {
                "condition_type": "natural_language_event",
                "raw_text": "driver turns the wheel",
                "need_review": True,
                "confidence": 0.3,
            },
        }
    ]


def test_parse_duration_constraint_supports_parameter_minimum_and_within_forms():
    assert parse_duration_constraint("for a duration of P_LIMIT") | {"duration_type": "duration"} == {
        "condition_type": "duration_constraint",
        "text": "for a duration of P_LIMIT",
        "duration": "P_LIMIT",
        "value": None,
        "unit": None,
        "operator": "for_duration",
        "timing_relation": "sustain_for",
        "confidence": 0.9,
        "need_review": False,
        "duration_type": "duration",
    }
    parsed_at_least = parse_duration_constraint("for at least 100ms")
    assert parsed_at_least["duration"] == 100
    assert parsed_at_least["unit"] == "ms"
    assert parsed_at_least["operator"] == ">="
    assert parsed_at_least["timing_relation"] == "sustain_for"
    parsed_within = parse_duration_constraint("within 100ms")
    assert parsed_within["duration"] == 100
    assert parsed_within["unit"] == "ms"
    assert parsed_within["operator"] == "<="
    assert parsed_within["timing_relation"] == "within_time"


def test_parse_duration_constraint_supports_general_timing_forms():
    examples = [
        ("duration time is equal to or greater than P_TIME", ">=", "duration_compare", "P_TIME", None, None),
        ("the duration is 200ms", "=", "duration_compare", 200, 200, "ms"),
        ("for duration greater than P_TIME", ">", "sustain_for", "P_TIME", None, None),
        ("for more than P_TIME", ">", "sustain_for", "P_TIME", None, None),
        ("within the debounce time P_TIME", "<=", "within_time", "P_TIME", None, None),
        ("in the debounce time P_TIME", "<=", "within_time", "P_TIME", None, None),
        ("for P_TIME", "for_duration", "sustain_for", "P_TIME", None, None),
        ("exceeding the debounce time P_TIME", ">", "exceed_time", "P_TIME", None, None),
    ]

    for text, operator, timing_relation, duration, value, unit in examples:
        parsed = parse_duration_constraint(text)

        assert parsed["condition_type"] == "duration_constraint"
        assert parsed["duration"] == duration
        assert parsed["operator"] == operator
        assert parsed["timing_relation"] == timing_relation
        assert parsed["value"] == value
        assert parsed["unit"] == unit
        assert parsed["need_review"] is False


def test_duration_helpers_normalize_operator_relation_and_value():
    assert normalize_duration_operator("duration time is equal to or greater than P_TIME") == ">="
    assert normalize_duration_operator("for more than P_TIME") == ">"
    assert classify_timing_relation("within the debounce time P_TIME") == "within_time"
    assert extract_duration_value("the duration is 200ms") == {"duration": 200, "value": 200, "unit": "ms"}


def test_parse_chunked_condition_parses_duration_inside_parenthesized_condition():
    parsed = parse_chunked_condition("fault occurs (signal1 < signal2 for a xxx period of xxx P_TIME)")

    duration_chunks = [
        chunk for chunk in parsed["parsed_chunks"] if chunk["parse_result"].get("condition_type") == "duration_constraint"
    ]

    assert duration_chunks
    assert duration_chunks[0]["parse_result"]["duration"] == "P_TIME"


def test_parse_chunked_condition_parses_phase_timing_constraint():
    parsed = parse_chunked_condition("both steer angle request are timeout before activation")

    timing_chunks = [
        chunk for chunk in parsed["parsed_chunks"] if chunk["chunk_type"] == "phase_timing_constraint"
    ]

    assert timing_chunks
    assert timing_chunks[0]["parse_result"] == {
        "condition_type": "phase_timing_constraint",
        "timing_relation": "before_phase",
        "phase": "activation",
        "confidence": 0.9,
    }


def test_parse_chunked_condition_parses_temporal_context_constraint():
    parsed = parse_chunked_condition("an ASP check failure is detected during a {journey}")

    context_chunks = [
        chunk for chunk in parsed["parsed_chunks"] if chunk["chunk_type"] == "temporal_context_constraint"
    ]

    assert context_chunks
    assert context_chunks[0]["parse_result"] == {
        "condition_type": "temporal_context_constraint",
        "timing_relation": "during_context",
        "context": "journey",
        "relative_time": None,
        "confidence": 0.9,
    }


def test_parse_chunked_condition_parses_previous_temporal_context_constraint():
    parsed = parse_chunked_condition("ASP check failure has been detected during the previous {journey}")

    context_chunks = [
        chunk for chunk in parsed["parsed_chunks"] if chunk["chunk_type"] == "temporal_context_constraint"
    ]

    assert context_chunks[0]["parse_result"]["context"] == "journey"
    assert context_chunks[0]["parse_result"]["relative_time"] == "previous"


def test_parse_chunked_condition_does_not_parse_from_source_as_temporal_context():
    parsed = parse_chunked_condition("steer angle signal requests to exit from CAN1")

    assert len(parsed["chunks"]) == 1
    assert all(chunk["chunk_type"] != "temporal_context_constraint" for chunk in parsed["parsed_chunks"])


def test_parse_chunked_condition_parses_quantified_parenthesized_member_group():
    parsed = parse_chunked_condition(
        "the signal on both lane (S_LANE1 is equal to VALID) and (S_LANE2 is equal to VALID) are valid",
        normalized_entities=[
            {"mention": "S_LANE1", "type": "SIGNAL", "canonical_name": "S_LANE1"},
            {"mention": "S_LANE2", "type": "SIGNAL", "canonical_name": "S_LANE2"},
            {"mention": "VALID", "type": "STATE", "canonical_name": "VALID"},
        ],
    )

    group_chunks = [
        chunk
        for chunk in parsed["parsed_chunks"]
        if chunk["parse_result"].get("condition_type") == "quantified_member_expression_group"
    ]

    assert group_chunks
    parse_result = group_chunks[0]["parse_result"]
    assert parse_result["group_mention"] == "the signal on both lane"
    assert parse_result["quantifier"] == "ALL"
    assert parse_result["logic"] == "AND"
    assert parse_result["shared_state"] == "valid"
    assert len(parse_result["member_conditions"]) == 2
    assert all(condition.get("type") == "signal_state_condition" for condition in parse_result["member_conditions"])


def test_parse_chunked_condition_preserves_failed_quantified_member_parse():
    parsed = parse_chunked_condition(
        "the signal on both lane (S_LANE1 unsupported relation P_LIMIT) and (S_LANE2 is equal to VALID) are valid"
    )

    parse_result = parsed["parsed_chunks"][0]["parse_result"]

    assert parse_result["condition_type"] == "quantified_member_expression_group"
    assert parse_result["need_review"] is True
    assert parse_result["member_conditions"][0]["raw_text"] == "S_LANE1 unsupported relation P_LIMIT"
    assert parse_result["member_conditions"][0]["need_review"] is True
    assert len(parse_result["member_conditions"]) == 2


def test_parse_chunked_condition_parses_parenthesized_condition_group():
    parsed = parse_chunked_condition(
        "(S_VEHICLE_SPEED >= P_SPEED_LIMIT AND S_SPEED_QF = VALID)",
        normalized_entities=[
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "P_SPEED_LIMIT", "type": "PARAMETER", "canonical_name": "P_SPEED_LIMIT"},
            {"mention": "S_SPEED_QF", "type": "SIGNAL", "canonical_name": "S_SPEED_QF"},
            {"mention": "VALID", "type": "STATE", "canonical_name": "VALID"},
        ],
    )

    parse_result = parsed["parsed_chunks"][0]["parse_result"]

    assert parse_result["condition_type"] == "parenthesized_condition_group"
    assert parse_result["logic"] == "AND"
    assert len(parse_result["member_conditions"]) == 2
    assert parse_result["member_conditions"][0]["parse_result"]["type"] == "parameter_threshold_condition"
    assert parse_result["member_conditions"][1]["parse_result"]["type"] == "signal_state_condition"


def test_parenthesized_condition_group_parses_sub_chunks():
    parsed = parse_chunked_condition(
        "(S_VEHICLE_SPEED >= P_SPEED_LIMIT AND S_SPEED_QF = VALID)",
        normalized_entities=[
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "P_SPEED_LIMIT", "type": "PARAMETER", "canonical_name": "P_SPEED_LIMIT"},
            {"mention": "S_SPEED_QF", "type": "SIGNAL", "canonical_name": "S_SPEED_QF"},
            {"mention": "VALID", "type": "STATE", "canonical_name": "VALID"},
        ],
    )

    parse_result = parsed["parsed_chunks"][0]["parse_result"]

    assert parse_result["condition_type"] == "parenthesized_condition_group"
    assert len(parse_result["member_conditions"]) == 2
    assert parse_result["member_conditions"][0]["raw_text"] == "S_VEHICLE_SPEED >= P_SPEED_LIMIT"
    assert parse_result["member_conditions"][1]["raw_text"] == "S_SPEED_QF = VALID"
    assert parse_result["member_conditions"][0]["raw_text"] != parsed["chunks"][0]["text"]


def test_parse_atomic_chunk_adapter_supports_syntactic_and_legacy_names():
    entities = [
        {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
        {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
    ]

    assert parse_atomic_chunk("S_STATUS is valid", entities, atomic_parser="syntactic")["type"] == "signal_state_condition"
    assert parse_atomic_chunk("S_STATUS is valid", entities, atomic_parser="legacy")["type"] == "signal_state_condition"
