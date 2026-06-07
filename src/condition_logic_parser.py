from typing import List

from src.schemas import JsonDict


LOGIC_MARKERS = {"AND", "OR"}


def parse_condition_logic(block: JsonDict) -> JsonDict:
    """Build a shallow condition group from condition lines and logic markers."""

    lines = list(block.get("condition_lines", []))
    logic_markers = list(block.get("logic_markers", []))
    marker_logic = _first_logic_marker(logic_markers) or _first_logic_marker(lines)
    logic = str(block.get("logic_hint") or marker_logic or "ALL").upper()
    children = [
        {"type": "condition_line", "text": line}
        for line in lines
        if str(line).upper() not in LOGIC_MARKERS
    ]
    return {
        "type": "condition_group",
        "block_id": block.get("block_id"),
        "logic": logic,
        "trigger": block.get("trigger"),
        "children": children,
        "need_review": False,
    }


def _first_logic_marker(lines: List[str]) -> str | None:
    for line in lines:
        marker = str(line).upper()
        if marker in LOGIC_MARKERS:
            return marker
    return None
