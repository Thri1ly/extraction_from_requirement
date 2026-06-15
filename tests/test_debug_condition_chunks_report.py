import json

from scripts.debug_condition_chunks_report import (
    get_condition_text,
    get_normalized_entities,
    get_record_id,
    markdown_escape,
    render_record_section,
    summarize_chunk_types,
    write_markdown_report,
)


def test_record_field_helpers_follow_expected_priority():
    assert get_condition_text({"condition": "A", "condition_line": "B"}) == "A"
    assert get_condition_text({"condition_line": "B"}) == "B"
    assert get_condition_text({"text": "C"}) == "C"
    assert get_condition_text({"sentence": "D"}) == "D"
    assert get_condition_text({"raw_text": "E"}) == "E"
    assert get_condition_text({"unknown": "x"}) is None

    assert get_record_id({"condition_id": "C001"}, 1) == "C001"
    assert get_record_id({"id": "ID2"}, 2) == "ID2"
    assert get_record_id({"requirement_id": "REQ3"}, 3) == "REQ3"
    assert get_record_id({}, 4) == "ROW_0004"

    assert get_normalized_entities({"normalized_entities": [{"mention": "S"}]}) == [{"mention": "S"}]
    assert get_normalized_entities({"normalized_entities": "bad"}) == []


def test_markdown_escape_flattens_pipes_and_truncates_long_text():
    escaped = markdown_escape("A|B\nC")
    assert escaped == "A\\|B C"

    long_text = "x" * 250
    assert markdown_escape(long_text) == ("x" * 200) + "..."


def test_summarize_chunk_types_counts_only_parsed_results():
    results = [
        {"status": "parsed", "chunk_result": {"chunks": [{"chunk_type": "atomic_condition"}]}},
        {"status": "parsed", "chunk_result": {"chunks": [{"chunk_type": "duration_constraint"}]}},
        {"status": "skipped"},
    ]

    assert summarize_chunk_types(results) == {
        "atomic_condition": 1,
        "duration_constraint": 1,
    }


def test_render_record_section_includes_chunks_entities_raw_result_and_errors():
    record_result = {
        "row_index": 1,
        "record_id": "C001",
        "status": "parsed",
        "condition_text": "S_A is valid",
        "chunk_result": {
            "raw_text": "S_A is valid",
            "chunks": [
                {
                    "chunk_id": "CHUNK_1",
                    "chunk_type": "atomic_condition",
                    "source": "main_clause",
                    "span": [0, 12],
                    "confidence": 0.8,
                    "need_review": False,
                    "text": "S_A is valid",
                    "entities": [{"mention": "S_A"}],
                }
            ],
            "debug_info": {"chunk_count": 1},
        },
    }

    section = render_record_section(record_result)

    assert "### 1. C001" in section
    assert "Original Condition:" in section
    assert "| 1 | atomic_condition | main_clause | [0, 12] | 0.8 | false | S_A is valid |" in section
    assert "#### CHUNK_1" in section
    assert json.dumps([{"mention": "S_A"}], ensure_ascii=False, indent=2) in section
    assert "Raw Chunk Result:" in section

    error_section = render_record_section(
        {
            "row_index": 2,
            "record_id": "C002",
            "status": "error",
            "error": "boom",
        }
    )
    assert "Status: ERROR" in error_section
    assert "boom" in error_section


def test_write_markdown_report_creates_summary_and_output_file(tmp_path):
    output = tmp_path / "report.md"
    results = [
        {
            "row_index": 1,
            "record_id": "C001",
            "status": "parsed",
            "condition_text": "S_A is valid",
            "chunk_result": {
                "raw_text": "S_A is valid",
                "chunks": [
                    {
                        "chunk_id": "CHUNK_1",
                        "chunk_type": "atomic_condition",
                        "source": "main_clause",
                        "span": [0, 12],
                        "confidence": 0.8,
                        "need_review": False,
                        "text": "S_A is valid",
                        "entities": [],
                    }
                ],
                "debug_info": {"chunk_count": 1},
            },
        },
        {"row_index": 2, "record_id": "ROW_0002", "status": "skipped", "error": "missing condition text"},
    ]

    write_markdown_report(results, output)

    report = output.read_text(encoding="utf-8")
    assert "# Condition Semantic Chunking Debug Report" in report
    assert "* Total records: 2" in report
    assert "* Parsed records: 1" in report
    assert "* Skipped records: 1" in report
    assert "* Total chunks: 1" in report
    assert "  * atomic_condition: 1" in report
