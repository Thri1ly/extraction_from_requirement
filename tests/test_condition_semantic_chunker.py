import json

from src.parser.condition_semantic_chunker import assign_entities_to_chunks, chunk_condition_sentence


def test_chunk_condition_sentence_splits_parenthesized_definition_and_duration():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert result["raw_text"] == text
    assert result["debug_info"]["chunk_count"] == 3
    assert result["debug_info"]["chunk_rules"] == [
        {"chunk_id": "CHUNK_1", "source": "pre_parenthesis", "chunk_type": "natural_language_condition"},
        {"chunk_id": "CHUNK_2", "source": "parenthesis", "chunk_type": "explicit_signal_definition"},
        {"chunk_id": "CHUNK_3", "source": "temporal_phrase", "chunk_type": "duration_constraint"},
    ]
    assert result["chunks"] == [
        {
            "chunk_id": "CHUNK_1",
            "chunk_type": "natural_language_condition",
            "text": "vehicle speed is invalid",
            "span": [0, 24],
            "entities": [
                {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
                {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            ],
            "source": "pre_parenthesis",
            "confidence": 0.8,
            "need_review": False,
        },
        {
            "chunk_id": "CHUNK_2",
            "chunk_type": "explicit_signal_definition",
            "text": "S_VEHICLE_SPEED is equal to INVALID",
            "span": [26, 61],
            "entities": [
                {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
                {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            ],
            "source": "parenthesis",
            "confidence": 0.9,
            "need_review": False,
        },
        {
            "chunk_id": "CHUNK_3",
            "chunk_type": "duration_constraint",
            "text": "for a duration of P_LIMIT",
            "span": [63, 88],
            "entities": [
                {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
            ],
            "source": "temporal_phrase",
            "confidence": 0.9,
            "need_review": False,
        },
    ]
    json.dumps(result)


def test_chunk_condition_sentence_ignores_trailing_period_after_duration():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT."
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert len(result["chunks"]) == 3
    assert "." not in [chunk["text"] for chunk in result["chunks"]]
    assert result["chunks"][2]["text"] == "for a duration of P_LIMIT"


def test_chunk_condition_sentence_keeps_parenthesized_signal_alias_in_one_chunk():
    text = "vehicle speed(S_VEHICLE_SPEED) is invalid"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "invalid", "type": "STATE", "canonical_name": "INVALID"},
        ],
    )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == text
    assert result["chunks"][0]["chunk_type"] in {"atomic_condition", "natural_language_condition"}
    assert result["chunks"][0]["source"] == "full_sentence"
    assert all(chunk["chunk_type"] != "explicit_signal_definition" for chunk in result["chunks"])


def test_chunk_condition_sentence_still_splits_parenthesized_explicit_condition():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID)"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
        ],
    )

    assert len(result["chunks"]) == 2
    assert result["chunks"][0]["chunk_type"] == "natural_language_condition"
    assert result["chunks"][1]["chunk_type"] == "explicit_signal_definition"


def test_chunk_condition_sentence_assigns_entities_to_each_matching_chunk():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "INVALID", "type": "STATE", "canonical_name": "INVALID"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    chunk_entities = [[entity["mention"] for entity in chunk["entities"]] for chunk in result["chunks"]]

    assert chunk_entities == [
        ["vehicle speed", "INVALID"],
        ["S_VEHICLE_SPEED", "INVALID"],
        ["P_LIMIT"],
    ]


def test_assign_entities_to_chunks_uses_absolute_spans_and_preserves_dictionary_misses():
    chunks = [
        {"chunk_id": "CHUNK_1", "text": "vehicle speed is invalid", "span": [0, 24], "entities": []},
        {"chunk_id": "CHUNK_2", "text": "S_VEHICLE_SPEED is equal to INVALID", "span": [26, 61], "entities": []},
    ]
    assigned = assign_entities_to_chunks(
        chunks,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "start": 0, "end": 13, "dictionary_match": False},
            {"mention": "INVALID", "type": "STATE", "start": 54, "end": 61, "dictionary_match": False},
            {"mention": "P_LIMIT", "type": "PARAMETER", "start": 81, "end": 88, "dictionary_match": False},
        ],
    )

    assert assigned[0]["entities"] == [
        {"mention": "vehicle speed", "type": "SIGNAL", "start": 0, "end": 13, "dictionary_match": False},
    ]
    assert assigned[1]["entities"] == [
        {"mention": "INVALID", "type": "STATE", "start": 54, "end": 61, "dictionary_match": False},
    ]


def test_chunk_condition_sentence_returns_atomic_condition_when_no_special_structure():
    text = "S_VEHICLE_SPEED is valid"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "S_VEHICLE_SPEED", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "valid", "type": "STATE", "canonical_name": "valid"},
        ],
    )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["chunk_id"] == "CHUNK_1"
    assert result["chunks"][0]["chunk_type"] == "atomic_condition"
    assert result["chunks"][0]["text"] == text
    assert result["chunks"][0]["span"] == [0, len(text)]
    assert result["chunks"][0]["source"] == "main_clause"
    json.dumps(result)


def test_chunk_condition_sentence_does_not_split_range_and():
    text = "vehicle speed is in range of 50kph and 100kph"
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "vehicle speed", "type": "SIGNAL", "canonical_name": "S_VEHICLE_SPEED"},
            {"mention": "50kph", "type": "VALUE", "canonical_name": "50kph"},
            {"mention": "100kph", "type": "VALUE", "canonical_name": "100kph"},
        ],
    )

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == text
    assert result["chunks"][0]["chunk_type"] in {"atomic_condition", "natural_language_condition"}


def test_chunk_condition_sentence_preserves_plain_rack_event_text():
    text = "the rack is moving to the right end stop"
    result = chunk_condition_sentence(text, normalized_entities=[])

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["chunk_type"] in {"natural_language_event", "natural_language_condition"}
    assert result["chunks"][0]["text"] == text
    assert result["chunks"] == [
        {
            "chunk_id": "CHUNK_1",
            "chunk_type": result["chunks"][0]["chunk_type"],
            "text": text,
            "span": [0, len(text)],
            "entities": [],
            "source": "main_clause",
            "confidence": result["chunks"][0]["confidence"],
            "need_review": result["chunks"][0]["need_review"],
        }
    ]
    json.dumps(result)
