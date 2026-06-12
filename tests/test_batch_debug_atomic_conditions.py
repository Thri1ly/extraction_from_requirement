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
            {"canonical_name": "S_EPS_SYSTEM_STATE", "type": "SIGNAL", "aliases": ["EPS system state"], "members": []},
            {"canonical_name": "LIMP_HOME", "type": "STATE", "aliases": ["LIMP HOME"], "members": []},
            {"canonical_name": "LIMP_ASIDE", "type": "STATE", "aliases": ["LIMP ASIDE"], "members": []},
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
    assert "- Average overall confidence: 0.50" in report
    assert "REQ_REVIEW" in report
    assert "state_definition_condition" in report

    parsed_without_review_md = tmp_path / "debug_report.parsed_without_review.md"
    parsed_with_review_md = tmp_path / "debug_report.parsed_with_review.md"
    unparsed_md = tmp_path / "debug_report.unparsed.md"

    assert parsed_without_review_md.exists()
    assert parsed_with_review_md.exists()
    assert unparsed_md.exists()

    pass_report = parsed_without_review_md.read_text(encoding="utf-8")
    review_report = parsed_with_review_md.read_text(encoding="utf-8")
    fail_report = unparsed_md.read_text(encoding="utf-8")

    assert "# Parsed Without Review" in pass_report
    assert "REQ_PASS" in pass_report
    assert "Input Entities" not in pass_report
    assert "Normalized Entities" not in pass_report
    assert "Syntax Analysis" not in pass_report
    assert "vehicle speed" in pass_report
    assert "S_VEHICLE_SPEED" in pass_report

    assert "# Parsed With Review" in review_report
    assert "REQ_REVIEW" in review_report
    assert "Input Entities" not in review_report
    assert "Normalized Entities" not in review_report
    assert "Syntax Analysis" not in review_report
    assert "S_COLUMN_TORQUE" in review_report

    assert "# Unparsed" in fail_report
    assert "REQ_FAIL" in fail_report
    assert "Input Entities" not in fail_report
    assert "Normalized Entities" not in fail_report
    assert "Syntax Analysis" not in fail_report
    assert "unsupported condition" in fail_report


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
    assert (tmp_path / "debug_report.parsed_without_review.md").exists()


def test_run_batch_debug_atomic_conditions_can_use_syntactic_parser(tmp_path):
    source = tmp_path / "condition_lines.jsonl"
    dictionary = tmp_path / "dictionary.json"
    output_jsonl = tmp_path / "debug_results.jsonl"
    output_md = tmp_path / "debug_report.md"
    write_dictionary(dictionary)
    write_jsonl(
        source,
        [
            {
                "requirement_id": "REQ_SYNTACTIC",
                "condition_line": "EPS system state shall be LIMP HOME or LIMP ASIDE",
                "entities": [
                    {"mention": "EPS system state", "type": "SIGNAL"},
                    {"mention": "LIMP HOME", "type": "STATE"},
                    {"mention": "LIMP ASIDE", "type": "STATE"},
                ],
            }
        ],
    )

    rows = run_batch_debug_atomic_conditions(
        source,
        dictionary,
        output_jsonl,
        output_md,
        atomic_parser="syntactic",
    )

    assert rows[0]["atomic_parser"] == "syntactic"
    assert rows[0]["syntax_analysis"]["placeholder_text"] == "SIGNAL_1 shall be STATE_1 or STATE_2"
    assert rows[0]["parsed"]["type"] == "condition_group"
    assert rows[0]["parsed"]["logic"] == "OR"

    parsed_without_review = tmp_path / "debug_report.parsed_without_review.md"
    report = parsed_without_review.read_text(encoding="utf-8")
    assert "**Syntax Analysis**" not in report
    assert "**Placeholder Text**" in report
    assert "SIGNAL_1 shall be STATE_1 or STATE_2" in report
    assert "placeholder_map" not in report
