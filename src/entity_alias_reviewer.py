import argparse
import json
from pathlib import Path
from typing import Callable, List, Sequence

from src.entity_dictionary_builder import load_jsonl, normalize_entity_type, write_jsonl
from src.schemas import JsonDict


STATUS_VALUES = {"approved", "rejected", "pending"}


def review_candidates(
    candidates: Sequence[JsonDict],
    input_func: Callable[[str], str] = input,
    print_func: Callable[[str], None] = print,
) -> List[JsonDict]:
    """Interactively review alias candidates and return edited records."""

    reviewed: List[JsonDict] = []
    total = len(candidates)
    for index, candidate in enumerate(candidates, start=1):
        current = dict(candidate)
        default_canonical = str(current.get("canonical_name") or current.get("suggested_canonical") or "")
        default_type = str(current.get("type") or "unknown")
        default_status = str(current.get("status") or "pending").lower()

        _print_candidate(index, total, current, print_func)
        canonical_name = _prompt_value(input_func, "canonical_name", default_canonical)
        entity_type = _prompt_value(input_func, "type", default_type)
        status = _prompt_status(input_func, print_func, default_status)

        if canonical_name:
            current["canonical_name"] = canonical_name
        current["type"] = normalize_entity_type(entity_type or default_type)
        current["status"] = status
        reviewed.append(current)
    return reviewed


def filter_approved(candidates: Sequence[JsonDict]) -> List[JsonDict]:
    """Return only candidates whose status is approved."""

    return [dict(candidate) for candidate in candidates if str(candidate.get("status", "")).lower() == "approved"]


def review_from_files(args: argparse.Namespace) -> tuple[List[JsonDict], List[JsonDict]]:
    """Review candidates from disk and write approved/reviewed JSONL outputs."""

    candidates = load_jsonl(Path(args.input))
    reviewed = review_candidates(candidates)
    approved = filter_approved(reviewed)
    write_jsonl(Path(args.approved_output), approved)
    if args.reviewed_output:
        write_jsonl(Path(args.reviewed_output), reviewed)
    return reviewed, approved


def build_arg_parser() -> argparse.ArgumentParser:
    """Create CLI parser for candidate review."""

    parser = argparse.ArgumentParser(description="Interactively review entity alias candidates.")
    parser.add_argument("--input", default="data/entity_alias_candidates.jsonl", help="Input candidate JSONL path.")
    parser.add_argument(
        "--approved-output",
        default="data/entity_alias_approved.jsonl",
        help="Output JSONL path containing approved items only.",
    )
    parser.add_argument(
        "--reviewed-output",
        default=None,
        help="Optional JSONL path containing every reviewed item with edited fields.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point."""

    args = build_arg_parser().parse_args(argv)
    reviewed, approved = review_from_files(args)
    print(f"Reviewed {len(reviewed)} candidates.")
    print(f"Wrote {len(approved)} approved candidates to {args.approved_output}")
    if args.reviewed_output:
        print(f"Wrote all reviewed candidates to {args.reviewed_output}")
    return 0


def _print_candidate(index: int, total: int, candidate: JsonDict, print_func: Callable[[str], None]) -> None:
    print_func("")
    print_func(f"[{index}/{total}] mention: {candidate.get('mention', '')}")
    print_func(f"  suggested_canonical: {candidate.get('suggested_canonical', '')}")
    if candidate.get("canonical_name"):
        print_func(f"  canonical_name: {candidate.get('canonical_name', '')}")
    print_func(f"  type: {candidate.get('type', '')}")
    print_func(f"  status: {candidate.get('status', '')}")
    print_func(f"  confidence: {candidate.get('confidence', '')}")
    evidence = candidate.get("evidence", [])
    if evidence:
        print_func(f"  evidence: {json.dumps(evidence, ensure_ascii=False)}")


def _prompt_value(input_func: Callable[[str], str], field_name: str, default: str) -> str:
    value = input_func(f"{field_name} [{default}]: ").strip()
    return default if value == "" else value


def _prompt_status(input_func: Callable[[str], str], print_func: Callable[[str], None], default: str) -> str:
    while True:
        value = input_func(f"status approved/rejected/pending [{default}]: ").strip().lower()
        status = default if value == "" else value
        if status in STATUS_VALUES:
            return status
        print_func(f"Invalid status: {status}. Use approved, rejected, or pending.")
