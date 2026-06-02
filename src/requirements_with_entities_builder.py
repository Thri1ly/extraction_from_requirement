import argparse
import json
from pathlib import Path
from typing import Iterable, List, Sequence

from src.entity_dictionary_builder import load_jsonl, normalize_entity_type, write_jsonl
from src.schemas import JsonDict


ENTITY_LIST_FIELDS = ("entities", "rule_entities", "ner_entities")


def build_requirements_with_entities(
    requirements: Sequence[JsonDict],
    rule_rows: Sequence[object] | None = None,
    ner_rows: Sequence[object] | None = None,
) -> List[JsonDict]:
    """Attach rule and NER entities to requirement rows."""

    rule_index = build_entity_index(rule_rows or [])
    ner_index = build_entity_index(ner_rows or [])
    merged: List[JsonDict] = []
    for row_index, requirement in enumerate(requirements):
        item = dict(requirement)
        key = requirement_key(item, row_index)
        existing_rule = normalize_entities(item.get("rule_entities", []))
        existing_ner = normalize_entities(item.get("ner_entities", []))
        item["rule_entities"] = dedupe_entities(existing_rule + rule_index.get(key, []))
        item["ner_entities"] = dedupe_entities(existing_ner + ner_index.get(key, []))
        merged.append(item)
    return merged


def build_entity_index(rows: Sequence[object]) -> dict[str, List[JsonDict]]:
    """Build an entity lookup by requirement_id when present, otherwise by row index."""

    index: dict[str, List[JsonDict]] = {}
    for row_index, row in enumerate(rows):
        key = extraction_key(row, row_index)
        index.setdefault(key, []).extend(extract_entities_from_row(row))
    return {key: dedupe_entities(value) for key, value in index.items()}


def normalize_entities(entities: Iterable[object]) -> List[JsonDict]:
    """Normalize extractor entities to {'mention': ..., 'type': ...} plus extra fields."""

    normalized: List[JsonDict] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        mention = str(entity.get("mention") or entity.get("text") or entity.get("name") or "").strip()
        if not mention:
            continue
        item = dict(entity)
        item["mention"] = mention
        item["type"] = normalize_entity_type(item.get("type", "UNKNOWN"))
        item.pop("text", None)
        item.pop("name", None)
        normalized.append(item)
    return normalized


def dedupe_entities(entities: Sequence[JsonDict]) -> List[JsonDict]:
    """Deduplicate entities while preserving first occurrence and extra metadata."""

    seen = set()
    result = []
    for entity in entities:
        key = (
            str(entity.get("mention", "")).strip().lower(),
            normalize_entity_type(entity.get("type", "UNKNOWN")),
            entity.get("start"),
            entity.get("end"),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(entity)
    return result


def extract_entities_from_row(row: object) -> List[JsonDict]:
    """Extract entity lists from supported extractor output row formats."""

    if isinstance(row, list):
        return normalize_entities(row)
    if not isinstance(row, dict):
        return []
    if row.get("mention") or row.get("text") or row.get("name"):
        return normalize_entities([row])
    for field_name in ENTITY_LIST_FIELDS:
        value = row.get(field_name)
        if isinstance(value, list):
            return normalize_entities(value)
    return []


def requirement_key(requirement: JsonDict, row_index: int) -> str:
    """Return the merge key for a requirement row."""

    requirement_id = requirement.get("requirement_id") or requirement.get("id")
    return str(requirement_id) if requirement_id else f"__row_{row_index}"


def extraction_key(row: object, row_index: int) -> str:
    """Return the merge key for an extractor row."""

    if isinstance(row, dict):
        requirement_id = row.get("requirement_id") or row.get("id")
        if requirement_id:
            return str(requirement_id)
    return f"__row_{row_index}"


def read_jsonl_rows(path: Path) -> List[JsonDict]:
    """Read JSONL rows with BOM tolerance."""

    return load_jsonl(path)


def build_from_files(args: argparse.Namespace) -> List[JsonDict]:
    """Build requirements_with_entities JSONL from CLI arguments."""

    requirements = read_jsonl_rows(Path(args.requirements))
    rule_rows = read_jsonl_rows(Path(args.rule_entities)) if args.rule_entities else []
    ner_rows = read_jsonl_rows(Path(args.ner_entities)) if args.ner_entities else []
    merged = build_requirements_with_entities(requirements, rule_rows=rule_rows, ner_rows=ner_rows)
    write_jsonl(Path(args.output), merged)
    return merged


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(description="Attach rule and NER extractor outputs to requirement JSONL rows.")
    parser.add_argument("--requirements", required=True, help="Raw requirements JSONL path.")
    parser.add_argument("--rule-entities", default=None, help="Rule extractor output JSONL path.")
    parser.add_argument("--ner-entities", default=None, help="NER extractor output JSONL path.")
    parser.add_argument("--output", required=True, help="Output requirements_with_entities JSONL path.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    merged = build_from_files(args)
    print(f"Wrote {len(merged)} requirement rows to {args.output}")
    return 0
