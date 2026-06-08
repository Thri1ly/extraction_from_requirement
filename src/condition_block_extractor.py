import re
from typing import List

from src.schemas import JsonDict


INVALID_CONDITION_LINES = {"NORMAL EXIT", "FAULT EXIT"}
LOGIC_MARKERS = {"AND", "OR"}
TRIGGER_PREFIXES = [
    "in case of",
    "during",
    "after",
    "when",
    "if",
]
LIST_HEADER_TRIGGERS = [
    "if/when",
    "when/if",
    "while",
    "when",
    "if",
]
LIST_HEADER_SCOPES = [
    "the following",
    "following",
    "below",
]
LIST_HEADER_OBJECTS = [
    "conditions",
    "condition",
]
LIST_HEADER_STATES = [
    "satisfied",
    "fulfilled",
    "fullfilled",
    "met",
]
CONDITION_HEADER_PREFIXES = [
    "under the following conditions",
    "under following conditions",
]


def _prefix_pattern(prefixes: List[str]) -> str:
    sorted_prefixes = sorted(prefixes, key=len, reverse=True)
    return "|".join(re.escape(prefix).replace(r"\ ", r"\s+") for prefix in sorted_prefixes)


BELOW_CONDITIONS_RE = re.compile(
    r"(?P<action>.*?)\s+(?P<trigger>if\s+below\s+(?P<logic>ALL|ANY)\s+conditions\s+are\s+met)\s*:\s*(?P<conditions>.+)",
    flags=re.IGNORECASE | re.DOTALL,
)

PROCESSED_HEADER_RE = re.compile(r"^(?P<trigger>(?:when|if)\b.*\b(?P<logic>ALL|ANY)\b.*?:?)$", flags=re.I)

CONDITION_LIST_HEADER_RE = re.compile(
    rf"^(?P<trigger>(?:{_prefix_pattern(LIST_HEADER_TRIGGERS)})\s+"
    rf"(?:{_prefix_pattern(LIST_HEADER_SCOPES)})\s+"
    rf"(?:{_prefix_pattern(LIST_HEADER_OBJECTS)})\s+"
    rf"(?:are|is)\s+"
    rf"(?:{_prefix_pattern(LIST_HEADER_STATES)}))\s*:?\s*$",
    flags=re.IGNORECASE,
)

NESTED_CONDITION_HEADER_RE = re.compile(
    r"^(?P<logic>ANY|ALL)\s+of\s+(?:below|the\s+following|following)\s+conditions?\s+(?:are|is)\s+(?:met|satisfied)\s*:?\s*$",
    flags=re.IGNORECASE,
)

TRIGGER_PREFIX_RE = re.compile(
    rf"^(?P<trigger>{_prefix_pattern(TRIGGER_PREFIXES)})\b\s*:?\s*(?P<condition>.*)$",
    flags=re.IGNORECASE,
)

CONDITION_HEADER_PREFIX_RE = re.compile(
    rf"^(?P<trigger>{_prefix_pattern(CONDITION_HEADER_PREFIXES)})\b\s*:?\s*$",
    flags=re.IGNORECASE,
)


def extract_condition_blocks(text: str) -> List[JsonDict]:
    """Extract condition blocks from processed condition text or a requirement text."""

    blocks: List[JsonDict] = []
    below_block = BELOW_CONDITIONS_RE.match(text.strip())
    if below_block:
        condition_lines, logic_markers, _skipped = parse_condition_rows(below_block.group("conditions"))
        blocks.append(
            {
                "block_id": "cond_block_1",
                "trigger": _normalize_spaces(below_block.group("trigger")),
                "logic_hint": below_block.group("logic").upper(),
                "action_text": _normalize_spaces(below_block.group("action")),
                "condition_text": "\n".join(condition_lines),
                "condition_lines": condition_lines,
                "logic_markers": logic_markers,
            }
        )
        return blocks

    if "\n" in text:
        processed = _extract_processed_condition_block(text)
        if processed:
            return [processed]

    inline = _extract_inline_when_if_block(text)
    if inline:
        return [inline]

    processed = _extract_processed_condition_block(text)
    if processed:
        return [processed]
    return []


def split_condition_lines(condition_text: str) -> List[str]:
    """Split a condition block into condition lines without block-level logic markers."""

    condition_lines, _logic_markers, _skipped_lines = parse_condition_rows(condition_text)
    return condition_lines


def parse_condition_rows(condition_text: str) -> tuple[List[str], List[str], List[JsonDict]]:
    """Split condition text into condition lines, block-level logic markers, and skipped rows."""

    lines: List[str] = []
    logic_markers: List[str] = []
    skipped_lines: List[JsonDict] = []
    for raw_line in condition_text.splitlines():
        line = raw_line.strip().strip("-* ")
        if not line:
            continue
        leading_marker, line = _split_leading_logic_marker(line)
        if leading_marker:
            logic_markers.append(leading_marker)
        if not line:
            continue
        _trigger, condition = _strip_single_line_trigger(line)
        invalid_marker = condition.upper()
        if invalid_marker in INVALID_CONDITION_LINES:
            skipped_lines.append({"line": condition, "reason": "invalid_condition_line"})
            continue
        lines.append(condition)
    return ([line for line in lines if line], logic_markers, skipped_lines)


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
    condition_lines, logic_markers, skipped_lines = parse_condition_rows(match.group("condition"))
    return {
        "block_id": "cond_block_1",
        "trigger": match.group("trigger").lower(),
        "logic_hint": None,
        "action_text": text[: match.start()].strip(),
        "condition_text": "\n".join(condition_lines),
        "condition_lines": condition_lines,
        "logic_markers": logic_markers,
        "skipped_lines": skipped_lines,
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
        lines, logic_markers, skipped = parse_condition_rows(condition)
        return _build_processed_block(trigger, "ALL", lines, logic_markers, skipped)

    first_line = raw_lines[0]
    header = _match_processed_header(first_line)
    if header:
        condition_source = "\n".join(raw_lines[1:])
        lines, logic_markers, skipped = parse_condition_rows(condition_source)
        logic_hint = header.get("logic_hint") or _first_logic_marker(logic_markers)
        return _build_processed_block(header["trigger"], logic_hint, lines, logic_markers, skipped)

    trigger, lines, logic_markers, skipped, nested_blocks = _parse_processed_condition_lines(raw_lines)
    return _build_processed_block(trigger, _first_logic_marker(logic_markers), lines, logic_markers, skipped, nested_blocks)


def _strip_single_line_trigger(line: str) -> tuple[str, str]:
    match = TRIGGER_PREFIX_RE.match(line)
    if not match:
        return "", line
    return (_normalize_spaces(match.group("trigger")).lower(), _clean_condition_fragment(match.group("condition")))


def _parse_processed_condition_lines(raw_lines: List[str]) -> tuple[str, List[str], List[str], List[JsonDict], List[JsonDict]]:
    trigger = ""
    lines: List[str] = []
    logic_markers: List[str] = []
    skipped_lines: List[JsonDict] = []
    nested_blocks: List[JsonDict] = []
    index = 0
    while index < len(raw_lines):
        raw_line = raw_lines[index]
        leading_marker, line = _split_leading_logic_marker(raw_line)
        if leading_marker:
            logic_markers.append(leading_marker)
        if not line:
            index += 1
            continue
        nested_header = _match_nested_condition_header(line)
        if nested_header:
            nested_source = "\n".join(raw_lines[index + 1 :])
            nested_lines, nested_logic_markers, nested_skipped = parse_condition_rows(nested_source)
            nested_blocks.append(
                {
                    "block_id": f"cond_block_1_nested_{len(nested_blocks) + 1}",
                    "trigger": line,
                    "logic_hint": nested_header["logic_hint"],
                    "condition_text": "\n".join(nested_lines),
                    "condition_lines": nested_lines,
                    "logic_markers": nested_logic_markers,
                    "skipped_lines": nested_skipped,
                }
            )
            break
        line_trigger, condition = _strip_single_line_trigger(line)
        if line_trigger and not trigger:
            trigger = line_trigger
        if not condition:
            index += 1
            continue
        invalid_marker = condition.upper()
        if invalid_marker in INVALID_CONDITION_LINES:
            skipped_lines.append({"line": condition, "reason": "invalid_condition_line"})
            index += 1
            continue
        lines.append(condition)
        index += 1
    return trigger, lines, logic_markers, skipped_lines, nested_blocks


def _split_leading_logic_marker(line: str) -> tuple[str | None, str]:
    match = re.match(r"^(?P<marker>AND|OR)\b\s*(?P<rest>.*)$", line.strip(), flags=re.IGNORECASE)
    if not match:
        return None, line
    return match.group("marker").upper(), match.group("rest").strip()


def _match_nested_condition_header(line: str) -> JsonDict | None:
    match = NESTED_CONDITION_HEADER_RE.match(line)
    if not match:
        return None
    return {"logic_hint": match.group("logic").upper()}


def _match_processed_header(line: str) -> JsonDict | None:
    logic_header = PROCESSED_HEADER_RE.match(line)
    if logic_header:
        return {"trigger": line, "logic_hint": logic_header.group("logic").upper()}
    list_header = CONDITION_LIST_HEADER_RE.match(line)
    if list_header:
        return {"trigger": line, "logic_hint": None}
    configured_header = CONDITION_HEADER_PREFIX_RE.match(line)
    if configured_header:
        return {"trigger": line, "logic_hint": None}
    return None


def _clean_condition_fragment(text: str) -> str:
    cleaned = text.strip().rstrip(",").strip()
    return "" if cleaned == ":" else cleaned


def _first_logic_marker(logic_markers: List[str]) -> str | None:
    return logic_markers[0] if logic_markers else None


def _build_processed_block(
    trigger: str,
    logic_hint: str | None,
    condition_lines: List[str],
    logic_markers: List[str],
    skipped_lines: List[JsonDict],
    nested_condition_blocks: List[JsonDict] | None = None,
) -> JsonDict:
    block = {
        "block_id": "cond_block_1",
        "trigger": trigger,
        "logic_hint": logic_hint,
        "action_text": "",
        "condition_text": "\n".join(line for line in condition_lines if line.upper() not in LOGIC_MARKERS),
        "condition_lines": condition_lines,
        "logic_markers": logic_markers,
        "skipped_lines": skipped_lines,
    }
    if nested_condition_blocks:
        block["nested_condition_blocks"] = nested_condition_blocks
    return block


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
