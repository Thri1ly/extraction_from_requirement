import argparse
import importlib
import json
from datetime import datetime
from pathlib import Path
from typing import Callable, List, Sequence

from src.requirements_with_entities_builder import normalize_entities
from src.schemas import JsonDict


Extractor = Callable[[str], List[JsonDict]]
EXIT_COMMANDS = {":q", ":quit", "exit", "quit"}


def load_extractor(spec: str) -> Extractor:
    """Load an extractor callable from a module:function spec."""

    if ":" not in spec:
        raise ValueError(f"Extractor spec must be module:function, got: {spec}")
    module_name, function_name = spec.split(":", 1)
    module = importlib.import_module(module_name)
    extractor = getattr(module, function_name)
    if not callable(extractor):
        raise TypeError(f"Extractor is not callable: {spec}")
    return extractor


def count_existing_records(output_path: Path) -> int:
    """Count existing non-blank JSONL records."""

    if not output_path.exists():
        return 0
    with output_path.open("r", encoding="utf-8-sig") as file:
        return sum(1 for line in file if line.strip())


def make_requirement_id(index: int, prefix: str = "REQ_INTERACTIVE") -> str:
    """Create a stable interactive requirement ID from a 1-based index."""

    return f"{prefix}_{index:06d}"


def run_single_extraction(
    text: str,
    rule_extractor: Extractor,
    ner_extractor: Extractor,
    output_path: Path,
    requirement_id: str,
) -> JsonDict:
    """Run both extractors for one requirement and append the result to JSONL."""

    rule_entities = normalize_entities(rule_extractor(text))
    ner_entities = normalize_entities(ner_extractor(text))
    record: JsonDict = {
        "requirement_id": requirement_id,
        "raw_text": text,
        "rule_entities": rule_entities,
        "ner_entities": ner_entities,
        "created_at": datetime.now().isoformat(timespec="seconds"),
    }
    append_record(output_path, record)
    return record


def append_record(output_path: Path, record: JsonDict) -> None:
    """Append one JSONL record without truncating existing history."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def interactive_loop(
    rule_extractor: Extractor,
    ner_extractor: Extractor,
    output_path: Path,
    id_prefix: str = "REQ_INTERACTIVE",
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> None:
    """Read requirements interactively, run extractors, print and append results."""

    next_index = count_existing_records(output_path) + 1
    print_func(f"Appending extraction records to {output_path}")
    print_func("Enter a requirement. Use :q, :quit, exit, or quit to stop.")
    while True:
        try:
            text = input_func("requirement> ").strip()
        except (KeyboardInterrupt, EOFError):
            print_func("")
            print_func("Interrupted. Existing records have already been saved.")
            return

        if not text:
            continue
        if text.lower() in EXIT_COMMANDS:
            print_func("Stopped.")
            return

        requirement_id = make_requirement_id(next_index, id_prefix)
        record = run_single_extraction(
            text,
            rule_extractor=rule_extractor,
            ner_extractor=ner_extractor,
            output_path=output_path,
            requirement_id=requirement_id,
        )
        print_extraction_record(record, print_func)
        print_func(f"Saved to {output_path}")
        next_index += 1


def print_extraction_record(record: JsonDict, print_func: Callable[[str], None] = print) -> None:
    """Print a compact comparison of text, rule entities, and NER entities."""

    print_func("")
    print_func(f"ID: {record.get('requirement_id')}")
    print_func(f"Text: {record.get('raw_text')}")
    print_func("Rule entities:")
    print_func(json.dumps(record.get("rule_entities", []), ensure_ascii=False, indent=2))
    print_func("NER entities:")
    print_func(json.dumps(record.get("ner_entities", []), ensure_ascii=False, indent=2))
    print_func("")


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""

    parser = argparse.ArgumentParser(description="Interactively run rule and NER extractors for one requirement at a time.")
    parser.add_argument("--rule-extractor", required=True, help="Rule extractor callable as module:function.")
    parser.add_argument("--ner-extractor", required=True, help="NER extractor callable as module:function.")
    parser.add_argument(
        "--output",
        default="data/interactive_entity_extraction_records.jsonl",
        help="Append-only JSONL output path.",
    )
    parser.add_argument("--id-prefix", default="REQ_INTERACTIVE", help="Prefix for generated requirement IDs.")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    interactive_loop(
        rule_extractor=load_extractor(args.rule_extractor),
        ner_extractor=load_extractor(args.ner_extractor),
        output_path=Path(args.output),
        id_prefix=args.id_prefix,
    )
    return 0
