import json
from pathlib import Path
from typing import Iterable, List

from src.schemas import JsonDict


ID_KEYS = ["requirement_id", "chunk_id", "feature_id", "id"]
CONDITION_TEXT_KEYS = ["conditions", "condition", "raw_conditions", "text", "raw_text"]


def read_jsonl(path: Path) -> List[JsonDict]:
    """Read JSONL rows with UTF-8 BOM tolerance."""

    with path.open("r", encoding="utf-8-sig") as file:
        return [json.loads(line) for line in file if line.strip()]


def write_jsonl(path: Path, rows: Iterable[JsonDict]) -> None:
    """Write rows as JSONL with non-ASCII text preserved."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_markdown(path: Path, content: str) -> None:
    """Write a Markdown review file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def row_id(row: JsonDict) -> str:
    """Return a stable row identifier for review output."""

    for key in ID_KEYS:
        if row.get(key):
            return str(row[key])
    return "UNKNOWN_ID"


def condition_text(row: JsonDict) -> str:
    """Return the source condition text from a requirement-like row."""

    for key in CONDITION_TEXT_KEYS:
        if row.get(key):
            return str(row[key])
    return ""


def base_row(row: JsonDict) -> JsonDict:
    """Copy identifying fields into a stage output row."""

    return {key: row[key] for key in ID_KEYS if key in row}


def json_block(value: object) -> str:
    """Format a value as a fenced JSON code block."""

    return "```json\n" + json.dumps(value, ensure_ascii=False, indent=2) + "\n```"


def text_block(value: str) -> str:
    """Format text as a fenced text code block."""

    return f"```text\n{value or ''}\n```"


def numbered_list(items: List[str]) -> str:
    """Format a Markdown numbered list."""

    if not items:
        return "- None\n"
    return "".join(f"{index}. {item}\n" for index, item in enumerate(items, 1))


def collect_condition_line_texts_from_group(group: JsonDict) -> List[str]:
    """Collect condition_line texts recursively from a condition group."""

    lines: List[str] = []
    for child in group.get("children", []):
        if child.get("type") == "condition_line":
            lines.append(str(child.get("text", "")))
        elif child.get("type") == "condition_group":
            lines.extend(collect_condition_line_texts_from_group(child))
    return lines


def collect_condition_line_texts(row: JsonDict) -> List[str]:
    """Collect condition lines from known stage output shapes."""

    lines: List[str] = []
    for block in row.get("condition_blocks", []):
        lines.extend(str(line) for line in block.get("condition_lines", []))
        for nested in block.get("nested_condition_blocks", []):
            lines.extend(str(line) for line in nested.get("condition_lines", []))
    for group in row.get("condition_groups", []):
        lines.extend(collect_condition_line_texts_from_group(group))
    if row.get("condition_line"):
        lines.append(str(row["condition_line"]))
    if row.get("condition_lines"):
        lines.extend(str(line) for line in row["condition_lines"])
    return lines
