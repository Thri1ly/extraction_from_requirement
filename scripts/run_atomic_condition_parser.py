import argparse
import sys
from pathlib import Path
from typing import List

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import base_row, collect_condition_line_texts, json_block, read_jsonl, row_id, write_jsonl, write_markdown
from src.parser.atomic_condition_parser import parse_condition_line
from src.schemas import JsonDict


def run_atomic_condition_parser(input_jsonl: Path, output_jsonl: Path, output_md: Path) -> List[JsonDict]:
    """Parse condition lines from prior stage outputs into atomic conditions."""

    output_rows: List[JsonDict] = []
    md = ["# Atomic Condition Parser Review\n\n"]
    for index, row in enumerate(read_jsonl(input_jsonl), 1):
        atomic_conditions = []
        for line_number, line in enumerate(collect_condition_line_texts(row), 1):
            atomic_conditions.append(
                {
                    "line_no": line_number,
                    "condition_line": line,
                    "parsed": parse_condition_line(line),
                }
            )
        output_row = {
            **base_row(row),
            "raw_conditions": row.get("raw_conditions", ""),
            "atomic_conditions": atomic_conditions,
        }
        output_rows.append(output_row)

        md.append(f"## {index}. {row_id(row)}\n\n")
        md.append("**Atomic Conditions**\n\n")
        md.append(json_block(atomic_conditions) + "\n\n")

    write_jsonl(output_jsonl, output_rows)
    write_markdown(output_md, "".join(md))
    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run atomic_condition_parser over extracted condition lines.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    run_atomic_condition_parser(args.input, args.output_jsonl, args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
