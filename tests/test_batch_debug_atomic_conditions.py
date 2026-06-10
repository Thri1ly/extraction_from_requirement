import json

from scripts.batch_debug_atomic_conditions import main, run_batch_debug_atomic_conditions


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def write_dictionary(path):
    payload = {
        "entities": [
            {"canonical_name": "S_VEHICLE_SPEED", "type": "SIGNAL", "aliases": ["vehicle speed"], "members": []},
            {"canonical_name": "3kph", "type": "VALUE", "aliases": ["3kph"], "members": []},
            {"canonical_name": "S_COLUMN_TORQUE", "type": "SIGNAL", "aliases": ["Column Torque"], "members": []},
            {"canonical_name": "S_COLUMN_VELOCITY", "type": "SIGNAL", "aliases": ["Column Velocity"], "members": []},
            {"canonical_name": "==", "type": "OPERATOR", "aliases": ["equal to"], "members": []},
            {"canonical_name": "0", "type": "VALUE", "aliases": ["zero"], "members": []},
        ]
    }
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_run_batch_debug_atomic_conditions_writes_jsonl_and_markdown_summary(tmp_path):
    source = tmp_path / "condition_lines.jsonl"
    dictionary = tmp_path / "dictionary.json"
    output_jsonl = tmp_path / "debug_results.jsonl"
    output_md = tmp_path / "debug_report.md"
    write_dictionary(dictionary)
    write_jsonl(
        source,
        [
            {
                "requirement_id": "REQ_PASS",
                "condition line": "vehicle speed is greater than 3kph",
                "entities": [
                    {"mention": "vehicle speed", "type": "SIGNAL"},
                    {"mention": "3kph", "type": "VALUE"},
                ],
            },
            {
                "requirement_id": "REQ_REVIEW",
                "condition_line": "no input torque and no column movement condition ({Column Torque} and {Column Velocity} are equal to zero)",
                "entities": [
                    {"mention": "input torque", "type": "UNKNOWN"},
                    {"mention": "column movement condition", "type": "UNKNOWN"},
                    {"mention": "Column Torque", "type": "SIGNAL"},
                    {"mention": "Column Velocity", "type": "SIGNAL"},
                    {"mention": "equal to", "type": "OPERATOR"},
                    {"mention": "zero", "type": "VALUE"},
                ],
            },
            {
                "requirement_id": "REQ_FAIL",
                "condition_line": "unsupported condition",
                "entities": [],
            },
        ],
    )

    rows = run_batch_debug_atomic_conditions(source, dictionary, output_jsonl, output_md)

    assert len(rows) == 3
    assert read_jsonl(output_jsonl)[0]["parsed"]["type"] == "threshold_condition"
    report = output_md.read_text(encoding="utf-8")
    assert "# Batch Atomic Condition Debug Report" in report
    assert "- Total condition lines: 3" in report
    assert "- Parsed without review: 1" in report
    assert "- Parsed with review: 1" in report
    assert "- Unparsed: 1" in report
    assert "- Average overall confidence: 0.63" in report
    assert "REQ_REVIEW" in report
    assert "state_definition_condition" in report


def test_batch_debug_atomic_conditions_cli(tmp_path):
    source = tmp_path / "condition_lines.jsonl"
    dictionary = tmp_path / "dictionary.json"
    output_jsonl = tmp_path / "debug_results.jsonl"
    output_md = tmp_path / "debug_report.md"
    write_dictionary(dictionary)
    write_jsonl(
        source,
        [
            {
                "condition_line": "vehicle speed is greater than 3kph",
                "entities": [
                    {"mention": "vehicle speed", "type": "SIGNAL"},
                    {"mention": "3kph", "type": "VALUE"},
                ],
            }
        ],
    )

    exit_code = main(
        [
            "--input",
            str(source),
            "--dictionary",
            str(dictionary),
            "--output-jsonl",
            str(output_jsonl),
            "--output-md",
            str(output_md),
        ]
    )

    assert exit_code == 0
    assert output_jsonl.exists()
    assert output_md.exists()
