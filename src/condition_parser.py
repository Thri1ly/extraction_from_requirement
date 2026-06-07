from typing import List

from src.atomic_condition_parser import (
    parse_atomic_conditions,
    parse_condition_line,
    parse_fault_state_conditions,
    parse_range_conditions,
    parse_redundant_signal_validity,
    parse_state_definition_conditions,
    parse_threshold_conditions,
)
from src.condition_block_extractor import extract_condition_blocks
from src.condition_logic_parser import parse_condition_logic
from src.dependency_parser import parse_dependencies, parse_trend_dependencies
from src.schemas import JsonDict, unique_dicts


def parse_conditions(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse Layer4 condition objects from requirement text."""

    conditions: List[JsonDict] = []
    condition_groups = parse_condition_groups(text, normalized_entities)
    conditions.extend(condition_groups)
    conditions.extend(flatten_condition_groups(condition_groups))
    conditions.extend(parse_atomic_conditions(text, normalized_entities))
    conditions.extend(parse_dependencies(text, normalized_entities))
    conditions = unique_dicts(conditions)
    if not conditions:
        return [{"type": "unparsed_condition", "mention": text, "need_review": True}]
    return conditions


def parse_condition_groups(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Extract condition blocks and parse them into condition groups."""

    groups: List[JsonDict] = []
    for block in extract_condition_blocks(text):
        group = parse_condition_logic(block)
        group["children"] = [
            parse_condition_line(child["text"], normalized_entities)
            if child.get("type") == "condition_line"
            else child
            for child in group.get("children", [])
        ]
        groups.append(group)
    return groups


def flatten_condition_groups(groups: List[JsonDict]) -> List[JsonDict]:
    """Return atomic children from condition groups for backward compatibility."""

    flattened: List[JsonDict] = []
    for group in groups:
        for child in group.get("children", []):
            if child.get("type") == "condition_group":
                flattened.extend(flatten_condition_groups([child]))
            elif child.get("type") != "unparsed_condition":
                flattened.append(child)
    return flattened
