import argparse
from pathlib import Path
from typing import List, Sequence

from src.entity_dictionary_builder import load_dictionary, normalize_dictionary_entities, write_dictionary
from src.schemas import JsonDict


def sort_dictionary_entities(entities: Sequence[JsonDict]) -> List[JsonDict]:
    """Sort dictionary entities by type, then by canonical_name."""

    normalized = normalize_dictionary_entities(entities)
    return sorted(
        normalized,
        key=lambda item: (
            str(item.get("type", "")).upper(),
            str(item.get("canonical_name", "")).upper(),
            str(item.get("canonical_name", "")),
        ),
    )


def sort_dictionary_file(input_path: Path, output_path: Path) -> List[JsonDict]:
    """Read, sort, and write an entity dictionary."""

    sorted_entities = sort_dictionary_entities(load_dictionary(input_path))
    write_dictionary(output_path, sorted_entities)
    return sorted_entities


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(description="Sort an entity dictionary by type and canonical_name.")
    parser.add_argument("--input", required=True, help="Input dictionary JSON/JSONL path.")
    parser.add_argument("--output", required=True, help="Output sorted dictionary JSON/JSONL path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    sorted_entities = sort_dictionary_file(Path(args.input), Path(args.output))
    print(f"Wrote {len(sorted_entities)} sorted dictionary entities to {args.output}")
    return 0
