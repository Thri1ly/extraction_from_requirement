import argparse
import sys
from pathlib import Path
from typing import List

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.condition_review_utils import base_row, condition_text, json_block, read_jsonl, row_id, text_block, write_jsonl, write_markdown
from src.parser.condition_block_extractor import extract_condition_blocks
from src.schemas import JsonDict


def run_condition_block_extractor(input_jsonl: Path, output_jsonl: Path, output_md: Path) -> List[JsonDict]:
    """Run condition_block_extractor over requirement rows and save JSONL plus Markdown review."""

    output_rows: List[JsonDict] = []
    md = ["# Condition Block Extractor Review\n\n"]
    for index, row in enumerate(read_jsonl(input_jsonl), 1):
        source_text = condition_text(row)
        blocks = extract_condition_blocks(source_text)
        output_row = {
            **base_row(row),
            "raw_conditions": source_text,
            "condition_blocks": blocks,
        }
        output_rows.append(output_row)

        md.append(f"## {index}. {row_id(row)}\n\n")
        md.append("**Raw Conditions**\n\n")
        md.append(text_block(source_text) + "\n\n")
        md.append("**Condition Blocks**\n\n")
        md.append(json_block(blocks) + "\n\n")

    write_jsonl(output_jsonl, output_rows)
    write_markdown(output_md, "".join(md))
    return output_rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Run condition_block_extractor and write JSONL plus Markdown review.")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-jsonl", required=True, type=Path)
    parser.add_argument("--output-md", required=True, type=Path)
    args = parser.parse_args()
    run_condition_block_extractor(args.input, args.output_jsonl, args.output_md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
