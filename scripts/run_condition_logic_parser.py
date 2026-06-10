import argparse
import sys
from pathlib import Path
from typing import List

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import (
    base_row,
    collect_condition_line_texts_from_group,
    json_block,
    read_jsonl,
    row_id,
    text_block,
    write_jsonl,
    write_markdown,
)
from src.parser.condition_logic_parser import parse_condition_logic
from src.schemas import JsonDict


def run_condition_logic_parser(
    input_jsonl: Path,
    output_jsonl: Path,
    output_md: Path,
    output_lines_jsonl: Path | None = None,
) -> List[JsonDict]:
    """Convert extracted condition blocks into condition groups."""

    output_rows: List[JsonDict] = []
    condition_line_rows: List[JsonDict] = []
    md = ["# Condition Logic Parser Review\n\n"]
    for index, row in enumerate(read_jsonl(input_jsonl), 1):
        groups = [parse_condition_logic(block) for block in row.get("condition_blocks", [])]
        for group in groups:
            condition_line_rows.extend(
                {"condition line": line}
                for line in collect_condition_line_texts_from_group(group)
            )
        output_row = {
            **base_row(row),
            "raw_conditions": row.get("raw_conditions", ""),
            "condition_blocks": row.get("condition_blocks", []),
            "condition_groups": groups,
        }
        output_rows.append(output_row)

        md.append(f"## {index}. {row_id(row)}\n\n")
        md.append("**Raw Conditions**\n\n")
        md.append(text_block(str(row.get("raw_conditions", ""))) + "\n\n")
        md.append("**Condition Groups**\n\n")
        md.append(json_block(groups) + "\n\n")

    write_jsonl(output_jsonl, output_rows)
    if output_lines_jsonl:
        write_jsonl(output_lines_jsonl, condition_line_rows)
    write_markdown(output_md, "".join(md))
    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run condition_logic_parser and write JSONL plus Markdown review.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    parser.add_argument(
        "--output-lines-jsonl",
        type=Path,
        help="Optional JSONL containing only collected condition lines as {'condition line': '...'} rows.",
    )
    args = parser.parse_args()
    run_condition_logic_parser(args.input, args.output_jsonl, args.output_md, args.output_lines_jsonl)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
