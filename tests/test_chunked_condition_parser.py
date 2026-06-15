import json

from src.parser.chunked_condition_parser import (
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
    assert parsed["parsed_chunks"][2]["parse_result"] == {
        "condition_type": "duration_constraint",
        "duration": "P_LIMIT",
        "unit": None,
        "operator": "for_duration",
        "confidence": 0.9,
    }
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
    assert parse_duration_constraint("for a duration of P_LIMIT") == {
        "condition_type": "duration_constraint",
        "duration": "P_LIMIT",
        "unit": None,
        "operator": "for_duration",
        "confidence": 0.9,
    }
    assert parse_duration_constraint("for at least 100ms") == {
        "condition_type": "duration_constraint",
        "duration": 100,
        "unit": "ms",
        "operator": ">=",
        "confidence": 0.9,
    }
    assert parse_duration_constraint("within 100ms") == {
        "condition_type": "duration_constraint",
        "duration": 100,
        "unit": "ms",
        "operator": "<=",
        "confidence": 0.9,
    }


def test_parse_atomic_chunk_adapter_supports_syntactic_and_legacy_names():
    entities = [
        {"mention": "S_STATUS", "type": "SIGNAL", "canonical_name": "S_STATUS"},
        {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
    ]

    assert parse_atomic_chunk("S_STATUS is valid", entities, atomic_parser="syntactic")["type"] == "signal_state_condition"
    assert parse_atomic_chunk("S_STATUS is valid", entities, atomic_parser="legacy")["type"] == "signal_state_condition"
