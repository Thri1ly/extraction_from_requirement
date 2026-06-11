import argparse
import json
import sys
from pathlib import Path
from typing import List, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import json_block, read_jsonl, row_id, text_block, write_jsonl, write_markdown
from scripts.debug_atomic_condition_line import debug_atomic_condition_line
from src.schemas import JsonDict


CONDITION_LINE_KEYS = ["condition_line", "condition line", "text", "condition"]
ENTITY_KEYS = ["entities", "normalized_input_entities", "rule_entities", "ner_entities"]


def run_batch_debug_atomic_conditions(
    input_jsonl: Path,
    dictionary_path: Path,
    output_jsonl: Path,
    output_md: Path,
    unknown_candidates_path: Path | None = None,
) -> List[JsonDict]:
    """Debug atomic parsing for all condition lines in a JSONL file."""

    results: List[JsonDict] = []
    for row in read_jsonl(input_jsonl):
        condition_line = _condition_line_from_row(row)
        entities = _entities_from_row(row)
        result = debug_atomic_condition_line(
            condition_line=condition_line,
            entities=entities,
            dictionary_path=dictionary_path,
            unknown_candidates_path=unknown_candidates_path,
            requirement_id=row_id(row),
        )
        results.append({**_source_metadata(row), **result})

    write_jsonl(output_jsonl, results)
    write_markdown(output_md, build_markdown_report(results))
    write_category_reports(output_md, results)
    return results


def build_markdown_report(results: Sequence[JsonDict]) -> str:
    """Build a Markdown report with aggregate parse metrics and row details."""

    metrics = summarize_results(results)
    md = ["# Batch Atomic Condition Debug Report\n\n"]
    md.append("## Summary\n\n")
    md.append(f"- Total condition lines: {metrics['total']}\n")
    md.append(f"- Parsed without review: {metrics['parsed_without_review']}\n")
    md.append(f"- Parsed with review: {metrics['parsed_with_review']}\n")
    md.append(f"- Unparsed: {metrics['unparsed']}\n")
    md.append(f"- Average overall confidence: {metrics['average_overall_confidence']:.2f}\n\n")

    md.append("## Details\n\n")
    for index, result in enumerate(results, 1):
        parsed = result.get("parsed", {})
        md.append(f"### {index}. {result.get('requirement_id') or 'UNKNOWN_ID'}\n\n")
        md.append(f"- Parsed type: `{parsed.get('type', 'UNKNOWN')}`\n")
        md.append(f"- Need review: `{str(parsed.get('need_review', False)).lower()}`\n")
        md.append(f"- Overall confidence: `{_overall_confidence(result):.2f}`\n\n")
        md.append("**Condition Line**\n\n")
        md.append(text_block(str(result.get("condition_line", ""))) + "\n\n")
        md.append("**Parsed Result**\n\n")
        md.append(json_block(parsed) + "\n\n")
    return "".join(md)


def write_category_reports(output_md: Path, results: Sequence[JsonDict]) -> None:
    """Write parsed/review/unparsed detail reports next to the main report."""

    categories = {
        "parsed_without_review": ("Parsed Without Review", _is_parsed_without_review),
        "parsed_with_review": ("Parsed With Review", _is_parsed_with_review),
        "unparsed": ("Unparsed", _is_unparsed),
    }
    for suffix, (title, predicate) in categories.items():
        category_path = output_md.with_name(f"{output_md.stem}.{suffix}{output_md.suffix}")
        category_results = [result for result in results if predicate(result)]
        write_markdown(category_path, build_category_report(title, category_results))


def build_category_report(title: str, results: Sequence[JsonDict]) -> str:
    """Build a Markdown detail report for one parse category."""

    md = [f"# {title}\n\n"]
    md.append(f"- Count: {len(results)}\n\n")
    for index, result in enumerate(results, 1):
        parsed = result.get("parsed", {})
        md.append(f"## {index}. {result.get('requirement_id') or 'UNKNOWN_ID'}\n\n")
        md.append(f"- Parsed type: `{parsed.get('type', 'UNKNOWN')}`\n")
        md.append(f"- Need review: `{str(parsed.get('need_review', False)).lower()}`\n")
        md.append(f"- Overall confidence: `{_overall_confidence(result):.2f}`\n\n")
        md.append("**Condition Line**\n\n")
        md.append(text_block(str(result.get("condition_line", ""))) + "\n\n")
        md.append("**Normalized Entities**\n\n")
        md.append(json_block(result.get("normalized_entities", [])) + "\n\n")
        md.append("**Parsed Result**\n\n")
        md.append(json_block(parsed) + "\n\n")
    return "".join(md)


def summarize_results(results: Sequence[JsonDict]) -> JsonDict:
    """Compute aggregate counts and confidence statistics."""

    total = len(results)
    unparsed = 0
    parsed_with_review = 0
    parsed_without_review = 0
    confidence_values: List[float] = []

    for result in results:
        parsed = result.get("parsed", {})
        parsed_type = parsed.get("type")
        need_review = bool(parsed.get("need_review"))
        if parsed_type == "unparsed_condition":
            unparsed += 1
        elif need_review:
            parsed_with_review += 1
        else:
            parsed_without_review += 1
        confidence_values.append(_overall_confidence(result))

    average_confidence = sum(confidence_values) / len(confidence_values) if confidence_values else 0.0
    return {
        "total": total,
        "parsed_without_review": parsed_without_review,
        "parsed_with_review": parsed_with_review,
        "unparsed": unparsed,
        "average_overall_confidence": round(average_confidence, 2),
    }


def _is_unparsed(result: JsonDict) -> bool:
    return result.get("parsed", {}).get("type") == "unparsed_condition"


def _is_parsed_with_review(result: JsonDict) -> bool:
    parsed = result.get("parsed", {})
    return parsed.get("type") != "unparsed_condition" and bool(parsed.get("need_review"))


def _is_parsed_without_review(result: JsonDict) -> bool:
    parsed = result.get("parsed", {})
    return parsed.get("type") != "unparsed_condition" and not bool(parsed.get("need_review"))


def _condition_line_from_row(row: JsonDict) -> str:
    for key in CONDITION_LINE_KEYS:
        if row.get(key):
            return str(row[key])
    raise ValueError(f"Missing condition line field. Expected one of: {', '.join(CONDITION_LINE_KEYS)}")


def _entities_from_row(row: JsonDict) -> List[JsonDict]:
    entities: List[JsonDict] = []
    for key in ENTITY_KEYS:
        value = row.get(key)
        if isinstance(value, list):
            entities.extend(dict(item) for item in value if isinstance(item, dict))
    return entities


def _source_metadata(row: JsonDict) -> JsonDict:
    return {
        key: row[key]
        for key in ("chunk_id", "feature_id", "feature_name")
        if key in row
    }


def _overall_confidence(result: JsonDict) -> float:
    confidence = result.get("parse_confidence")
    if isinstance(confidence, dict):
        try:
            return float(confidence.get("overall", 0.0))
        except (TypeError, ValueError):
            return 0.0
    return 0.0


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser for batch atomic condition debugging."""

    parser = argparse.ArgumentParser(description="Batch debug atomic condition parsing from a JSONL file.")
    parser.add_argument("--input", required=True, type=Path, help="Input JSONL with condition_line and entities fields.")
    parser.add_argument("--dictionary", required=True, type=Path, help="Entity dictionary JSON/JSONL path.")
    parser.add_argument("--output-jsonl", required=True, type=Path, help="Detailed debug result JSONL output path.")
    parser.add_argument("--output-md", required=True, type=Path, help="Markdown summary report output path.")
    parser.add_argument("--unknown-candidates", type=Path, help="Optional JSONL path for dictionary misses.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    run_batch_debug_atomic_conditions(
        input_jsonl=args.input,
        dictionary_path=args.dictionary,
        output_jsonl=args.output_jsonl,
        output_md=args.output_md,
        unknown_candidates_path=args.unknown_candidates,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
