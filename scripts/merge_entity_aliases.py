import argparse
import json
import sys
from pathlib import Path


if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.entity_dictionary_builder import merge_from_files


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Merge reviewed approved alias JSONL into an entity dictionary.")
    parser.add_argument("--dictionary", required=True, help="Path to signals/entity dictionary JSON or JSONL.")
    parser.add_argument("--candidates", required=True, help="Path to approved alias JSONL from review_entity_alias_candidates.py.")
    parser.add_argument(
        "--output",
        default="config/entities/signals_merged.json",
        help="Output merged dictionary path. Use .jsonl to write JSONL, otherwise JSON is written.",
    )
    parser.add_argument(
        "--report-output",
        default="data/entity_alias_merge_report.json",
        help="Optional merge report JSON path.",
    )
    parser.add_argument(
        "--create-missing",
        action="store_true",
        default=True,
        help="Create new entities for approved candidates whose canonical_name is not in the dictionary. Enabled by default.",
    )
    parser.add_argument(
        "--no-create-missing",
        action="store_false",
        dest="create_missing",
        help="Do not create missing canonical entities; report them as unmatched instead.",
    )
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()
    report = merge_from_files(args)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Wrote merged dictionary to {args.output}")
    if args.report_output:
        print(f"Wrote merge report to {args.report_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
