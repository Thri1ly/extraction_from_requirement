import json
from typing import List

from src.schemas import JsonDict


SECTION_ORDER = [
    "Requirement ID",
    "Function",
    "Requirement Type",
    "Component",
    "Conditions",
    "Actions",
    "Entities",
    "Coreference",
    "Original Requirement",
]


def _json_line(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def build_embedding_text(requirement: JsonDict) -> str:
    """Build stable embedding text from an enhanced requirement dictionary."""

    lines: List[str] = [
        f"Requirement ID: {requirement.get('requirement_id', '')}",
        f"Function: {requirement.get('function', '')}",
        f"Requirement Type: {requirement.get('requirement_type', '')}",
        f"Component: {requirement.get('component', '')}",
        "Conditions:",
    ]
    lines.extend(_json_line(condition) for condition in requirement.get("parsed_conditions", []))
    lines.append("Actions:")
    lines.extend(_json_line(action) for action in requirement.get("parsed_actions", []))
    lines.append("Entities:")
    lines.extend(_json_line(entity) for entity in requirement.get("normalized_entities", []))
    lines.append("Coreference:")
    lines.append(_json_line(requirement.get("coreference", {})))
    lines.append(f"Original Requirement: {requirement.get('raw_text', '')}")
    return "\n".join(lines)
