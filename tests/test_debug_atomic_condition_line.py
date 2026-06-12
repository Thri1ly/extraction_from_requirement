import json

from scripts.debug_atomic_condition_line import debug_atomic_condition_line, load_entities, main


def write_dictionary(path):
    payload = {
        "entities": [
            {
                "canonical_name": "S_VEHICLE_SPEED",
                "type": "SIGNAL",
                "aliases": ["S_VEHICLE_SPEED", "vehicle speed"],
                "members": [],
            },
            {
                "canonical_name": "3kph",
                "type": "VALUE",
                "aliases": ["3kph"],
                "members": [],
            },
            {
                "canonical_name": "S_COLUMN_TORQUE",
                "type": "SIGNAL",
                "aliases": ["Column Torque"],
                "members": [],
            },
            {
                "canonical_name": "S_COLUMN_VELOCITY",
                "type": "SIGNAL",
                "aliases": ["Column Velocity"],
                "members": [],
            },
            {
                "canonical_name": "==",
                "type": "OPERATOR",
                "aliases": ["equal to"],
                "members": [],
            },
            {
                "canonical_name": "0",
                "type": "VALUE",
                "aliases": ["zero"],
                "members": [],
            },
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_debug_atomic_condition_line_normalizes_supplied_entities_and_parses(tmp_path):
    dictionary = tmp_path / "dictionary.json"
    write_dictionary(dictionary)
    entities = [
        {"mention": "vehicle speed", "type": "SIGNAL"},
        {"mention": "3kph", "type": "VALUE"},
    ]

    result = debug_atomic_condition_line(
        "vehicle speed is greater than 3kph",
        entities,
        dictionary,
        requirement_id="DEBUG_001",
    )

    assert result["requirement_id"] == "DEBUG_001"
    assert result["condition_line"] == "vehicle speed is greater than 3kph"
    assert result["normalized_entities"][0]["canonical_name"] == "S_VEHICLE_SPEED"
    assert result["normalized_entities"][1]["type"] == "VALUE"
    assert result["parsed"]["type"] == "threshold_condition"
    assert result["parsed"]["signal"] == "S_VEHICLE_SPEED"
    assert result["parsed"]["operator"] == ">"
    assert result["parsed"]["value"] == 3
    assert result["parsed"]["unit"] == "kph"


def test_load_entities_accepts_json_array_and_entities_object(tmp_path):
    entities = [{"mention": "vehicle speed", "type": "SIGNAL"}]
    entities_file = tmp_path / "entities.json"
    entities_file.write_text(json.dumps({"entities": entities}), encoding="utf-8")

    assert load_entities(json.dumps(entities), None) == entities
    assert load_entities(None, entities_file) == entities


def test_debug_atomic_condition_line_cli_writes_json_outputs(tmp_path):
    dictionary = tmp_path / "dictionary.json"
    output_json = tmp_path / "debug.json"
    output_jsonl = tmp_path / "debug.jsonl"
    write_dictionary(dictionary)

    exit_code = main(
        [
            "--condition-line",
            "vehicle speed is greater than 3kph",
            "--entities-json",
            '[{"mention":"vehicle speed","type":"SIGNAL"},{"mention":"3kph","type":"VALUE"}]',
            "--dictionary",
            str(dictionary),
            "--requirement-id",
            "DEBUG_002",
            "--output-json",
            str(output_json),
            "--output-jsonl",
            str(output_jsonl),
        ]
    )

    assert exit_code == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["requirement_id"] == "DEBUG_002"
    assert json.loads(output_jsonl.read_text(encoding="utf-8"))["parsed"]["operator"] == ">"


def test_debug_atomic_condition_line_outputs_confidence_for_unclear_named_definition(tmp_path):
    dictionary = tmp_path / "dictionary.json"
    write_dictionary(dictionary)
    entities = [
        {"mention": "input torque", "type": "UNKNOWN"},
        {"mention": "column movement condition", "type": "UNKNOWN"},
        {"mention": "Column Torque", "type": "SIGNAL"},
        {"mention": "Column Velocity", "type": "SIGNAL"},
        {"mention": "equal to", "type": "OPERATOR"},
        {"mention": "zero", "type": "VALUE"},
    ]

    result = debug_atomic_condition_line(
        "no input torque and no column movement condition ({Column Torque} and {Column Velocity} are equal to zero)",
        entities,
        dictionary,
        requirement_id="DEBUG_CONFIDENCE",
    )

    parsed = result["parsed"]
    assert parsed["type"] == "state_definition_condition"
    assert parsed["state_source"] == "inferred_from_text"
    assert parsed["definition"]["type"] == "condition_group"
    assert parsed["definition"]["children"][0]["signal"] == "S_COLUMN_TORQUE"
    assert parsed["definition"]["children"][1]["signal"] == "S_COLUMN_VELOCITY"
    assert parsed["confidence"] == {
        "overall": 0.78,
        "structure": 0.95,
        "state_name": 0.45,
        "definition": 0.95,
    }
    assert result["parse_confidence"] == {
        "overall": 0.4,
        "parser": 0.78,
        "normalization": 0.4,
    }
    assert parsed["need_review"] is True
    assert parsed["review_reason"] == "state name inferred from unclear natural-language description"


def test_debug_atomic_condition_line_keeps_dictionary_misses_and_lowers_confidence(tmp_path):
    dictionary = tmp_path / "dictionary.json"
    dictionary.write_text(json.dumps({"entities": []}, ensure_ascii=False), encoding="utf-8")

    result = debug_atomic_condition_line(
        "S_UNKNOWN_STATUS is valid",
        [
            {"mention": "S_UNKNOWN_STATUS", "type": "SIGNAL"},
            {"mention": "valid", "type": "STATE"},
        ],
        dictionary,
        requirement_id="DEBUG_UNKNOWN",
        atomic_parser="syntactic",
    )

    by_mention = {entity["mention"]: entity for entity in result["normalized_entities"]}
    assert by_mention["S_UNKNOWN_STATUS"]["dictionary_match"] is False
    assert by_mention["valid"]["dictionary_match"] is False
    assert result["parsed"]["type"] == "signal_state_condition"
    assert result["parsed"]["signal"] == "S_UNKNOWN_STATUS"
    assert result["parse_confidence"] == {
        "overall": 0.4,
        "parser": 0.9,
        "normalization": 0.4,
    }
