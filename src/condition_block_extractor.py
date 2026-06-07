import re
from typing import List

from src.schemas import JsonDict


INVALID_CONDITION_LINES = {"NORMAL EXIT", "FAULT EXIT"}
LOGIC_MARKERS = {"AND", "OR"}

BELOW_CONDITIONS_RE = re.compile(
    r"(?P<action>.*?)\s+(?P<trigger>if\s+below\s+(?P<logic>ALL|ANY)\s+conditions\s+are\s+met)\s*:\s*(?P<conditions>.+)",
    flags=re.IGNORECASE | re.DOTALL,
)

PROCESSED_HEADER_RE = re.compile(
    r"^(?P<trigger>(?:when|if)\s+(?P<logic>ALL|ANY)\b.*?:?)$",
    flags=re.IGNORECASE,
)

TRIGGER_PREFIX_RE = re.compile(
    r"^(?P<trigger>when|if|in\s+case\s+of)\b\s*(?P<condition>.*)$",
    flags=re.IGNORECASE,
)


def extract_condition_blocks(text: str) -> List[JsonDict]:
    """Extract condition blocks from processed condition text or a requirement text."""

    blocks: List[JsonDict] = []
    below_block = BELOW_CONDITIONS_RE.match(text.strip())
    if below_block:
        condition_lines, _skipped = filter_condition_lines(split_condition_lines(below_block.group("conditions")))
        blocks.append(
            {
                "block_id": "cond_block_1",
                "trigger": _normalize_spaces(below_block.group("trigger")),
                "logic_hint": below_block.group("logic").upper(),
                "action_text": _normalize_spaces(below_block.group("action")),
                "condition_text": "\n".join(condition_lines),
                "condition_lines": [line for line in condition_lines if line not in LOGIC_MARKERS],
            }
        )
        return blocks

    inline = _extract_inline_when_if_block(text)
    if inline:
        return [inline]

    processed = _extract_processed_condition_block(text)
    if processed:
        return [processed]
    return []


def split_condition_lines(condition_text: str) -> List[str]:
    """Split a condition block into condition lines while keeping logic markers."""

    lines: List[str] = []
    for raw_line in condition_text.splitlines():
        line = raw_line.strip().strip("-* ")
        if not line:
            continue
        if line.upper() in LOGIC_MARKERS:
            lines.append(line.upper())
            continue
        lines.extend(_split_inline_logic_markers(line))
    return [line for line in lines if line]


def filter_condition_lines(lines: List[str]) -> tuple[List[str], List[JsonDict]]:
    """Filter invalid condition rows and return skipped row metadata."""

    valid_lines: List[str] = []
    skipped_lines: List[JsonDict] = []
    for line in lines:
        marker = line.upper()
        if marker in INVALID_CONDITION_LINES:
            skipped_lines.append({"line": line, "reason": "invalid_condition_line"})
            continue
        valid_lines.append(line)
    return valid_lines, skipped_lines


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


def _extract_processed_condition_block(text: str) -> JsonDict | None:
    cleaned = text.strip()
    if not cleaned:
        return None

    raw_lines = [line.strip().strip("-* ") for line in cleaned.splitlines() if line.strip()]
    if not raw_lines:
        return None

    if len(raw_lines) == 1:
        trigger, condition = _strip_single_line_trigger(raw_lines[0])
        lines, skipped = filter_condition_lines(split_condition_lines(condition))
        return _build_processed_block(trigger, "ALL", lines, skipped)

    first_line = raw_lines[0]
    header = PROCESSED_HEADER_RE.match(first_line)
    if header:
        condition_source = "\n".join(raw_lines[1:])
        lines, skipped = filter_condition_lines(split_condition_lines(condition_source))
        return _build_processed_block(first_line, header.group("logic").upper(), lines, skipped)

    lines, skipped = filter_condition_lines(split_condition_lines("\n".join(raw_lines)))
    return _build_processed_block("", None, lines, skipped)


def _strip_single_line_trigger(line: str) -> tuple[str, str]:
    match = TRIGGER_PREFIX_RE.match(line)
    if not match:
        return "", line
    return (_normalize_spaces(match.group("trigger")).lower(), match.group("condition").strip())


def _build_processed_block(
    trigger: str,
    logic_hint: str | None,
    condition_lines: List[str],
    skipped_lines: List[JsonDict],
) -> JsonDict:
    return {
        "block_id": "cond_block_1",
        "trigger": trigger,
        "logic_hint": logic_hint,
        "action_text": "",
        "condition_text": "\n".join(line for line in condition_lines if line.upper() not in LOGIC_MARKERS),
        "condition_lines": condition_lines,
        "skipped_lines": skipped_lines,
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
