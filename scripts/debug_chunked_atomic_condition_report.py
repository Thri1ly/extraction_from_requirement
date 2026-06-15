import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.parser.condition_semantic_chunker import chunk_condition_sentence
from src.schemas import JsonDict


INPUT_JSONL = "data/sample_chunked_atomic_conditions.jsonl"
OUTPUT_MD = "reports/chunked_atomic_condition_debug_report.md"
MAX_RECORDS = None
ATOMIC_PARSER = "syntactic"
DICTIONARY_PATH = "data/sample_entity_mapping.jsonl"

CONDITION_TEXT_KEYS = ["condition", "condition_line", "text", "sentence", "raw_text"]
RECORD_ID_KEYS = ["condition_id", "id", "requirement_id"]
ATOMIC_CHUNK_TYPES = {
    "atomic_condition",
    "natural_language_condition",
    "explicit_signal_definition",
}
SPECIAL_CHUNK_TYPES = {
    "duration_constraint",
    "phase_timing_constraint",
    "temporal_context_constraint",
    "bracketed_condition_group",
    "parenthesized_condition_group",
    "quantified_parenthesized_member_group",
}
RAW_CHUNK_TYPES = {"natural_language_event", "unparsed_chunk"}


def load_jsonl(path: str | Path) -> list[JsonDict]:
    """Load JSON objects from a JSONL file."""

    input_path = Path(path)
    if not input_path.exists():
        return []

    records: list[JsonDict] = []
    with input_path.open("r", encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            record = json.loads(stripped)
            if not isinstance(record, dict):
                raise ValueError(f"Line {line_number} is not a JSON object.")
            records.append(record)
    return records


def _strip_outer_entity_wrapper(value: str) -> str:
    """Remove one simple outer bracket wrapper used around entity mentions."""

    stripped = value.strip()
    if len(stripped) >= 2 and (stripped[0], stripped[-1]) in {("{", "}"), ("[", "]"), ("(", ")")}:
        return stripped[1:-1].strip()
    return stripped


def _dictionary_key(value: object) -> str:
    """Build the light lookup key used after exact and case-insensitive lookup."""

    text = _strip_outer_entity_wrapper(str(value))
    return re.sub(r"[\s_]+", "", text.lower())


def _add_dictionary_alias(index: JsonDict, alias: object, entry: JsonDict) -> None:
    """Add one alias to all supported dictionary indexes."""

    alias_text = str(alias).strip()
    if not alias_text:
        return
    index.setdefault("exact", {})[alias_text] = entry
    index.setdefault("casefold", {})[alias_text.lower()] = entry
    index.setdefault("compact", {})[_dictionary_key(alias_text)] = entry


def _add_dictionary_record(index: JsonDict, mention: object, record: JsonDict) -> None:
    """Normalize one dictionary record into lookup indexes."""

    mention_text = str(mention or record.get("mention") or record.get("name") or "").strip()
    canonical_name = str(record.get("canonical_name") or record.get("name") or mention_text).strip()
    entity_type = str(record.get("type") or record.get("entity_type") or "").strip()
    entry = dict(record)
    if mention_text:
        entry["mention"] = mention_text
    if canonical_name:
        entry["canonical_name"] = canonical_name
    if entity_type:
        entry["type"] = entity_type

    aliases = [mention_text, record.get("mention"), record.get("name"), canonical_name]
    aliases.extend(record.get("aliases", []) if isinstance(record.get("aliases"), list) else [])
    for alias in aliases:
        _add_dictionary_alias(index, alias, entry)


def _add_dictionary_object(index: JsonDict, item: object) -> None:
    """Accept all supported JSON dictionary item shapes."""

    if not isinstance(item, dict):
        return
    if any(key in item for key in ("mention", "name", "canonical_name", "entity_type", "type")):
        _add_dictionary_record(index, item.get("mention") or item.get("name"), item)
        return
    for mention, value in item.items():
        if isinstance(value, dict):
            _add_dictionary_record(index, mention, value)


def load_entity_dictionary(path: str | None) -> dict:
    """Load a flexible JSON/JSONL entity dictionary into lookup indexes."""

    index: JsonDict = {"exact": {}, "casefold": {}, "compact": {}}
    if path is None:
        return index

    dictionary_path = Path(path)
    if not dictionary_path.exists():
        return index

    try:
        if dictionary_path.suffix.lower() == ".jsonl":
            with dictionary_path.open("r", encoding="utf-8-sig") as handle:
                for line in handle:
                    stripped = line.strip()
                    if not stripped:
                        continue
                    _add_dictionary_object(index, json.loads(stripped))
        else:
            data = json.loads(dictionary_path.read_text(encoding="utf-8-sig"))
            if isinstance(data, list):
                for item in data:
                    _add_dictionary_object(index, item)
            else:
                _add_dictionary_object(index, data)
    except Exception:
        return {"exact": {}, "casefold": {}, "compact": {}}
    return index


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


def extract_entities_for_condition(text: str, record: dict | None = None) -> list[dict]:
    """
    Placeholder entity extraction hook.

    This function receives one condition sentence and optionally the original record.
    It should return a list of entity dictionaries.

    I will later replace this placeholder with my rule extractor + NER extractor.

    Expected entity format:
    {
        "mention": "...",
        "type": "SIGNAL|STATE|VALUE|PARAMETER|COMPONENT|FAULT|...",
        "canonical_name": "...",
        "start": 0,
        "end": 10,
        "confidence": 0.8
    }
    """

    return []


def _coerce_entity_list(entities: object) -> list[JsonDict]:
    """Return only JSON-object entities copied from an arbitrary value."""

    if not isinstance(entities, list):
        return []
    return [dict(entity) for entity in entities if isinstance(entity, dict)]


def _is_dictionary_loaded(entity_dictionary: dict | None) -> bool:
    """Return true when at least one dictionary lookup entry is available."""

    if not entity_dictionary:
        return False
    return any(bool(entity_dictionary.get(key)) for key in ("exact", "casefold", "compact"))


def _lookup_dictionary_entry(mention: str, entity_dictionary: dict) -> JsonDict | None:
    """Find a dictionary record by exact, case-insensitive, then compact key."""

    exact = entity_dictionary.get("exact", {})
    if mention in exact:
        return exact[mention]

    casefold = entity_dictionary.get("casefold", {})
    case_key = mention.lower()
    if case_key in casefold:
        return casefold[case_key]

    compact = entity_dictionary.get("compact", {})
    compact_key = _dictionary_key(mention)
    return compact.get(compact_key)


def normalize_entities_with_dictionary(entities: list[dict], entity_dictionary: dict) -> list[dict]:
    """Normalize extracted or raw entities against a lightweight mapping dictionary."""

    normalized_entities: list[dict] = []
    for entity in entities:
        item = dict(entity)
        if item.get("dictionary_match") is True or (item.get("canonical_name") and "normalization_confidence" in item):
            normalized_entities.append(item)
            continue

        mention = str(item.get("mention") or item.get("text") or item.get("name") or item.get("canonical_name") or "").strip()
        if mention:
            item.setdefault("mention", mention)
        match = _lookup_dictionary_entry(mention, entity_dictionary) if mention and _is_dictionary_loaded(entity_dictionary) else None
        if match:
            item["canonical_name"] = match.get("canonical_name") or mention
            if match.get("type"):
                item["type"] = match["type"]
            if match.get("members") is not None:
                item["members"] = list(match.get("members", []))
            item["dictionary_match"] = True
            item["normalization_confidence"] = 1.0
            item["need_review"] = False
        else:
            item["canonical_name"] = mention
            item["dictionary_match"] = False
            item["normalization_confidence"] = 0.4
            item["need_review"] = True
        normalized_entities.append(item)
    return normalized_entities


def get_normalized_entities(
    record: JsonDict,
    text: str | None = None,
    entity_dictionary: dict | None = None,
) -> JsonDict:
    """Return entities plus source and normalization metadata."""

    dictionary_loaded = _is_dictionary_loaded(entity_dictionary)

    entities = record.get("normalized_entities")
    if isinstance(entities, list):
        return {
            "entities": _coerce_entity_list(entities),
            "entities_source": "normalized_entities",
            "normalization_applied": False,
            "dictionary_loaded": dictionary_loaded,
        }

    entities = record.get("entities")
    if isinstance(entities, list):
        return {
            "entities": normalize_entities_with_dictionary(_coerce_entity_list(entities), entity_dictionary or {}),
            "entities_source": "entities",
            "normalization_applied": True,
            "dictionary_loaded": dictionary_loaded,
        }

    if text is None or not str(text).strip():
        return {
            "entities": [],
            "entities_source": "empty",
            "normalization_applied": False,
            "dictionary_loaded": dictionary_loaded,
        }

    extracted_entities = extract_entities_for_condition(str(text), record)
    return {
        "entities": normalize_entities_with_dictionary(_coerce_entity_list(extracted_entities), entity_dictionary or {}),
        "entities_source": "extract_entities_for_condition",
        "normalization_applied": True,
        "dictionary_loaded": dictionary_loaded,
    }


def markdown_escape(text: object, max_len: int = 180) -> str:
    """Escape compact text for a Markdown table cell."""

    escaped = str(text).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    escaped = " ".join(escaped.split())
    if len(escaped) > max_len:
        return escaped[:max_len] + "..."
    return escaped


def parse_atomic_chunk(
    chunk_text: str,
    chunk_entities: Sequence[JsonDict],
    atomic_parser: str = "syntactic",
) -> JsonDict:
    """Parse a single chunk with the configured atomic parser."""

    try:
        if atomic_parser == "syntactic":
            from src.parser.syntactic_atomic_condition_parser import parse_condition_line
        elif atomic_parser == "legacy":
            from src.parser.atomic_condition_parser import parse_condition_line
        else:
            raise ValueError(f"Unknown atomic parser: {atomic_parser}")
        return parse_condition_line(chunk_text, normalized_entities=list(chunk_entities))
    except Exception as exc:
        return {
            "condition_type": "atomic_parse_error",
            "raw_text": chunk_text,
            "error": str(exc),
            "need_review": True,
        }


def parse_special_chunk(chunk: JsonDict, atomic_parser: str = "syntactic") -> JsonDict:
    """Parse known non-atomic chunks when an existing parser is available."""

    chunk_type = str(chunk.get("chunk_type", ""))
    chunk_text = str(chunk.get("text", ""))
    try:
        if chunk_type == "duration_constraint":
            from src.parser.chunked_condition_parser import parse_duration_constraint

            return parse_duration_constraint(chunk_text)
        if chunk_type == "phase_timing_constraint":
            from src.parser.chunked_condition_parser import parse_phase_timing_constraint

            return parse_phase_timing_constraint(chunk_text)
        if chunk_type == "temporal_context_constraint":
            from src.parser.chunked_condition_parser import parse_temporal_context_constraint

            return parse_temporal_context_constraint(chunk_text)
        if chunk_type == "quantified_parenthesized_member_group":
            from src.parser.chunked_condition_parser import parse_quantified_parenthesized_member_group

            return parse_quantified_parenthesized_member_group(chunk, atomic_parser=atomic_parser)
    except Exception as exc:
        return {
            "condition_type": "special_chunk_parse_error",
            "raw_text": chunk_text,
            "chunk_type": chunk_type,
            "error": str(exc),
            "need_review": True,
        }

    return {
        "condition_type": chunk_type,
        "raw_text": chunk_text,
        "note": "special_chunk_not_atomic_parsed",
        "need_review": False,
    }


def parse_chunk(chunk: JsonDict, atomic_parser: str = "syntactic") -> JsonDict:
    """Dispatch one semantic chunk to atomic or special parsing."""

    chunk_type = str(chunk.get("chunk_type", ""))
    chunk_text = str(chunk.get("text", ""))
    chunk_entities = list(chunk.get("entities", []))
    if chunk_type in ATOMIC_CHUNK_TYPES:
        return parse_atomic_chunk(chunk_text, chunk_entities, atomic_parser=atomic_parser)
    if chunk_type in SPECIAL_CHUNK_TYPES:
        return parse_special_chunk(chunk, atomic_parser=atomic_parser)
    if chunk_type in RAW_CHUNK_TYPES:
        return {
            "condition_type": chunk_type,
            "raw_text": chunk_text,
            "need_review": chunk_type == "unparsed_chunk",
        }
    return parse_atomic_chunk(chunk_text, chunk_entities, atomic_parser=atomic_parser)


def parse_chunks_for_record(record: JsonDict, row_index: int, entity_dictionary: dict | None = None) -> JsonDict:
    """Chunk one record and attach placeholder atomic parse results."""

    record_id = get_record_id(record, row_index)
    try:
        text = get_condition_text(record)
        if text is None:
            return {
                "record_id": record_id,
                "row_index": row_index,
                "status": "SKIPPED",
                "error": "missing condition text",
                "entities_source": "empty",
                "normalization_applied": False,
                "dictionary_loaded": _is_dictionary_loaded(entity_dictionary),
            }

        entity_info = get_normalized_entities(record, text, entity_dictionary)
        normalized_entities = list(entity_info["entities"])
        chunk_result = chunk_condition_sentence(text, normalized_entities)
        chunk_parse_results: list[JsonDict] = []
        for chunk in chunk_result.get("chunks", []):
            if not isinstance(chunk, dict):
                continue
            chunk_parse_results.append(
                {
                    "chunk_id": chunk.get("chunk_id"),
                    "chunk_type": chunk.get("chunk_type"),
                    "chunk_text": chunk.get("text"),
                    "chunk_entities": list(chunk.get("entities", [])),
                    "parse_result": parse_chunk(chunk, atomic_parser=ATOMIC_PARSER),
                }
            )

        return {
            "record_id": record_id,
            "row_index": row_index,
            "raw_text": text,
            "normalized_entities": normalized_entities,
            "entities_source": entity_info["entities_source"],
            "normalization_applied": entity_info["normalization_applied"],
            "dictionary_loaded": entity_info["dictionary_loaded"],
            "chunk_result": chunk_result,
            "chunk_parse_results": chunk_parse_results,
            "status": "OK",
        }
    except Exception as exc:
        text = get_condition_text(record)
        entity_info = get_normalized_entities(record, text, entity_dictionary)
        return {
            "record_id": record_id,
            "row_index": row_index,
            "raw_text": text or "",
            "normalized_entities": list(entity_info["entities"]),
            "entities_source": entity_info["entities_source"],
            "normalization_applied": entity_info["normalization_applied"],
            "dictionary_loaded": entity_info["dictionary_loaded"],
            "chunk_result": {},
            "chunk_parse_results": [],
            "status": "ERROR",
            "error": str(exc),
        }


def summarize_results(results: Sequence[JsonDict]) -> JsonDict:
    """Summarize record, chunk, and placeholder parse counts."""

    parsed_records = [result for result in results if result.get("status") == "OK"]
    skipped_records = [result for result in results if result.get("status") == "SKIPPED"]
    error_records = [result for result in results if result.get("status") == "ERROR"]
    chunk_type_counts: Counter[str] = Counter()
    atomic_parse_type_counts: Counter[str] = Counter()
    total_chunks = 0

    for result in parsed_records:
        chunks = result.get("chunk_parse_results", [])
        if not isinstance(chunks, list):
            continue
        total_chunks += len(chunks)
        for chunk in chunks:
            if not isinstance(chunk, dict):
                continue
            chunk_type_counts[str(chunk.get("chunk_type", "UNKNOWN"))] += 1
            parse_result = chunk.get("parse_result", {})
            if isinstance(parse_result, dict):
                atomic_parse_type_counts[str(parse_result.get("condition_type") or "unknown")] += 1

    return {
        "total_records": len(results),
        "parsed_records": len(parsed_records),
        "skipped_records": len(skipped_records),
        "error_records": len(error_records),
        "total_chunks": total_chunks,
        "chunk_type_distribution": dict(sorted(chunk_type_counts.items())),
        "atomic_parse_type_distribution": dict(sorted(atomic_parse_type_counts.items())),
    }


def render_record_section(result: JsonDict) -> str:
    """Render one record into Markdown."""

    row_index = int(result.get("row_index", 0))
    record_id = str(result.get("record_id", f"ROW_{row_index:04d}"))
    status = str(result.get("status", "unknown"))
    lines = [f"### {row_index}. {record_id}\n\n"]

    if status != "OK":
        lines.append(f"Status: {status}\n\n")
        lines.append("```text\n")
        lines.append(str(result.get("error", "")) + "\n")
        lines.append("```\n\n")
        return "".join(lines)

    lines.append("Original Condition:\n\n")
    lines.append("```text\n")
    lines.append(str(result.get("raw_text", "")) + "\n")
    lines.append("```\n\n")
    lines.append(f"Entities Source: {markdown_escape(result.get('entities_source', 'empty'))}\n\n")
    lines.append(f"Normalization Applied: {str(bool(result.get('normalization_applied', False))).lower()}\n\n")
    lines.append(f"Dictionary Loaded: {str(bool(result.get('dictionary_loaded', False))).lower()}\n\n")

    lines.append("Chunks Overview:\n\n")
    lines.append("| # | chunk_type | chunk_text | parse_type | need_review |\n")
    lines.append("|---|------------|------------|------------|-------------|\n")
    parsed_chunks = result.get("chunk_parse_results", [])
    for index, parsed_chunk in enumerate(parsed_chunks, start=1):
        parse_result = parsed_chunk.get("parse_result", {}) if isinstance(parsed_chunk, dict) else {}
        parse_type = parse_result.get("condition_type") or "unknown" if isinstance(parse_result, dict) else "unknown"
        need_review = str(bool(parse_result.get("need_review", False))).lower() if isinstance(parse_result, dict) else "false"
        lines.append(
            f"| {index} | {markdown_escape(parsed_chunk.get('chunk_type', ''))} | "
            f"{markdown_escape(parsed_chunk.get('chunk_text', ''))} | {markdown_escape(parse_type)} | "
            f"{need_review} |\n"
        )

    for index, parsed_chunk in enumerate(parsed_chunks, start=1):
        lines.append(f"\n#### Chunk {index} Parse Result\n\n")
        lines.append("Chunk Text:\n\n")
        lines.append("```text\n")
        lines.append(str(parsed_chunk.get("chunk_text", "")) + "\n")
        lines.append("```\n\n")
        lines.append("Chunk Entities:\n\n")
        lines.append("```json\n")
        lines.append(json.dumps(parsed_chunk.get("chunk_entities", []), ensure_ascii=False, indent=2) + "\n")
        lines.append("```\n\n")
        lines.append("Parse Result:\n\n")
        lines.append("```json\n")
        lines.append(json.dumps(parsed_chunk.get("parse_result", {}), ensure_ascii=False, indent=2) + "\n")
        lines.append("```\n\n")
    return "".join(lines)


def write_markdown_report(results: Sequence[JsonDict], output_path: str | Path) -> None:
    """Write a Markdown report for chunked atomic debug results."""

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    summary = summarize_results(results)

    lines = ["# Chunked Atomic Condition Debug Report\n\n"]
    lines.append("## Summary\n\n")
    lines.append(f"- Total records: {summary['total_records']}\n")
    lines.append(f"- Parsed records: {summary['parsed_records']}\n")
    lines.append(f"- Skipped records: {summary['skipped_records']}\n")
    lines.append(f"- Error records: {summary['error_records']}\n")
    lines.append(f"- Total chunks: {summary['total_chunks']}\n")
    lines.append("- Chunk type distribution:\n")
    for chunk_type, count in summary["chunk_type_distribution"].items():
        lines.append(f"  - {chunk_type}: {count}\n")
    if not summary["chunk_type_distribution"]:
        lines.append("  - None: 0\n")
    lines.append("- Atomic parse type distribution:\n")
    for parse_type, count in summary["atomic_parse_type_distribution"].items():
        lines.append(f"  - {parse_type}: {count}\n")
    if not summary["atomic_parse_type_distribution"]:
        lines.append("  - None: 0\n")
    lines.append("\n## Records\n\n")
    for result in results:
        lines.append(render_record_section(result))

    output.write_text("".join(lines), encoding="utf-8")


def main() -> int:
    """Run the chunked atomic condition debug report script."""

    entity_dictionary = load_entity_dictionary(DICTIONARY_PATH)
    records = load_jsonl(INPUT_JSONL)
    if isinstance(MAX_RECORDS, int):
        records = records[:MAX_RECORDS]

    results: list[JsonDict] = []
    for row_index, record in enumerate(records, start=1):
        try:
            results.append(parse_chunks_for_record(record, row_index, entity_dictionary))
        except Exception as exc:
            results.append(
                {
                    "row_index": row_index,
                    "record_id": get_record_id(record, row_index),
                    "status": "ERROR",
                    "error": str(exc),
                    "entities_source": "empty",
                    "normalization_applied": False,
                    "dictionary_loaded": _is_dictionary_loaded(entity_dictionary),
                }
            )

    write_markdown_report(results, OUTPUT_MD)
    print(f"Wrote {len(results)} records to {OUTPUT_MD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
