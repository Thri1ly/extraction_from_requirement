import re
from typing import Callable, List

from src.parser.atomic_condition_parser import (
    COMPOUND_OPERATOR_PATTERNS,
    OPERATOR_ALIASES,
    VALUE_ALIASES,
    VALUE_UNIT_PATTERN,
    parse_atomic_conditions as legacy_parse_atomic_conditions,
    parse_condition_line as legacy_parse_condition_line,
)
from src.schemas import JsonDict, number_value


SUPPORTED_ENTITY_TYPES = {"SIGNAL", "STATE", "VALUE", "PARAMETER", "COMPONENT", "FAULT"}
RELATION_PATTERN = re.compile(
    r"\b(?:is|are|be|shall\s+be|should\s+be|must\s+be|become|becomes|remain|remains)\b",
    flags=re.IGNORECASE,
)
SYNTACTIC_COMPOUND_OPERATOR_PATTERNS = [
    (r"\bequals?\s+(?:to\s+)?(?:or|and|and/or|and\s*/\s*or)?\s*greater\s+than\b", ">="),
    (r"\bequals?\s+(?:to\s+)?(?:or|and|and/or|and\s*/\s*or)?\s*less\s+than\b", "<="),
]


def parse_atomic_conditions(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse atomic conditions with entity placeholder syntax before legacy fallback."""

    normalized_entities = normalized_entities or []
    syntactic_conditions = parse_syntactic_atomic_conditions(text, normalized_entities)
    if syntactic_conditions:
        return syntactic_conditions
    return legacy_parse_atomic_conditions(text, normalized_entities)


def parse_condition_line(text: str, normalized_entities: List[JsonDict] | None = None) -> JsonDict:
    """Parse one condition line with syntactic relation extraction and legacy fallback."""

    parsed = parse_syntactic_atomic_conditions(text, normalized_entities or [])
    if parsed:
        return parsed[0]
    return legacy_parse_condition_line(text, normalized_entities)


def parse_syntactic_atomic_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Extract simple subject-predicate relations from placeholderized entity syntax."""

    if not normalized_entities:
        return []

    analysis = build_syntax_analysis(text, normalized_entities)
    placeholder_text = str(analysis["placeholder_text"])
    placeholder_map = analysis["placeholder_map"]
    signals = _placeholders_by_type(placeholder_map, "SIGNAL")
    components = _placeholders_by_type(placeholder_map, "COMPONENT")
    faults = _placeholders_by_type(placeholder_map, "FAULT")
    right_entities = _right_relation_entities(placeholder_map)

    conditions: List[JsonDict] = []
    conditions.extend(_parse_fault_in_component_condition(text, placeholder_text, faults, components, placeholder_map))
    conditions.extend(_parse_quantified_component_member_state(text, placeholder_text, components, right_entities, placeholder_map))
    conditions.extend(_parse_component_state_condition(text, placeholder_text, components, right_entities, placeholder_map))
    conditions.extend(_parse_parenthesized_signal_state_with_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_explicit_parenthesized_condition(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_bracketed_range_condition(text, placeholder_text, signals, placeholder_map))
    conditions.extend(_parse_signal_value_state_clause_group(text, placeholder_text, signals, placeholder_map))
    conditions.extend(_parse_quantified_signal_member_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_parenthesized_signal_state_without_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_state_without_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_multi_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_multi_signal_single_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_single_right(text, placeholder_text, signals, right_entities, placeholder_map))
    return conditions


def _parse_fault_in_component_condition(
    original_text: str,
    placeholder_text: str,
    faults: List[str],
    components: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(faults) != 1 or len(components) != 1:
        return []

    match = re.search(
        rf"\b{re.escape(faults[0])}\s+in\s+{re.escape(components[0])}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    fault = placeholder_map[faults[0]]["entity"]
    component = placeholder_map[components[0]]["entity"]
    return [
        {
            "type": "fault_component_condition",
            "mention": original_text,
            "fault": str(fault.get("canonical_name") or fault.get("mention")),
            "component": str(component.get("canonical_name") or component.get("mention")),
            "relation": "in",
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_quantified_component_member_state(
    original_text: str,
    placeholder_text: str,
    components: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(components) != 1 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []

    component_placeholder = components[0]
    match = re.search(
        rf"\b(?P<quantifier>(?:(?:at\s*least|atleast)\s+)?one\s+of|both(?:\s+of)?|all(?:\s+of)?)\s+"
        rf"(?:the\s+)?{re.escape(component_placeholder)}\s+"
        rf"{RELATION_PATTERN.pattern}(?:\s+in)?\s+{re.escape(state_placeholder)}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    quantifier, logic = _quantified_signal_logic(match.group("quantifier"))
    component = placeholder_map[component_placeholder]["entity"]
    source_component = str(component.get("canonical_name") or component.get("mention"))
    members = [str(member) for member in component.get("members", []) if str(member).strip()]
    state = placeholder_map[state_placeholder]["entity"]
    if not members:
        return [
            {
                "type": "condition_group",
                "logic": logic,
                "quantifier": quantifier,
                "mention": original_text,
                "source_component": source_component,
                "children": [],
                "parser": "syntactic",
                "need_review": True,
                "review_reason": "quantified component has no members to expand",
            }
        ]

    children = [
        _condition_for_component_state(
            original_text,
            {"mention": member, "type": "COMPONENT", "canonical_name": member},
            state,
        )
        for member in members
    ]
    if any(child is None for child in children):
        return []

    return [
        {
            "type": "condition_group",
            "logic": logic,
            "quantifier": quantifier,
            "mention": original_text,
            "source_component": source_component,
            "children": children,
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_component_state_condition(
    original_text: str,
    placeholder_text: str,
    components: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(components) != 1 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []

    component_placeholder = components[0]
    if not _has_component_state_relation_between(placeholder_text, component_placeholder, state_placeholder):
        return []

    condition = _condition_for_component_state(
        original_text,
        placeholder_map[component_placeholder]["entity"],
        placeholder_map[state_placeholder]["entity"],
    )
    if not condition:
        return []
    condition["parser"] = "syntactic"
    return [condition]


def _parse_parenthesized_signal_state_with_predicate(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 2 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []

    match = re.search(
        rf"\b(?P<outer>SIGNAL_\d+)\s*\(\s*(?P<inner>SIGNAL_\d+)\s*\)\s+"
        rf"{RELATION_PATTERN.pattern}\s+{re.escape(state_placeholder)}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    inner_signal = match.group("inner")
    outer_signal = match.group("outer")
    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[inner_signal]["entity"],
        placeholder_map[state_placeholder]["entity"],
        operator=_operator_for_right_placeholder(placeholder_text, inner_signal, [state_placeholder], state_placeholder),
    )
    if not condition:
        return []

    condition["parser"] = "syntactic"
    condition["confidence"] = {
        "overall": 0.93,
        "structure": 0.93,
        "normalization": 0.95,
    }
    condition["need_review"] = False
    if not _same_canonical_entity(placeholder_map[outer_signal]["entity"], placeholder_map[inner_signal]["entity"]):
        condition["need_review"] = True
        condition["review_reason"] = "parenthesized signal canonical differs from leading signal"
        condition["confidence"]["overall"] = 0.72
        condition["confidence"]["normalization"] = 0.72
    return [condition]


def build_syntax_analysis(text: str, normalized_entities: List[JsonDict]) -> JsonDict:
    """Replace known entities with placeholders and attach optional local spaCy syntax info."""

    placeholder_text, placeholder_map = _placeholderize_entities(text, normalized_entities)
    return {
        "placeholder_text": placeholder_text,
        "placeholder_map": placeholder_map,
        "syntax_engine": _available_syntax_engine(),
        "syntax_tokens": _spacy_tokens(placeholder_text),
    }


def _parse_explicit_parenthesized_condition(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    """Prefer a clear parenthesized signal relation when the outer phrase repeats it."""

    if len(signals) < 2 or len(right_entities) < 2:
        return []

    for match in re.finditer(r"\((?P<body>[^()]*)\)", placeholder_text):
        body = match.group("body")
        body_signals = [signal for signal in signals if signal in body]
        body_rights = [right for right in right_entities if right in body]
        if len(body_signals) != 1 or len(body_rights) != 1:
            continue

        body_signal = body_signals[0]
        body_right = body_rights[0]
        if not _has_relation_between(body, body_signal, body_right):
            continue

        outer_text = placeholder_text[: match.start()]
        outer_signals = [signal for signal in signals if signal in outer_text]
        outer_rights = [right for right in right_entities if right in outer_text]
        if len(outer_signals) != 1 or len(outer_rights) != 1:
            continue
        if not _same_canonical_entity(placeholder_map[outer_signals[0]]["entity"], placeholder_map[body_signal]["entity"]):
            continue
        if not _same_canonical_entity(placeholder_map[outer_rights[0]]["entity"], placeholder_map[body_right]["entity"]):
            continue

        condition = _condition_for_right_entity(
            original_text,
            placeholder_map[body_signal]["entity"],
            placeholder_map[body_right]["entity"],
            operator=_operator_for_right_placeholder(body, body_signal, [body_right], body_right),
        )
        if not condition:
            continue
        condition["parser"] = "syntactic"
        condition["confidence"] = {
            "overall": 0.95,
            "structure": 0.95,
            "normalization": 0.95,
        }
        condition["need_review"] = False
        return [condition]

    return []


def _parse_bracketed_range_condition(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1:
        return []

    signal = signals[0]
    left_entities = [
        placeholder
        for placeholder, payload in placeholder_map.items()
        if str(payload["entity"].get("type", "")).upper() in {"VALUE", "PARAMETER"}
        and placeholder_text.find(placeholder) < placeholder_text.find(signal)
    ]
    right_entities = [
        placeholder
        for placeholder, payload in placeholder_map.items()
        if str(payload["entity"].get("type", "")).upper() in {"VALUE", "PARAMETER"}
        and placeholder_text.find(placeholder) > placeholder_text.find(signal)
    ]
    if len(left_entities) != 1 or len(right_entities) != 1:
        return []

    left = left_entities[0]
    right = right_entities[0]
    pattern = re.compile(
        rf"\b{re.escape(left)}\s*(?P<left_op><=|<|>=|>)\s*{re.escape(signal)}\s*"
        rf"(?P<right_op><=|<|>=|>)\s*{re.escape(right)}\b",
        flags=re.IGNORECASE,
    )
    match = pattern.search(placeholder_text)
    if not match:
        return []
    bounds = _range_bounds(left, match.group("left_op"), right, match.group("right_op"))
    if not bounds:
        return []

    condition: JsonDict = {
        "type": "range_condition",
        "mention": original_text,
        "signal": str(placeholder_map[signal]["entity"].get("canonical_name") or placeholder_map[signal]["entity"].get("mention")),
        "lower_operator": bounds["lower_operator"],
        "upper_operator": bounds["upper_operator"],
        "parser": "syntactic",
        "need_review": False,
    }
    _assign_range_bound(condition, "lower", placeholder_map[bounds["lower"]]["entity"])
    _assign_range_bound(condition, "upper", placeholder_map[bounds["upper"]]["entity"])
    return [condition]


def _range_bounds(left: str, left_operator: str, right: str, right_operator: str) -> JsonDict | None:
    if left_operator in {"<", "<="} and right_operator in {"<", "<="}:
        return {
            "lower": left,
            "lower_operator": ">=" if left_operator == "<=" else ">",
            "upper": right,
            "upper_operator": "<=" if right_operator == "<=" else "<",
        }
    if left_operator in {">", ">="} and right_operator in {">", ">="}:
        return {
            "lower": right,
            "lower_operator": ">=" if right_operator == ">=" else ">",
            "upper": left,
            "upper_operator": "<=" if left_operator == ">=" else "<",
        }
    return None


def _assign_range_bound(condition: JsonDict, prefix: str, entity: JsonDict) -> None:
    entity_type = str(entity.get("type", "")).upper()
    if entity_type == "PARAMETER":
        condition[f"{prefix}_parameter"] = str(entity.get("canonical_name") or entity.get("mention"))
        return

    parsed_value = _value_from_entity(entity)
    if parsed_value is None:
        condition[f"{prefix}_value"] = str(entity.get("canonical_name") or entity.get("mention"))
        condition["need_review"] = True
        condition["review_reason"] = "range bound value was not parsed"
        return
    condition[f"{prefix}_value"] = parsed_value["value"]
    if parsed_value.get("unit"):
        condition[f"{prefix}_unit"] = parsed_value["unit"]


def _parse_signal_value_state_clause_group(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if not signals:
        return []

    ordered_signals = _ordered_placeholders(placeholder_text, signals)
    clauses = _signal_value_state_clauses(placeholder_text, ordered_signals, placeholder_map)
    if len(clauses) != len(ordered_signals) or not clauses:
        return []

    clause_groups = [
        _value_state_clause_group(original_text, placeholder_text, clause, placeholder_map)
        for clause in clauses
    ]
    if any(group is None for group in clause_groups):
        return []

    if len(clause_groups) == 1:
        group = clause_groups[0]
        group["parser"] = "syntactic"
        return [group]

    logic = _clause_group_logic(placeholder_text, clauses)
    if not logic:
        return []

    return [
        {
            "type": "condition_group",
            "logic": logic,
            "mention": original_text,
            "children": clause_groups,
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _signal_value_state_clauses(
    placeholder_text: str,
    ordered_signals: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    clauses: List[JsonDict] = []
    values = _placeholders_by_type(placeholder_map, "VALUE")
    states = _placeholders_by_type(placeholder_map, "STATE")
    for index, signal in enumerate(ordered_signals):
        start = placeholder_text.find(signal)
        end = placeholder_text.find(ordered_signals[index + 1]) if index + 1 < len(ordered_signals) else len(placeholder_text)
        if start < 0 or end <= start:
            return []
        clause_text = placeholder_text[start:end]
        clause_values = [value for value in values if clause_text.find(value) >= 0]
        clause_states = [state for state in states if clause_text.find(state) >= 0]
        if len(clause_values) != 1 or len(clause_states) != 1:
            return []
        value = clause_values[0]
        state = clause_states[0]
        value_end = clause_text.find(value) + len(value)
        state_start = clause_text.find(state)
        if state_start <= value_end or ":" not in clause_text[value_end:state_start]:
            return []
        if not _has_relation_between(placeholder_text, signal, value):
            return []
        clauses.append(
            {
                "signal": signal,
                "value": value,
                "state": state,
                "start": start,
                "end": end,
                "state_end": start + state_start + len(state),
            }
        )
    return clauses


def _value_state_clause_group(
    original_text: str,
    placeholder_text: str,
    clause: JsonDict,
    placeholder_map: JsonDict,
) -> JsonDict | None:
    signal = placeholder_map[clause["signal"]]["entity"]
    value = placeholder_map[clause["value"]]["entity"]
    state = placeholder_map[clause["state"]]["entity"]
    operator = _operator_for_right_placeholder(placeholder_text, clause["signal"], [clause["value"]], clause["value"])
    value_condition = _condition_for_right_entity(original_text, signal, value, operator=operator)
    state_condition = _condition_for_right_entity(original_text, signal, state, operator=operator)
    if not value_condition or not state_condition:
        return None

    signal_mention = _display_entity_mention(original_text, signal)
    parsed_value = _value_from_entity(value)
    if parsed_value is None:
        return None
    state_name = str(state.get("canonical_name") or state.get("mention"))
    return {
        "type": "condition_group",
        "logic": "AND",
        "mention": f"{signal_mention} {operator} {parsed_value['value']}:{state_name}",
        "children": [value_condition, state_condition],
        "need_review": False,
    }


def _parse_quantified_signal_member_right(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1 or len(right_entities) != 1:
        return []

    signal_placeholder = signals[0]
    right_placeholder = right_entities[0]
    match = re.search(
        rf"\b(?P<quantifier>(?:(?:at\s*least|atleast)\s+)?one\s+of|both(?:\s+of)?|all(?:\s+of)?)\s+"
        rf"(?:the\s+)?{re.escape(signal_placeholder)}\s+"
        rf"{RELATION_PATTERN.pattern}\s+{re.escape(right_placeholder)}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    quantifier, logic = _quantified_signal_logic(match.group("quantifier"))
    signal = placeholder_map[signal_placeholder]["entity"]
    source_signal = str(signal.get("canonical_name") or signal.get("mention"))
    members = [str(member) for member in signal.get("members", []) if str(member).strip()]
    operator = _operator_for_right_placeholder(placeholder_text, signal_placeholder, right_entities, right_placeholder)
    right_entity = placeholder_map[right_placeholder]["entity"]
    if not members:
        return [
            {
                "type": "condition_group",
                "logic": logic,
                "quantifier": quantifier,
                "mention": original_text,
                "source_signal": source_signal,
                "children": [],
                "parser": "syntactic",
                "need_review": True,
                "review_reason": "quantified signal has no members to expand",
            }
        ]

    children = [
        _condition_for_right_entity(
            original_text,
            {"mention": member, "type": "SIGNAL", "canonical_name": member},
            right_entity,
            operator=operator,
        )
        for member in members
    ]
    if any(child is None for child in children):
        return []

    return [
        {
            "type": "condition_group",
            "logic": logic,
            "quantifier": quantifier,
            "mention": original_text,
            "source_signal": source_signal,
            "children": children,
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_parenthesized_signal_state_without_predicate(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 2 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []

    match = re.search(
        rf"\b(?P<outer>SIGNAL_\d+)\s*\(\s*(?P<inner>SIGNAL_\d+)\s*\)\s+{re.escape(state_placeholder)}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    inner_signal = match.group("inner")
    outer_signal = match.group("outer")
    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[inner_signal]["entity"],
        placeholder_map[state_placeholder]["entity"],
        operator="==",
    )
    if not condition:
        return []

    condition["parser"] = "syntactic"
    condition["confidence"] = {
        "overall": 0.9,
        "structure": 0.9,
        "normalization": 0.95,
    }
    condition["need_review"] = False
    if not _same_canonical_entity(placeholder_map[outer_signal]["entity"], placeholder_map[inner_signal]["entity"]):
        condition["need_review"] = True
        condition["review_reason"] = "parenthesized signal canonical differs from leading signal"
        condition["confidence"]["overall"] = 0.72
        condition["confidence"]["normalization"] = 0.72
    return [condition]


def _parse_single_signal_state_without_predicate(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []

    match = re.search(
        rf"\b{re.escape(signals[0])}\s+{re.escape(state_placeholder)}\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[signals[0]]["entity"],
        placeholder_map[state_placeholder]["entity"],
        operator="==",
    )
    if not condition:
        return []
    condition["parser"] = "syntactic"
    condition["confidence"] = {
        "overall": 0.8,
        "structure": 0.8,
        "normalization": 0.9,
    }
    condition["need_review"] = False
    return [condition]


def _parse_single_signal_multi_right(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1 or len(right_entities) < 2:
        return []

    ordered_rights = _ordered_placeholders(placeholder_text, right_entities)
    if not _has_relation_between(placeholder_text, signals[0], ordered_rights[0]):
        return []

    logic = _placeholder_list_logic(placeholder_text, ordered_rights)
    if not logic:
        return []

    signal = placeholder_map[signals[0]]["entity"]
    children = [
        _condition_for_right_entity(
            original_text,
            signal,
            placeholder_map[right]["entity"],
            operator=_operator_for_right_placeholder(placeholder_text, signals[0], ordered_rights, right),
        )
        for right in ordered_rights
    ]
    if any(child is None for child in children):
        return []

    return [
        {
            "type": "condition_group",
            "logic": logic,
            "mention": original_text,
            "children": children,
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_multi_signal_single_right(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) < 2 or len(right_entities) != 1:
        return []

    ordered_signals = _ordered_placeholders(placeholder_text, signals)
    logic = _placeholder_list_logic(placeholder_text, ordered_signals)
    if not logic or not _has_relation_between(placeholder_text, ordered_signals[-1], right_entities[0]):
        return []

    right_entity = placeholder_map[right_entities[0]]["entity"]
    operator = _operator_for_right_placeholder(placeholder_text, ordered_signals[-1], right_entities, right_entities[0])
    children = [
        _condition_for_right_entity(original_text, placeholder_map[signal]["entity"], right_entity, operator=operator)
        for signal in ordered_signals
    ]
    if any(child is None for child in children):
        return []

    return [
        {
            "type": "condition_group",
            "logic": logic,
            "mention": original_text,
            "children": children,
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_single_signal_single_right(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1 or len(right_entities) != 1:
        return []
    if not _has_relation_between(placeholder_text, signals[0], right_entities[0]):
        return []

    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[signals[0]]["entity"],
        placeholder_map[right_entities[0]]["entity"],
        operator=_operator_for_right_placeholder(placeholder_text, signals[0], right_entities, right_entities[0]),
    )
    if not condition:
        return []
    condition["parser"] = "syntactic"
    return [condition]


def _condition_for_right_entity(
    original_text: str,
    signal: JsonDict,
    right_entity: JsonDict,
    operator: str = "==",
) -> JsonDict | None:
    signal_name = str(signal.get("canonical_name") or signal.get("mention"))
    signal_mention = _display_entity_mention(original_text, signal)
    right_type = str(right_entity.get("type", "")).upper()

    if right_type == "STATE":
        required_state = str(right_entity.get("canonical_name") or right_entity.get("mention"))
        return {
            "type": "signal_state_condition",
            "mention": f"{signal_mention} {operator} {required_state}",
            "signal": signal_name,
            "operator": operator,
            "required_state": required_state,
            "need_review": False,
        }

    if right_type == "PARAMETER":
        parameter_name = str(right_entity.get("canonical_name") or right_entity.get("mention"))
        return {
            "type": "parameter_threshold_condition",
            "mention": f"{signal_mention} {operator} {parameter_name}",
            "signal": signal_name,
            "operator": operator,
            "parameter": parameter_name,
            "need_review": False,
        }

    if right_type == "VALUE":
        parsed_value = _value_from_entity(right_entity)
        if parsed_value is None:
            return None
        return {
            "type": "threshold_condition",
            "mention": f"{signal_mention} {operator} {parsed_value['value']}",
            "signal": signal_name,
            "transform": None,
            "operator": operator,
            "value": parsed_value["value"],
            "unit": parsed_value["unit"],
            "need_review": False,
        }

    return None


def _condition_for_component_state(
    original_text: str,
    component: JsonDict,
    state: JsonDict,
) -> JsonDict | None:
    if str(state.get("type", "")).upper() != "STATE":
        return None

    component_name = str(component.get("canonical_name") or component.get("mention"))
    component_mention = _display_entity_mention(original_text, component)
    required_state = str(state.get("canonical_name") or state.get("mention"))
    return {
        "type": "component_state_condition",
        "mention": f"{component_mention} == {required_state}",
        "component": component_name,
        "operator": "==",
        "required_state": required_state,
        "need_review": False,
    }


def _placeholderize_entities(text: str, entities: List[JsonDict]) -> tuple[str, JsonDict]:
    spans = []
    for entity in entities:
        entity_type = str(entity.get("type", "")).upper()
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            continue
        for start, end, priority in _entity_spans(text, entity):
            spans.append((start, end, priority, entity_type, entity))

    selected = []
    occupied_until = -1
    for start, end, priority, entity_type, entity in sorted(spans, key=lambda item: (item[0], item[2], -(item[1] - item[0]))):
        if start < occupied_until:
            continue
        selected.append((start, end, entity_type, entity))
        occupied_until = end

    pieces = []
    cursor = 0
    counters: dict[str, int] = {}
    placeholder_map: JsonDict = {}
    for start, end, entity_type, entity in selected:
        counters[entity_type] = counters.get(entity_type, 0) + 1
        placeholder = f"{entity_type}_{counters[entity_type]}"
        pieces.append(text[cursor:start])
        pieces.append(placeholder)
        cursor = end
        placeholder_map[placeholder] = {"entity": entity, "span": [start, end], "text": text[start:end]}
    pieces.append(text[cursor:])
    return _remove_entity_wrapper_braces_from_placeholders("".join(pieces)), placeholder_map


def _remove_entity_wrapper_braces_from_placeholders(text: str) -> str:
    placeholder_pattern = "|".join(sorted(SUPPORTED_ENTITY_TYPES))
    return re.sub(
        rf"(?<![\w|])\{{(?P<placeholder>(?:{placeholder_pattern})_\d+)\}}(?!\|)",
        r"\g<placeholder>",
        text,
    )


def _right_relation_entities(placeholder_map: JsonDict) -> List[str]:
    return [
        placeholder
        for placeholder, payload in placeholder_map.items()
        if str(payload["entity"].get("type", "")).upper() in {"STATE", "VALUE", "PARAMETER"}
    ]


def _quantified_signal_logic(quantifier_text: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", quantifier_text.strip().lower())
    if normalized.startswith(("both", "all")):
        return "ALL", "AND"
    return "ANY_ONE", "OR"


def _placeholders_by_type(placeholder_map: JsonDict, entity_type: str) -> List[str]:
    return [
        placeholder
        for placeholder, payload in placeholder_map.items()
        if str(payload["entity"].get("type", "")).upper() == entity_type
    ]


def _ordered_placeholders(text: str, placeholders: List[str]) -> List[str]:
    return sorted(placeholders, key=lambda placeholder: text.find(placeholder))


def _placeholder_list_logic(text: str, placeholders: List[str]) -> str | None:
    if len(placeholders) < 2:
        return None

    has_and = False
    has_or = False
    for left, right in zip(placeholders, placeholders[1:]):
        left_end = text.find(left) + len(left)
        right_start = text.find(right)
        if right_start <= left_end:
            return None
        separator = text[left_end:right_start]
        if re.search(r"\b(?:or|and/or)\b", separator, flags=re.IGNORECASE):
            has_or = True
        elif re.search(r"\band\b", separator, flags=re.IGNORECASE) or "," in separator:
            has_and = True
        else:
            return None

    if has_or and has_and:
        return "OR" if re.search(r"\b(?:or|and/or)\b", text, flags=re.IGNORECASE) else "AND"
    if has_or:
        return "OR"
    if has_and:
        return "AND"
    return None


def _clause_group_logic(text: str, clauses: List[JsonDict]) -> str | None:
    if len(clauses) < 2:
        return None

    has_and = False
    has_or = False
    for left, right in zip(clauses, clauses[1:]):
        separator = text[int(left["state_end"]) : int(right["start"])]
        if re.search(r"\b(?:or|and/or)\b", separator, flags=re.IGNORECASE):
            has_or = True
        elif re.search(r"\band\b", separator, flags=re.IGNORECASE) or "," in separator:
            has_and = True
        else:
            return None

    if has_or and has_and:
        return "OR" if re.search(r"\b(?:or|and/or)\b", text, flags=re.IGNORECASE) else "AND"
    if has_or:
        return "OR"
    if has_and:
        return "AND"
    return None


def _has_relation_between(text: str, left_placeholder: str, right_placeholder: str) -> bool:
    left_end = text.find(left_placeholder) + len(left_placeholder)
    right_start = text.find(right_placeholder)
    if right_start <= left_end:
        return False
    return bool(RELATION_PATTERN.search(text[left_end:right_start]))


def _has_component_state_relation_between(text: str, component_placeholder: str, state_placeholder: str) -> bool:
    component_end = text.find(component_placeholder) + len(component_placeholder)
    state_start = text.find(state_placeholder)
    if state_start <= component_end:
        return False
    separator = text[component_end:state_start]
    return bool(
        re.search(rf"{RELATION_PATTERN.pattern}(?:\s+in)?\s*$", separator, flags=re.IGNORECASE)
        or re.search(r"\bin\s*$", separator, flags=re.IGNORECASE)
    )


def _operator_for_right_placeholder(
    text: str,
    signal_placeholder: str,
    ordered_rights: List[str],
    right_placeholder: str,
) -> str:
    right_index = ordered_rights.index(right_placeholder)
    if right_index == 0:
        left_boundary = text.find(signal_placeholder) + len(signal_placeholder)
    else:
        previous_right = ordered_rights[right_index - 1]
        left_boundary = text.find(previous_right) + len(previous_right)
    right_start = text.find(right_placeholder)
    if right_start <= left_boundary:
        return "=="

    local_text = text[left_boundary:right_start]
    operator = _operator_from_text(local_text)
    if operator:
        return operator
    return "=="


def _operator_from_text(text: str) -> str | None:
    if re.search(
        r"\b(?:is|are|be|shall\s+be|should\s+be|must\s+be|become|becomes|remain|remains)\s+not\b",
        text,
        flags=re.IGNORECASE,
    ):
        return "!="

    for pattern, operator in SYNTACTIC_COMPOUND_OPERATOR_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return operator

    for pattern, operator in COMPOUND_OPERATOR_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return operator

    aliases = sorted(OPERATOR_ALIASES, key=len, reverse=True)
    for alias in aliases:
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE):
            return OPERATOR_ALIASES[alias]
    return None


def _entity_spans(text: str, entity: JsonDict) -> List[tuple[int, int, int]]:
    spans: List[tuple[int, int, int]] = []
    seen: set[tuple[int, int]] = set()
    for priority, field_name in enumerate(("mention", "canonical_name")):
        value = str(entity.get(field_name, "")).strip()
        if not value:
            continue
        for match in re.finditer(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE):
            key = (match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            spans.append((match.start(), match.end(), priority))
    return spans


def _entity_span(text: str, entity: JsonDict) -> tuple[int, int] | None:
    candidates: List[tuple[int, int]] = []
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if not value:
            continue
        match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE)
        if match:
            candidates.append((match.start(), match.end()))
    return min(candidates, key=lambda span: span[0]) if candidates else None


def _same_canonical_entity(left: JsonDict, right: JsonDict) -> bool:
    left_type = str(left.get("type", "")).upper()
    right_type = str(right.get("type", "")).upper()
    if left_type != right_type:
        return False

    left_name = str(left.get("canonical_name") or left.get("mention") or "").strip().lower()
    right_name = str(right.get("canonical_name") or right.get("mention") or "").strip().lower()
    return bool(left_name and right_name and left_name == right_name)


def _display_entity_mention(text: str, entity: JsonDict) -> str:
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE):
            return value.strip("{}").strip()
    return str(entity.get("mention") or entity.get("canonical_name") or "").strip("{}").strip()


def _value_from_entity(entity: JsonDict) -> JsonDict | None:
    for field_name in ("canonical_name", "mention"):
        raw_value = str(entity.get(field_name, "")).strip().strip("\"'")
        if not raw_value:
            continue
        value_key = raw_value.lower()
        if value_key in VALUE_ALIASES:
            return {"value": VALUE_ALIASES[value_key], "unit": entity.get("unit")}
        if re.fullmatch(r"0x[0-9a-f]+", raw_value, flags=re.IGNORECASE):
            return {"value": raw_value, "unit": entity.get("unit")}
        value_unit = re.fullmatch(VALUE_UNIT_PATTERN, raw_value, flags=re.IGNORECASE)
        if value_unit:
            return {"value": number_value(value_unit.group("value")), "unit": value_unit.group("unit")}
        if re.fullmatch(r"\d+(?:\.\d+)?", raw_value):
            return {"value": number_value(raw_value), "unit": entity.get("unit")}
    return None


def _available_syntax_engine() -> str:
    try:
        import spacy  # noqa: F401
    except ImportError:
        return "placeholder"
    return "spacy"


def _spacy_tokens(text: str) -> List[JsonDict]:
    try:
        import spacy
    except ImportError:
        return []

    nlp = _load_spacy_model(spacy.load)
    if nlp is None:
        return []
    doc = nlp(text)
    return [
        {
            "text": token.text,
            "pos": token.pos_,
            "dep": token.dep_,
            "head": token.head.text,
        }
        for token in doc
    ]


def _load_spacy_model(loader: Callable[[str], object]) -> object | None:
    for model_name in ("en_core_web_sm", "en_core_web_md"):
        try:
            return loader(model_name)
        except OSError:
            continue
    return None
