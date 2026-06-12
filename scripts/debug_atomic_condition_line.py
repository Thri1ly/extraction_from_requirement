import argparse
import json
import sys
from pathlib import Path
from typing import List, Sequence

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import write_jsonl
from src.parser.atomic_condition_parser import parse_condition_line
from src.parser.syntactic_atomic_condition_parser import (
    build_syntax_analysis,
    parse_condition_line as parse_syntactic_condition_line,
)
from src.entity_dictionary_builder import load_jsonl
from src.normalizer import normalize_entities
from src.schemas import JsonDict

ATOMIC_PARSERS = {
    "legacy": parse_condition_line,
    "syntactic": parse_syntactic_condition_line,
}


def debug_atomic_condition_line(
    condition_line: str,
    entities: Sequence[JsonDict],
    dictionary_path: Path,
    unknown_candidates_path: Path | None = None,
    requirement_id: str | None = None,
    atomic_parser: str = "legacy",
) -> JsonDict:
    """Normalize supplied entities and parse one condition line for interactive debugging."""

    parser_func = resolve_atomic_parser(atomic_parser)
    normalized_entities = normalize_entities(
        text=condition_line,
        rule_entities=list(entities),
        dictionary_path=dictionary_path,
        unknown_candidates_path=unknown_candidates_path,
        requirement_id=requirement_id,
    )
    parsed = parser_func(condition_line, normalized_entities=normalized_entities)
    result = {
        "requirement_id": requirement_id,
        "condition_line": condition_line,
        "atomic_parser": atomic_parser,
        "input_entities": list(entities),
        "normalized_entities": normalized_entities,
        "parse_confidence": parse_confidence(parsed, normalized_entities),
        "parsed": parsed,
    }
    if atomic_parser == "syntactic":
        result["syntax_analysis"] = build_syntax_analysis(condition_line, normalized_entities)
    return result


def resolve_atomic_parser(parser_name: str):
    """Return the requested atomic parser callable."""

    try:
        return ATOMIC_PARSERS[parser_name]
    except KeyError as exc:
        choices = ", ".join(sorted(ATOMIC_PARSERS))
        raise ValueError(f"Unknown atomic parser '{parser_name}'. Expected one of: {choices}") from exc


def parse_confidence(parsed: JsonDict, normalized_entities: Sequence[JsonDict] | None = None) -> JsonDict:
    """Return a debug-friendly confidence summary for the parsed condition."""

    confidence = parsed.get("confidence")
    if isinstance(confidence, dict):
        parser_confidence = float(confidence.get("overall", 0.9))
    elif parsed.get("need_review"):
        parser_confidence = 0.2
    else:
        parser_confidence = 0.9

    normalization_confidence = min(
        (
            float(entity.get("normalization_confidence", 1.0))
            for entity in (normalized_entities or [])
        ),
        default=1.0,
    )
    overall = round(min(parser_confidence, normalization_confidence), 2)
    if normalization_confidence < 1.0:
        return {
            "overall": overall,
            "parser": round(parser_confidence, 2),
            "normalization": round(normalization_confidence, 2),
        }
    if isinstance(confidence, dict):
        result = dict(confidence)
        result["overall"] = overall
        return result
    return {"overall": overall}


def load_entities(entities_json: str | None = None, entities_file: Path | None = None) -> List[JsonDict]:
    """Load extractor entities from a JSON string or JSON/JSONL file."""

    if entities_json and entities_file:
        raise ValueError("Use either --entities-json or --entities-file, not both.")
    if entities_json:
        payload = json.loads(entities_json)
        return _entities_from_payload(payload)
    if entities_file:
        if entities_file.suffix.lower() == ".jsonl":
            rows = load_jsonl(entities_file)
            if len(rows) == 1 and isinstance(rows[0].get("entities"), list):
                return _entities_from_payload(rows[0])
            return _entities_from_payload(rows)
        payload = json.loads(entities_file.read_text(encoding="utf-8-sig"))
        return _entities_from_payload(payload)
    return []


def _entities_from_payload(payload: object) -> List[JsonDict]:
    if isinstance(payload, dict) and isinstance(payload.get("entities"), list):
        payload = payload["entities"]
    if not isinstance(payload, list):
        raise ValueError("Entities input must be a JSON array or an object with an 'entities' array.")
    entities: List[JsonDict] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entity #{index} must be an object.")
        entities.append(dict(item))
    return entities


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser for single-line atomic condition debugging."""

    parser = argparse.ArgumentParser(description="Debug atomic parsing for one condition line with supplied entities.")
    parser.add_argument("--condition-line", required=True, help="One condition line to parse.")
    parser.add_argument("--dictionary", required=True, type=Path, help="Entity dictionary JSON/JSONL path.")
    parser.add_argument("--entities-json", help="Extractor entities as a JSON array.")
    parser.add_argument("--entities-file", type=Path, help="Extractor entities from a JSON or JSONL file.")
    parser.add_argument("--unknown-candidates", type=Path, help="Optional JSONL path for dictionary misses.")
    parser.add_argument("--requirement-id", help="Optional ID recorded in unknown candidate evidence.")
    parser.add_argument(
        "--atomic-parser",
        choices=sorted(ATOMIC_PARSERS),
        default="legacy",
        help="Atomic parser module to use.",
    )
    parser.add_argument("--output-json", type=Path, help="Optional path to write the debug result as pretty JSON.")
    parser.add_argument("--output-jsonl", type=Path, help="Optional path to write the debug result as one JSONL row.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    parser = build_arg_parser()
    args = parser.parse_args(argv)
    entities = load_entities(args.entities_json, args.entities_file)
    result = debug_atomic_condition_line(
        condition_line=args.condition_line,
        entities=entities,
        dictionary_path=args.dictionary,
        unknown_candidates_path=args.unknown_candidates,
        requirement_id=args.requirement_id,
        atomic_parser=args.atomic_parser,
    )
    formatted = json.dumps(result, ensure_ascii=False, indent=2)
    print(formatted)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(formatted + "\n", encoding="utf-8")
    if args.output_jsonl:
        write_jsonl(args.output_jsonl, [result])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
