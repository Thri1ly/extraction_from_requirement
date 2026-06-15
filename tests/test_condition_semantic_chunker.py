import json

from src.parser.condition_text_preprocessor import clean_condition_text
from src.parser.condition_semantic_chunker import (
    assign_entities_to_chunks,
    chunk_condition_sentence,
    find_balanced_square_bracket_span,
    split_bracket_group_sub_chunks,
    split_square_bracket_condition_group,
)


def test_clean_condition_text_removes_unmatched_outer_parentheses_and_brackets():
    examples = [
        (
            "(S_A is valid AND S_B is invalid",
            "S_A is valid AND S_B is invalid",
            "remove_unmatched_opening_parenthesis",
            "(",
        ),
        (
            "S_A is valid AND S_B is invalid)",
            "S_A is valid AND S_B is invalid",
            "remove_unmatched_closing_parenthesis",
            ")",
        ),
        ("[S_A is valid", "S_A is valid", "remove_unmatched_opening_square_bracket", "["),
        ("S_A is valid]", "S_A is valid", "remove_unmatched_closing_square_bracket", "]"),
        ("{S_A is valid", "S_A is valid", "remove_unmatched_opening_curly_brace", "{"),
        ("S_A is valid}", "S_A is valid", "remove_unmatched_closing_curly_brace", "}"),
    ]

    for text, cleaned_text, action, char in examples:
        result = clean_condition_text(text)

        assert result["cleaned_text"] == cleaned_text
        assert result["changed"] is True
        assert result["need_review"] is True
        assert result["cleaning_actions"][0]["action"] == action
        assert result["cleaning_actions"][0]["char"] == char


def test_clean_condition_text_preserves_balanced_or_non_outer_brackets():
    examples = [
        "vehicle speed(S_VEHICLE_SPEED) is invalid",
        "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID)",
        "[S_A is valid AND S_B is invalid]",
        "{S_VEHICLE_SPEED} is valid",
        "|{S_COLUMN_TORQUE}| is greater than 5Nm",
        "((S_A is valid))",
    ]

    for text in examples:
        result = clean_condition_text(text)

        assert result["cleaned_text"] == text
        assert result["changed"] is False
        assert result["need_review"] is False
        assert result["cleaning_actions"] == []


def test_clean_condition_text_repeats_outer_noise_cleanup():
    assert clean_condition_text("((S_A is valid")["cleaned_text"] == "S_A is valid"
    assert clean_condition_text("S_A is valid))")["cleaned_text"] == "S_A is valid"


def test_chunk_condition_sentence_includes_text_preprocessing_debug_info():
    result = chunk_condition_sentence("(S_A is valid AND S_B is invalid", normalized_entities=[])

    preprocessing = result["debug_info"]["text_preprocessing"]
    assert preprocessing["original_text"] == "(S_A is valid AND S_B is invalid"
    assert preprocessing["cleaned_text"] == "S_A is valid AND S_B is invalid"
    assert preprocessing["changed"] is True
    assert result["chunks"][0]["text"] == "S_A is valid"


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


def test_chunk_condition_sentence_treats_square_brackets_as_condition_group_container():
    text = (
        "angle request is out of range in normal operation"
        "[(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND "
        "(S_SPC_ANGLE_REQUEST is greater than 'static limit')] "
        "for a duration greater than P_LIMIT"
    )
    result = chunk_condition_sentence(
        text,
        normalized_entities=[
            {"mention": "angle request", "type": "SIGNAL", "canonical_name": "S_SPC_ANGLE_REQUEST"},
            {"mention": "S_SPC_ANGLE_MODE_REQUEST", "type": "SIGNAL", "canonical_name": "S_SPC_ANGLE_MODE_REQUEST"},
            {"mention": "normal", "type": "STATE", "canonical_name": "normal"},
            {"mention": "S_SPC_ANGLE_REQUEST", "type": "SIGNAL", "canonical_name": "S_SPC_ANGLE_REQUEST"},
            {"mention": "static limit", "type": "PARAMETER", "canonical_name": "static limit"},
            {"mention": "P_LIMIT", "type": "PARAMETER", "canonical_name": "P_LIMIT"},
        ],
    )

    assert [chunk["chunk_type"] for chunk in result["chunks"]] == [
        "natural_language_condition",
        "bracketed_condition_group",
        "duration_constraint",
    ]
    assert [chunk["text"] for chunk in result["chunks"]] == [
        "angle request is out of range in normal operation",
        "(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit')",
        "for a duration greater than P_LIMIT",
    ]
    assert "[" not in result["chunks"][1]["text"]
    assert "]" not in result["chunks"][1]["text"]


def test_chunk_condition_sentence_splits_general_duration_phrases_after_and():
    examples = [
        ("signal is invalid and duration time is equal to or greater than P_TIME", "duration time is equal to or greater than P_TIME"),
        ("signal is invalid and the duration is 200ms", "the duration is 200ms"),
        ("signal is invalid for duration greater than P_TIME", "for duration greater than P_TIME"),
        ("signal is invalid for more than P_TIME", "for more than P_TIME"),
        ("signal is invalid within the debounce time P_TIME", "within the debounce time P_TIME"),
        ("signal is invalid in the debounce time P_TIME", "in the debounce time P_TIME"),
        ("signal is invalid for P_TIME", "for P_TIME"),
        ("signal is invalid exceeding the debounce time P_TIME", "exceeding the debounce time P_TIME"),
    ]

    for text, expected_duration_text in examples:
        result = chunk_condition_sentence(text, normalized_entities=[])

        assert result["chunks"][-1]["chunk_type"] == "duration_constraint"
        assert result["chunks"][-1]["source"] == "temporal_phrase"
        assert result["chunks"][-1]["text"] == expected_duration_text
        assert not result["chunks"][-1]["text"].lower().startswith("and ")


def test_chunk_condition_sentence_splits_duration_inside_parenthesized_condition():
    text = "fault occurs (signal1 < signal2 for a xxx period of xxx P_TIME)"

    result = chunk_condition_sentence(text, normalized_entities=[])

    assert [chunk["chunk_type"] for chunk in result["chunks"]] == [
        "natural_language_event",
        "explicit_signal_definition",
        "duration_constraint",
    ]
    assert result["chunks"][2]["text"] == "for a xxx period of xxx P_TIME"


def test_chunk_condition_sentence_splits_top_level_and_conditions():
    result = chunk_condition_sentence("S_A is valid and S_B is invalid", normalized_entities=[])

    assert [chunk["text"] for chunk in result["chunks"]] == ["S_A is valid", "S_B is invalid"]
    assert result["chunks"][0]["logic_after"] == "AND"
    assert "logic_after" not in result["chunks"][1]


def test_chunk_condition_sentence_splits_top_level_and_without_breaking_alias_parentheses():
    text = "vehicle speed(S_VEHICLE_SPEED) is invalid and EPS state(S_EPS_STATE) is Degraded"

    result = chunk_condition_sentence(text, normalized_entities=[])

    assert [chunk["text"] for chunk in result["chunks"]] == [
        "vehicle speed(S_VEHICLE_SPEED) is invalid",
        "EPS state(S_EPS_STATE) is Degraded",
    ]
    assert result["chunks"][0]["logic_after"] == "AND"


def test_chunk_condition_sentence_splits_top_level_parenthesized_clause_before_parenthesis_rules():
    text = "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) and EPS is Degraded"

    result = chunk_condition_sentence(text, normalized_entities=[])

    assert [chunk["text"] for chunk in result["chunks"]] == [
        "vehicle speed is invalid",
        "S_VEHICLE_SPEED is equal to INVALID",
        "EPS is Degraded",
    ]
    assert result["chunks"][1]["logic_after"] == "AND"


def test_chunk_condition_sentence_splits_top_level_or_conditions():
    result = chunk_condition_sentence("S_A is valid or S_B is valid", normalized_entities=[])

    assert [chunk["text"] for chunk in result["chunks"]] == ["S_A is valid", "S_B is valid"]
    assert result["chunks"][0]["logic_after"] == "OR"


def test_chunk_condition_sentence_splits_top_level_but_as_contrast():
    result = chunk_condition_sentence("S_A is valid but S_B is invalid", normalized_entities=[])

    assert [chunk["text"] for chunk in result["chunks"]] == ["S_A is valid", "S_B is invalid"]
    assert result["chunks"][0]["logic_after"] == "BUT"
    assert result["chunks"][0]["semantic_relation"] == "contrast"


def test_chunk_condition_sentence_does_not_split_protected_top_level_connectors():
    examples = [
        'S_A is equal to "Valid and Available"',
        "one of S_A and S_B is valid",
        "at least one of S_A and S_B is valid",
        "both S_A and S_B are valid",
        "vehicle speed is in range of 50kph and 100kph",
        "vehicle speed is between 50kph and 100kph",
    ]

    for text in examples:
        result = chunk_condition_sentence(text, normalized_entities=[])

        assert len(result["chunks"]) == 1
        assert result["chunks"][0]["text"] == text


def test_chunk_condition_sentence_splits_phase_timing_constraint():
    result = chunk_condition_sentence("both steer angle request are timeout before activation", normalized_entities=[])

    assert [chunk["chunk_type"] for chunk in result["chunks"]] == [
        "natural_language_condition",
        "phase_timing_constraint",
    ]
    assert result["chunks"][1]["text"] == "before activation"
    assert result["chunks"][1]["source"] == "temporal_phrase"
    assert result["chunks"][1]["timing_relation"] == "before_phase"
    assert result["chunks"][1]["phase"] == "activation"


def test_chunk_condition_sentence_splits_temporal_context_constraint():
    result = chunk_condition_sentence("an ASP check failure is detected during a {journey}", normalized_entities=[])

    assert [chunk["chunk_type"] for chunk in result["chunks"]] == [
        "natural_language_condition",
        "temporal_context_constraint",
    ]
    assert result["chunks"][1]["text"] == "during a {journey}"
    assert result["chunks"][1]["timing_relation"] == "during_context"
    assert result["chunks"][1]["context"] == "journey"


def test_chunk_condition_sentence_splits_previous_temporal_context_constraint():
    result = chunk_condition_sentence("ASP check failure has been detected during the previous {journey}", normalized_entities=[])

    assert result["chunks"][1]["chunk_type"] == "temporal_context_constraint"
    assert result["chunks"][1]["text"] == "during the previous {journey}"
    assert result["chunks"][1]["context"] == "journey"
    assert result["chunks"][1]["relative_time"] == "previous"


def test_chunk_condition_sentence_does_not_split_source_from_phrase():
    text = "steer angle signal requests to exit from CAN1"
    result = chunk_condition_sentence(text, normalized_entities=[])

    assert len(result["chunks"]) == 1
    assert result["chunks"][0]["text"] == text
    assert result["chunks"][0]["chunk_type"] != "temporal_context_constraint"


def test_chunk_condition_sentence_protects_quantified_parenthesized_member_group_with_comparison_members():
    text = "the signal on both lane (S_LANE1 > P_LIMIT) and (S_LANE2 > P_LIMIT) are valid"
    result = chunk_condition_sentence(text, normalized_entities=[])

    assert len(result["chunks"]) == 1
    chunk = result["chunks"][0]
    assert chunk["chunk_type"] == "quantified_parenthesized_member_group"
    assert chunk["text"] == text
    assert chunk["group_mention"] == "the signal on both lane"
    assert chunk["quantifier_hint"] == "ALL"
    assert chunk["logic_hint"] == "AND"
    assert chunk["shared_state"] == "valid"
    assert chunk["source"] == "quantified_parenthesized_member_group"
    assert [member["text"] for member in chunk["member_chunks"]] == ["S_LANE1 > P_LIMIT", "S_LANE2 > P_LIMIT"]
    assert all(member["chunk_type"] == "atomic_condition" for member in chunk["member_chunks"])


def test_chunk_condition_sentence_protects_quantified_parenthesized_member_group_with_textual_members():
    text = "the signal on both lane (S_LANE1 is equal to VALID) and (S_LANE2 is equal to VALID) are valid"
    result = chunk_condition_sentence(text, normalized_entities=[])

    chunk = result["chunks"][0]
    assert len(result["chunks"]) == 1
    assert chunk["chunk_type"] == "quantified_parenthesized_member_group"
    assert chunk["quantifier_hint"] == "ALL"
    assert chunk["logic_hint"] == "AND"
    assert chunk["shared_state"] == "valid"
    assert [member["text"] for member in chunk["member_chunks"]] == [
        "S_LANE1 is equal to VALID",
        "S_LANE2 is equal to VALID",
    ]


def test_chunk_condition_sentence_protects_any_one_quantified_parenthesized_member_group():
    text = "one of the signals (S_LANE1 > P_LIMIT) or (S_LANE2 > P_LIMIT) is valid"
    result = chunk_condition_sentence(text, normalized_entities=[])

    chunk = result["chunks"][0]
    assert len(result["chunks"]) == 1
    assert chunk["chunk_type"] == "quantified_parenthesized_member_group"
    assert chunk["quantifier_hint"] == "ANY_ONE"
    assert chunk["logic_hint"] == "OR"
    assert chunk["shared_state"] == "valid"
    assert len(chunk["member_chunks"]) == 2


def test_chunk_condition_sentence_protects_available_quantified_parenthesized_member_group():
    text = "both signal requests (S_REQ1 is equal to AVAILABLE) and (S_REQ2 is equal to AVAILABLE) are available"
    result = chunk_condition_sentence(text, normalized_entities=[])

    chunk = result["chunks"][0]
    assert len(result["chunks"]) == 1
    assert chunk["chunk_type"] == "quantified_parenthesized_member_group"
    assert chunk["quantifier_hint"] == "ALL"
    assert chunk["logic_hint"] == "AND"
    assert chunk["shared_state"] == "available"
    assert len(chunk["member_chunks"]) == 2


def test_find_balanced_square_bracket_span_returns_outer_span_or_none():
    text = "prefix[(S_A is equal to normal) AND (S_B is greater than 'static limit')] suffix"

    assert find_balanced_square_bracket_span(text) == [6, 73]
    assert find_balanced_square_bracket_span("prefix [missing close") is None
    assert find_balanced_square_bracket_span("no brackets") is None


def test_split_square_bracket_condition_group_returns_top_level_parts_without_brackets():
    text = (
        "angle request is out of range in normal operation"
        "[(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND "
        "(S_SPC_ANGLE_REQUEST is greater than 'static limit')] "
        "for a duration greater than P_LIMIT"
    )

    parts = split_square_bracket_condition_group(text)

    assert parts == {
        "prefix": "angle request is out of range in normal operation",
        "bracket_content": "(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit')",
        "suffix": "for a duration greater than P_LIMIT",
        "span": [49, 153],
    }


def test_split_bracket_group_sub_chunks_preserves_quoted_values_and_logic():
    content = "(S_A is equal to normal) AND (S_B is greater than 'static limit')"

    assert split_bracket_group_sub_chunks(content) == {
        "logic": "AND",
        "sub_chunks": [
            {"text": "S_A is equal to normal", "span": [1, 23]},
            {"text": "S_B is greater than 'static limit'", "span": [30, 64]},
        ],
    }


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
