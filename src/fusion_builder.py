from copy import deepcopy
from typing import Callable, List

from src.action_parser import parse_actions
from src.condition_parser import parse_conditions
from src.coreference_resolver import resolve_coreferences
from src.embedding_text_builder import build_embedding_text
from src.normalizer import normalize_entities
from src.schemas import JsonDict


def _safe_layer(layer_name: str, func: Callable[[], object], issues: List[JsonDict]) -> object:
    """Run a parser layer and convert exceptions into review issues."""

    try:
        return func()
    except Exception as exc:  # pragma: no cover - defensive path
        issues.append({"layer": layer_name, "message": str(exc)})
        return []


def _raw_text(requirement: JsonDict) -> str:
    return str(requirement.get("raw_text") or requirement.get("text") or requirement.get("requirement") or "")


def build_enhanced_requirement(requirement: JsonDict) -> JsonDict:
    """Fuse raw fields and Layer3-6 outputs into one enhanced requirement."""

    base = deepcopy(requirement)
    issues: List[JsonDict] = []
    text = _raw_text(base)
    base["raw_text"] = text
    base.setdefault("requirement_id", base.get("id", ""))
    base.setdefault("function", "")
    base.setdefault("requirement_type", "")
    base.setdefault("component", "")
    base.setdefault("rule_entities", [])
    base.setdefault("ner_entities", [])

    normalized_entities = _safe_layer(
        "normalizer",
        lambda: normalize_entities(text, base.get("rule_entities"), base.get("ner_entities")),
        issues,
    )
    parsed_conditions = _safe_layer("condition_parser", lambda: parse_conditions(text, normalized_entities), issues)
    parsed_actions = _safe_layer("action_parser", lambda: parse_actions(text, normalized_entities), issues)
    coreference = _safe_layer(
        "coreference_resolver",
        lambda: resolve_coreferences(text, parsed_actions, normalized_entities),
        issues,
    )

    enhanced = {
        **base,
        "normalized_entities": normalized_entities,
        "parsed_conditions": parsed_conditions,
        "parsed_actions": parsed_actions,
        "coreference": coreference,
        "parse_issues": issues,
        "need_review": bool(
            issues
            or any(item.get("need_review") for item in parsed_conditions)
            or any(item.get("need_review") for item in parsed_actions)
            or (isinstance(coreference, dict) and coreference.get("need_review"))
        ),
    }
    enhanced["embedding_text"] = build_embedding_text(enhanced)
    return enhanced
