import json
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser.condition_semantic_chunker import chunk_condition_sentence
from src.schemas import JsonDict


INPUT_JSONL = "data/condition_lines.jsonl"
OUTPUT_MD = "reports/condition_chunk_debug_report.md"
MAX_RECORDS = None

CONDITION_TEXT_KEYS = ["condition", "condition_line", "text", "sentence", "raw_text"]
RECORD_ID_KEYS = ["condition_id", "id", "requirement_id"]


def load_jsonl(path: str | Path) -> list[JsonDict]:
    """Load JSON objects from a JSONL file."""

    rows: list[JsonDict] = []
    with Path(path).open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            item = json.loads(stripped)
            if not isinstance(item, dict):
                raise ValueError(f"Line {line_number} is not a JSON object.")
            rows.append(item)
    return rows


def get_condition_text(record: JsonDict) -> str | None:
    """Return condition text using the configured field priority."""

    for key in CONDITION_TEXT_KEYS:
        value = record.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return None


def get_record_id(record: JsonDict, row_index: int) -> str:
    """Return a stable record id for report headings."""

    for key in RECORD_ID_KEYS:
        value = record.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return f"ROW_{row_index:04d}"


def get_normalized_entities(record: JsonDict) -> list[JsonDict]:
    """Return normalized entities if the record already has them."""

    entities = record.get("normalized_entities")
    if not isinstance(entities, list):
        return []
    return [dict(entity) for entity in entities if isinstance(entity, dict)]


def markdown_escape(text: object) -> str:
    """Escape compact text for a Markdown table cell."""

    escaped = str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    escaped = " ".join(escaped.split())
    if len(escaped) > 200:
        return escaped[:200] + "..."
    return escaped


def summarize_chunk_types(results: Sequence[JsonDict]) -> dict[str, int]:
    """Count chunk types in successfully parsed records."""

    counter: Counter[str] = Counter()
    for result in results:
        if result.get("status") != "parsed":
            continue
        chunk_result = result.get("chunk_result", {})
        if not isinstance(chunk_result, dict):
            continue
        for chunk in chunk_result.get("chunks", []):
            if isinstance(chunk, dict):
                counter[str(chunk.get("chunk_type", "UNKNOWN"))] += 1
    return dict(sorted(counter.items()))


def render_record_section(record_result: JsonDict) -> str:
    """Render one record result as Markdown."""

    row_index = int(record_result.get("row_index", 0))
    record_id = str(record_result.get("record_id", f"ROW_{row_index:04d}"))
    status = str(record_result.get("status", "unknown"))
    lines = [f"### {row_index}. {record_id}\n\n"]

    if status == "skipped":
        lines.append("Status: SKIPPED\n\n")
        lines.append("Reason:\n\n")
        lines.append("```text\n")
        lines.append(str(record_result.get("error", "missing condition text")) + "\n")
        lines.append("```\n\n")
        return "".join(lines)

    if status == "error":
        lines.append("Status: ERROR\n\n")
        lines.append("Error:\n\n")
        lines.append("```text\n")
        lines.append(str(record_result.get("error", "")) + "\n")
        lines.append("```\n\n")
        return "".join(lines)

    condition_text = str(record_result.get("condition_text", ""))
    chunk_result = record_result.get("chunk_result", {})
    chunks = chunk_result.get("chunks", []) if isinstance(chunk_result, dict) else []

    lines.append("Original Condition:\n\n")
    lines.append("```text\n")
    lines.append(condition_text + "\n")
    lines.append("```\n\n")
    lines.append("Chunks:\n\n")
    lines.append("| # | chunk_type | source | span | confidence | need_review | text |\n")
    lines.append("| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |\n")
    for index, chunk in enumerate(chunks, start=1):
        span = chunk.get("span", [])
        confidence = chunk.get("confidence", "")
        need_review = str(bool(chunk.get("need_review", False))).lower()
        lines.append(
            f"| {index} | {markdown_escape(chunk.get('chunk_type', ''))} | "
            f"{markdown_escape(chunk.get('source', ''))} | {markdown_escape(span)} | "
            f"{markdown_escape(confidence)} | {need_review} | {markdown_escape(chunk.get('text', ''))} |\n"
        )

    lines.append("\nEntities per Chunk:\n\n")
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id", "UNKNOWN_CHUNK"))
        lines.append(f"#### {chunk_id}\n\n")
        lines.append("```json\n")
        lines.append(json.dumps(chunk.get("entities", []), ensure_ascii=False, indent=2) + "\n")
        lines.append("```\n\n")

    lines.append("Raw Chunk Result:\n\n")
    lines.append("```json\n")
    lines.append(json.dumps(chunk_result, ensure_ascii=False, indent=2) + "\n")
    lines.append("```\n\n")
    return "".join(lines)


def write_markdown_report(results: Sequence[JsonDict], output_path: str | Path) -> None:
    """Write a Markdown report for chunking results."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    parsed_records = [result for result in results if result.get("status") == "parsed"]
    skipped_records = [result for result in results if result.get("status") == "skipped"]
    total_chunks = sum(len(result.get("chunk_result", {}).get("chunks", [])) for result in parsed_records)
    chunk_types = summarize_chunk_types(results)

    lines = ["# Condition Semantic Chunking Debug Report\n\n"]
    lines.append("## Summary\n\n")
    lines.append(f"* Total records: {len(results)}\n")
    lines.append(f"* Parsed records: {len(parsed_records)}\n")
    lines.append(f"* Skipped records: {len(skipped_records)}\n")
    lines.append(f"* Total chunks: {total_chunks}\n")
    lines.append("* Chunk type distribution:\n")
    if chunk_types:
        for chunk_type, count in chunk_types.items():
            lines.append(f"  * {chunk_type}: {count}\n")
    else:
        lines.append("  * None: 0\n")
    lines.append("\n## Records\n\n")
    for result in results:
        lines.append(render_record_section(result))

    output.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    """Run the condition semantic chunking report script."""

    records = load_jsonl(INPUT_JSONL)
    if isinstance(MAX_RECORDS, int):
        records = records[:MAX_RECORDS]

    results: list[JsonDict] = []
    for row_index, record in enumerate(records, start=1):
        record_id = get_record_id(record, row_index)
        text = get_condition_text(record)
        if text is None:
            results.append(
                {
                    "row_index": row_index,
                    "record_id": record_id,
                    "status": "skipped",
                    "error": "missing condition text",
                }
            )
            continue

        try:
            normalized_entities = get_normalized_entities(record)
            chunk_result = chunk_condition_sentence(text, normalized_entities)
            results.append(
                {
                    "row_index": row_index,
                    "record_id": record_id,
                    "status": "parsed",
                    "condition_text": text,
                    "normalized_entities": normalized_entities,
                    "chunk_result": chunk_result,
                }
            )
        except Exception as exc:
            results.append(
                {
                    "row_index": row_index,
                    "record_id": record_id,
                    "status": "error",
                    "condition_text": text,
                    "error": str(exc),
                }
            )

    write_markdown_report(results, OUTPUT_MD)
    print(f"Wrote {len(results)} records to {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
