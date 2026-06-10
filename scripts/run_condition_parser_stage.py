import argparse
import sys
from pathlib import Path
from typing import List

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import base_row, json_block, read_jsonl, row_id, text_block, write_jsonl, write_markdown
from src.parser.condition_parser import flatten_condition_groups, parse_condition_group_children
from src.schemas import JsonDict


def run_condition_parser_stage(input_jsonl: Path, output_jsonl: Path, output_md: Path) -> List[JsonDict]:
    """Parse condition_group children into atomic parsed condition objects."""

    output_rows: List[JsonDict] = []
    md = ["# Condition Parser Stage Review\n\n"]
    for index, row in enumerate(read_jsonl(input_jsonl), 1):
        parsed_groups = []
        for group in row.get("condition_groups", []):
            parsed_groups.append({**group, "children": parse_condition_group_children(group.get("children", []))})
        parsed_conditions = flatten_condition_groups(parsed_groups)
        output_row = {
            **base_row(row),
            "raw_conditions": row.get("raw_conditions", ""),
            "condition_groups": row.get("condition_groups", []),
            "parsed_condition_groups": parsed_groups,
            "parsed_conditions": parsed_conditions,
        }
        output_rows.append(output_row)

        md.append(f"## {index}. {row_id(row)}\n\n")
        md.append("**Raw Conditions**\n\n")
        md.append(text_block(str(row.get("raw_conditions", ""))) + "\n\n")
        md.append("**Parsed Condition Groups**\n\n")
        md.append(json_block(parsed_groups) + "\n\n")
        md.append("**Flattened Parsed Conditions**\n\n")
        md.append(json_block(parsed_conditions) + "\n\n")

    write_jsonl(output_jsonl, output_rows)
    write_markdown(output_md, "".join(md))
    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run condition_parser stage over condition groups.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    run_condition_parser_stage(args.input, args.output_jsonl, args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
