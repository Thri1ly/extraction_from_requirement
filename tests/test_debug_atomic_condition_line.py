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
