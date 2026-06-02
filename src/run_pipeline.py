import json
import sys
from pathlib import Path
from typing import Iterable

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.fusion_builder import build_enhanced_requirement
from src.schemas import JsonDict


ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = ROOT / "data" / "sample_complex_requirements.jsonl"
OUTPUT_PATH = ROOT / "data" / "enhanced_requirements.jsonl"


def read_jsonl(path: Path) -> Iterable[JsonDict]:
    """Read JSONL records, skipping blank lines."""

    with path.open("r", encoding="utf-8") as file:
        for line in file:
            line = line.strip()
            if not line:
                continue
            yield json.loads(line)


def write_jsonl(path: Path, rows: Iterable[JsonDict]) -> None:
    """Write JSONL records with non-ASCII characters preserved."""

    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def run_pipeline(input_path: Path = INPUT_PATH, output_path: Path = OUTPUT_PATH) -> list[JsonDict]:
    """Run the complete enhanced requirement pipeline."""

    enhanced_rows = [build_enhanced_requirement(row) for row in read_jsonl(input_path)]
    write_jsonl(output_path, enhanced_rows)

    for row in enhanced_rows:
        print(f"Requirement: {row.get('requirement_id')}")
        print("parsed_conditions:")
        print(json.dumps(row.get("parsed_conditions", []), ensure_ascii=False, indent=2))
        print("parsed_actions:")
        print(json.dumps(row.get("parsed_actions", []), ensure_ascii=False, indent=2))
        print("embedding_text:")
        print(row.get("embedding_text", ""))
        print()

    return enhanced_rows


if __name__ == "__main__":
    run_pipeline()
