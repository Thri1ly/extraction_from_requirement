import argparse
from pathlib import Path
from typing import List, Sequence

from src.entity_dictionary_builder import load_dictionary, load_jsonl, write_jsonl
from src.normalizer import normalize_entities
from src.schemas import JsonDict


def normalize_requirement_rows(
    requirements: Sequence[JsonDict],
    dictionary: Sequence[JsonDict],
    unknown_candidates_path: str | Path | None = None,
) -> List[JsonDict]:
    """Normalize extracted entities for requirement rows without parsing later layers."""

    normalized_rows: List[JsonDict] = []
    for row in requirements:
        item = dict(row)
        requirement_id = str(item.get("requirement_id") or item.get("id") or "")
        raw_text = str(item.get("raw_text") or item.get("text") or item.get("requirement") or "")
        item["raw_text"] = raw_text
        item["normalized_entities"] = normalize_entities(
            raw_text,
            rule_entities=item.get("rule_entities", []),
            ner_entities=item.get("ner_entities", []),
            dictionary=dictionary,
            unknown_candidates_path=unknown_candidates_path,
            requirement_id=requirement_id,
        )
        normalized_rows.append(item)
    return normalized_rows


def normalize_from_files(args: argparse.Namespace) -> List[JsonDict]:
    """Load requirements and dictionary, then write normalized requirement JSONL."""

    requirements = load_jsonl(Path(args.input))
    dictionary = load_dictionary(Path(args.dictionary))
    rows = normalize_requirement_rows(
        requirements,
        dictionary=dictionary,
        unknown_candidates_path=args.unknown_candidates_output,
    )
    write_jsonl(Path(args.output), rows)
    return rows


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(description="Normalize extracted entities using an entity dictionary.")
    parser.add_argument("--input", required=True, help="Input requirements_with_entities JSONL path.")
    parser.add_argument("--dictionary", required=True, help="Entity dictionary JSON/JSONL path.")
    parser.add_argument("--output", required=True, help="Output requirements_with_normalized_entities JSONL path.")
    parser.add_argument(
        "--unknown-candidates-output",
        default=None,
        help="Optional JSONL path for mentions not found in the dictionary.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    rows = normalize_from_files(args)
    print(f"Wrote {len(rows)} normalized requirement rows to {args.output}")
    return 0
