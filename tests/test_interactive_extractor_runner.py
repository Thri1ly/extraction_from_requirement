import json

from src.interactive_extractor_runner import (
    count_existing_records,
    interactive_loop,
    run_single_extraction,
)


def rule_extractor(text):
    if "vehicle speed" in text.lower():
        return [{"mention": "vehicle speed", "type": "signal"}]
    return []


def ner_extractor(text):
    if "MIL" in text:
        return [{"mention": "MIL", "type": "indicator"}]
    return []


def test_run_single_extraction_appends_record_without_overwriting(tmp_path):
    output_path = tmp_path / "records.jsonl"
    output_path.write_text('{"requirement_id":"REQ_INTERACTIVE_000001","raw_text":"old"}\n', encoding="utf-8")

    record = run_single_extraction(
        "EPS shall set MIL on when vehicle speed is valid.",
        rule_extractor=rule_extractor,
        ner_extractor=ner_extractor,
        output_path=output_path,
        requirement_id="REQ_INTERACTIVE_000002",
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 2
    assert rows[0]["raw_text"] == "old"
    assert rows[1] == record
    assert rows[1]["rule_entities"] == [{"mention": "vehicle speed", "type": "SIGNAL"}]
    assert rows[1]["ner_entities"] == [{"mention": "MIL", "type": "INDICATOR"}]


def test_count_existing_records_ignores_blank_lines(tmp_path):
    output_path = tmp_path / "records.jsonl"
    output_path.write_text('{"raw_text":"one"}\n\n{"raw_text":"two"}\n', encoding="utf-8")

    assert count_existing_records(output_path) == 2


def test_interactive_loop_appends_until_exit_command(tmp_path):
    output_path = tmp_path / "records.jsonl"
    answers = iter(["EPS shall set MIL on.", "Vehicle speed shall be valid.", ":q"])
    printed = []

    interactive_loop(
        rule_extractor=rule_extractor,
        ner_extractor=ner_extractor,
        output_path=output_path,
        input_func=lambda _: next(answers),
        print_func=printed.append,
    )

    rows = [json.loads(line) for line in output_path.read_text(encoding="utf-8").splitlines()]
    assert [row["requirement_id"] for row in rows] == ["REQ_INTERACTIVE_000001", "REQ_INTERACTIVE_000002"]
    assert rows[0]["ner_entities"] == [{"mention": "MIL", "type": "INDICATOR"}]
    assert rows[1]["rule_entities"] == [{"mention": "vehicle speed", "type": "SIGNAL"}]
    assert any("Saved to" in line for line in printed)
