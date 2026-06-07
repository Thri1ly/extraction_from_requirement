import re
from typing import List

from src.schemas import JsonDict


BELOW_CONDITIONS_RE = re.compile(
    r"(?P<action>.*?)\s+(?P<trigger>if\s+below\s+(?P<logic>ALL|ANY)\s+conditions\s+are\s+met)\s*:\s*(?P<conditions>.+)",
    flags=re.IGNORECASE | re.DOTALL,
)


def extract_condition_blocks(text: str) -> List[JsonDict]:
    """Extract condition blocks from a requirement text."""

    blocks: List[JsonDict] = []
    below_block = BELOW_CONDITIONS_RE.match(text.strip())
    if below_block:
        blocks.append(
            {
                "block_id": "cond_block_1",
                "trigger": _normalize_spaces(below_block.group("trigger")),
                "logic_hint": below_block.group("logic").upper(),
                "action_text": _normalize_spaces(below_block.group("action")),
                "condition_text": _strip_condition_text(below_block.group("conditions")),
                "condition_lines": [
                    line for line in split_condition_lines(below_block.group("conditions")) if line not in {"AND", "OR"}
                ],
            }
        )
        return blocks

    inline = _extract_inline_when_if_block(text)
    if inline:
        return [inline]
    return []


def split_condition_lines(condition_text: str) -> List[str]:
    """Split a condition block into condition lines while keeping logic markers."""

    lines: List[str] = []
    for raw_line in condition_text.splitlines():
        line = raw_line.strip().strip("-* ")
        if not line:
            continue
        if line.upper() in {"AND", "OR"}:
            lines.append(line.upper())
            continue
        lines.extend(_split_inline_logic_markers(line))
    return [line for line in lines if line]


def _extract_inline_when_if_block(text: str) -> JsonDict | None:
    match = re.search(r"\b(?P<trigger>when|if)\b\s+(?P<condition>.+?)(?:,\s*|\s+EPS\s+shall\s+|\s+shall\s+)", text, re.I)
    if not match:
        return None
    return {
        "block_id": "cond_block_1",
        "trigger": match.group("trigger").lower(),
        "logic_hint": None,
        "action_text": text[: match.start()].strip(),
        "condition_text": match.group("condition").strip(),
        "condition_lines": split_condition_lines(match.group("condition")),
    }


def _split_inline_logic_markers(line: str) -> List[str]:
    parts = re.split(r"\s+\b(AND|OR)\b\s+", line, flags=re.IGNORECASE)
    result: List[str] = []
    for part in parts:
        cleaned = part.strip()
        if not cleaned:
            continue
        result.append(cleaned.upper() if cleaned.upper() in {"AND", "OR"} else cleaned)
    return result


def _strip_condition_text(text: str) -> str:
    return "\n".join(split_condition_lines(text))


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())
