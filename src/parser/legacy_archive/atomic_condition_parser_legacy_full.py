import re
from typing import List

from src.normalizer import canonical_for_mention
from src.schemas import JsonDict, number_value, unique_dicts


OPERATOR_ALIASES = {
    "greater than or equal to": ">=",
    "less than or equal to": "<=",
    "not equal to": "!=",
    "not equals": "!=",
    "not equal": "!=",
    "greater than": ">",
    "more than": ">",
    "above": ">",
    "less than": "<",
    "lower than": "<",
    "below": "<",
    "equal to": "==",
    "equals": "==",
    ">=": ">=",
    "<=": "<=",
    "!=": "!=",
    "==": "==",
    ">": ">",
    "<": "<",
    "=": "==",
}

COMPOUND_OPERATOR_PATTERNS = [
    (r"\bequal\s+to\s*(?:\([^)]*\)|and\s*/\s*or|and/or|and|or)?\s*greater\s+than\b", ">="),
    (r"\bequal\s+to\s*(?:\([^)]*\)|and\s*/\s*or|and/or|and|or)?\s*less\s+than\b", "<="),
]
OPERATOR_PATTERN = "|".join(re.escape(operator) for operator in sorted(OPERATOR_ALIASES, key=len, reverse=True))
STATE_COMPARISON_OPERATORS = {"==", "!="}
SIGNAL_PATTERN = r"S_[A-Z0-9_]+|vehicle speed|Column Torque|Column Velocity|Driver Torque|assist torque|torque demand"
SUPPORTED_UNITS = ["c-deg", "rev/s", "kph", "Nm"]
UNIT_PATTERN = "|".join(re.escape(unit) for unit in sorted(SUPPORTED_UNITS, key=len, reverse=True))
VALUE_UNIT_PATTERN = rf"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>{UNIT_PATTERN})"
VALUE_ALIASES = {
    "zero": 0,
}


def parse_atomic_conditions(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse all supported atomic condition forms from text."""

    normalized_entities = normalized_entities or []
    conditions: List[JsonDict] = []
    bracketed_definitions = parse_bracketed_definition_conditions(text, normalized_entities)
    if bracketed_definitions:
        return bracketed_definitions
    conditions.extend(parse_state_definition_conditions(text))
    conditions.extend(parse_range_conditions(text))
    conditions.extend(parse_redundant_signal_validity(text))
    conditions.extend(parse_quantified_signal_member_state_conditions(text, normalized_entities))
    conditions.extend(parse_fault_state_conditions(text))
    conditions.extend(parse_signal_comparison_conditions(text, normalized_entities))
    conditions.extend(parse_signal_state_and_parameter_threshold_conditions(text, normalized_entities))
    conditions.extend(parse_single_signal_value_state_conditions(text, normalized_entities))
    conditions.extend(parse_single_signal_value_conditions(text, normalized_entities))
    conditions.extend(parse_multi_signal_value_state_conditions(text, normalized_entities))
    conditions.extend(parse_multi_signal_value_conditions(text, normalized_entities))
    conditions.extend(parse_single_signal_multi_state_conditions(text, normalized_entities))
    conditions.extend(parse_multi_signal_single_state_conditions(text, normalized_entities))
    conditions.extend(parse_signal_state_conditions(text, normalized_entities))
    conditions.extend(parse_suffix_quantified_signal_parameter_conditions(text, normalized_entities))
    conditions.extend(parse_single_signal_parameter_conditions(text, normalized_entities))
    conditions.extend(parse_threshold_conditions(text))
    return conditions


def parse_condition_line(text: str, normalized_entities: List[JsonDict] | None = None) -> JsonDict:
    """Parse one condition line and return one atomic condition or review marker."""

    parsed = parse_atomic_conditions(text, normalized_entities)
    if parsed:
        return parsed[0]
    return {"type": "unparsed_condition", "mention": text, "need_review": True}


def _parse_threshold_fragment(fragment: str) -> JsonDict | None:
    """Parse one threshold expression such as S_X is greater than 3kph."""

    pattern = re.compile(
        rf"(?P<signal>\|\{{[^}}]+\}}\||abs\{{[^}}]+\}}|absolute\s*\{{[^}}]+\}}|\{{[^}}]+\}}|{SIGNAL_PATTERN})"
        rf"\s+(?:is\s+)?(?P<operator>{OPERATOR_PATTERN})\s+{VALUE_UNIT_PATTERN}",
        flags=re.IGNORECASE,
    )
    match = pattern.search(fragment)
    if not match:
        return None

    raw_signal = match.group("signal").strip()
    transform = None
    signal_mention = raw_signal
    if raw_signal.startswith("|{") and raw_signal.endswith("}|"):
        transform = "ABS"
        signal_mention = raw_signal[2:-2]
    elif raw_signal.lower().startswith("abs{") and raw_signal.endswith("}"):
        transform = "ABS"
        signal_mention = raw_signal[4:-1]
    elif raw_signal.lower().startswith("absolute"):
        transform = "ABS"
        inner = re.search(r"\{([^}]+)\}", raw_signal)
        signal_mention = inner.group(1) if inner else raw_signal
    elif raw_signal.startswith("{") and raw_signal.endswith("}"):
        signal_mention = raw_signal[1:-1]

    return {
        "type": "threshold_condition",
        "mention": match.group(0),
        "signal": canonical_for_mention(signal_mention),
        "transform": transform,
        "operator": OPERATOR_ALIASES[match.group("operator").lower()],
        "value": number_value(match.group("value")),
        "unit": match.group("unit"),
        "need_review": False,
    }


def parse_state_definition_conditions(text: str) -> List[JsonDict]:
    """Parse named state definitions with their enclosed signal predicate."""

    conditions: List[JsonDict] = []
    for match in re.finditer(r"\bvehicle\s+is\s+moving\s*\((?P<expr>[^)]*)\)", text, flags=re.IGNORECASE):
        threshold = _parse_threshold_fragment(match.group("expr"))
        if not threshold:
            conditions.append(
                {
                    "type": "state_definition_condition",
                    "mention": match.group(0),
                    "state_name": "VehicleMoving",
                    "need_review": True,
                    "review_reason": "state definition predicate was not parsed",
                }
            )
            continue
        conditions.append(
            {
                "type": "state_definition_condition",
                "mention": match.group(0),
                "state_name": "VehicleMoving",
                "signal": threshold["signal"],
                "operator": threshold["operator"],
                "value": threshold["value"],
                "unit": threshold["unit"],
                "definition": threshold,
                "need_review": False,
            }
        )
    return conditions


def parse_bracketed_definition_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse named natural-language definitions whose bracketed predicate is clear."""

    bracketed_definition = _outer_bracketed_definition(text)
    if not bracketed_definition:
        return []

    main_clause, definition_text = bracketed_definition
    if not main_clause or not definition_text:
        return []

    definition_entities = [
        entity
        for entity in normalized_entities
        if _entity_appears_in_text(definition_text, entity)
    ]
    definition_candidates = []
    definition_candidates.extend(parse_signal_comparison_conditions(definition_text, definition_entities))
    definition_candidates.extend(parse_suffix_quantified_signal_parameter_conditions(definition_text, normalized_entities))
    definition_candidates.extend(parse_single_signal_parameter_conditions(definition_text, definition_entities))
    definition_candidates.extend(parse_single_signal_value_conditions(definition_text, definition_entities))
    definition_candidates.extend(parse_multi_signal_value_conditions(definition_text, definition_entities))
    definition_candidates.extend(parse_signal_state_conditions(definition_text, definition_entities))
    threshold = _parse_threshold_fragment(definition_text)
    if threshold:
        _apply_signal_entity_canonical(threshold, definition_text, definition_entities)
        definition_candidates.append(threshold)

    definition = _first_confident_definition(definition_candidates)
    if not definition:
        return []

    signal_state_group = _bracketed_signal_state_definition_group(
        text,
        main_clause,
        definition,
        normalized_entities,
    )
    if signal_state_group:
        return [signal_state_group]

    state_name, state_source, state_confidence = _state_name_from_main_clause(main_clause, normalized_entities)
    definition_confidence = _definition_confidence(definition)
    confidence = {
        "overall": round((0.95 + state_confidence + definition_confidence) / 3, 2),
        "structure": 0.95,
        "state_name": state_confidence,
        "definition": definition_confidence,
    }
    need_review = state_confidence < 0.8 or bool(definition.get("need_review"))
    result = {
        "type": "state_definition_condition",
        "mention": text,
        "state_name": state_name,
        "state_source": state_source,
        "definition_relation": "DEFINED_BY",
        "definition": definition,
        "confidence": confidence,
        "need_review": need_review,
    }
    if need_review and state_confidence < 0.8:
        result["review_reason"] = "state name inferred from unclear natural-language description"
    return [result]


def parse_redundant_signal_validity(text: str) -> List[JsonDict]:
    """Parse redundant vehicle-speed signal validity quantifiers."""

    conditions: List[JsonDict] = []
    patterns = [
        (r"\bboth\s+vehicle speed signals\s+are\s+valid(?:\s+again)?\b", "ALL"),
        (r"\bone\s+of\s+the\s+vehicle speed signals\s+is\s+valid\b", "ANY_ONE"),
    ]
    for pattern, quantifier in patterns:
        for match in re.finditer(pattern, text, flags=re.IGNORECASE):
            conditions.append(
                {
                    "type": "redundant_signal_validity",
                    "mention": match.group(0),
                    "signal_group": "VehicleSpeedGroup",
                    "members": ["S_MAIN_VEHICLE_SPEED", "S_SECONDARY_VEHICLE_SPEED"],
                    "quantifier": quantifier,
                    "required_state": "valid",
                    "need_review": False,
                }
            )
    return conditions


def parse_quantified_signal_member_state_conditions(
    text: str,
    normalized_entities: List[JsonDict],
) -> List[JsonDict]:
    """Parse both/all/one-of quantified state checks over signal members."""

    if not normalized_entities:
        return []

    for signal in _matching_expandable_signals(text, normalized_entities):
        match = _quantified_signal_state_match(text, signal)
        if not match:
            continue

        quantifier, logic = _quantifier_logic(match.group("quantifier"))
        state = match.group("state").strip()
        source_signal = str(signal.get("canonical_name") or signal.get("mention"))
        members = [str(member) for member in signal.get("members", []) if str(member).strip()]
        if not members:
            return [
                {
                    "type": "condition_group",
                    "logic": logic,
                    "quantifier": quantifier,
                    "mention": match.group(0),
                    "source_signal": source_signal,
                    "children": [],
                    "need_review": True,
                    "review_reason": "quantified signal has no members to expand",
                }
            ]

        return [
            {
                "type": "condition_group",
                "logic": logic,
                "quantifier": quantifier,
                "mention": match.group(0),
                "source_signal": source_signal,
                "children": [
                    {
                        "type": "signal_state_condition",
                        "mention": f"{member} == {state}",
                        "signal": member,
                        "operator": "==",
                        "required_state": state,
                        "need_review": False,
                    }
                    for member in members
                ],
                "need_review": False,
            }
        ]

    return []


def parse_range_conditions(text: str) -> List[JsonDict]:
    """Parse symbolic and natural-language range predicates."""

    conditions: List[JsonDict] = []
    symbolic = re.compile(
        r"(?P<lower>\d+(?:\.\d+)?)\s*(?P<unit>kph|Nm)\s*<=\s*"
        r"(?P<signal>S_[A-Z0-9_]+)\s*<=\s*(?P<upper>\d+(?:\.\d+)?)\s*(?P=unit)",
        flags=re.IGNORECASE,
    )
    for match in symbolic.finditer(text):
        conditions.append(
            {
                "type": "range_condition",
                "mention": match.group(0),
                "signal": canonical_for_mention(match.group("signal")),
                "lower_operator": ">=",
                "lower_value": number_value(match.group("lower")),
                "upper_operator": "<=",
                "upper_value": number_value(match.group("upper")),
                "unit": match.group("unit"),
                "need_review": False,
            }
        )

    if conditions:
        return conditions

    natural = re.compile(
        r"\b(?P<signal>vehicle speed|S_[A-Z0-9_]+)\s+is\s+in\s+range\s+of\s+"
        r"(?P<lower>\d+(?:\.\d+)?)\s*(?P<unit>kph|Nm)\s+and\s+"
        r"(?P<upper>\d+(?:\.\d+)?)\s*(?P=unit)\b",
        flags=re.IGNORECASE,
    )
    for match in natural.finditer(text):
        conditions.append(
            {
                "type": "range_condition",
                "mention": match.group(0),
                "signal": canonical_for_mention(match.group("signal")),
                "lower_operator": ">=",
                "lower_value": number_value(match.group("lower")),
                "upper_operator": "<=",
                "upper_value": number_value(match.group("upper")),
                "unit": match.group("unit"),
                "need_review": False,
            }
        )
    return conditions


def parse_threshold_conditions(text: str) -> List[JsonDict]:
    """Parse threshold predicates across text."""

    conditions: List[JsonDict] = []
    pattern = re.compile(
        rf"(?P<expr>(?:\|\{{[^}}]+\}}\||abs\{{[^}}]+\}}|absolute\s*\{{[^}}]+\}}|\{{[^}}]+\}}|{SIGNAL_PATTERN})"
        rf"\s+(?:is\s+)?(?:{OPERATOR_PATTERN})\s+{VALUE_UNIT_PATTERN})",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        parsed = _parse_threshold_fragment(match.group("expr"))
        if parsed:
            conditions.append(parsed)
    return unique_dicts(conditions, ["type", "signal", "operator", "value", "unit", "transform"])


def parse_signal_state_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse enum-like signal state predicates such as S_X is equal to "FULL"."""

    if not normalized_entities:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    states = _matching_entities(text, normalized_entities, "STATE")
    operator = (
        _operator_from_entities(text, normalized_entities)
        or _operator_from_text(text)
        or _implicit_state_operator(text, signals, states)
    )
    if not signals or not states or not operator:
        return []
    if operator not in STATE_COMPARISON_OPERATORS:
        return []

    if len(signals) > 1 or len(states) > 1:
        return [
            {
                "type": "signal_state_condition",
                "mention": text,
                "need_review": True,
                "review_reason": "ambiguous signal or state candidates",
                "candidates": {
                    "signals": [_candidate_entity(entity) for entity in signals],
                    "states": [_candidate_entity(entity) for entity in states],
                },
            }
        ]

    condition = {
        "type": "signal_state_condition",
        "mention": text,
        "signal": str(signals[0].get("canonical_name") or signals[0].get("mention")),
        "operator": operator,
        "required_state": str(states[0].get("canonical_name") or states[0].get("mention")),
        "need_review": False,
    }
    qualifiers = _duration_qualifiers(text, normalized_entities)
    if qualifiers:
        condition["qualifiers"] = qualifiers
    return [condition]


def parse_single_signal_multi_state_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse one signal mapped to a list of possible states."""

    if not normalized_entities:
        return []

    signals = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "SIGNAL"))
    states = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "STATE"))
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if len(signals) != 1 or len(states) < 2:
        return []

    ordered_states = _ordered_entities_by_position(text, states)
    if not operator:
        operator = _implicit_list_relation_operator(text, signals[0], ordered_states[0])
    if operator not in STATE_COMPARISON_OPERATORS:
        return []

    logic = _entity_list_logic(text, ordered_states)
    if not logic:
        return []

    signal_name = str(signals[0].get("canonical_name") or signals[0].get("mention"))
    signal_mention = _display_entity_mention(text, signals[0])
    children = [
        {
            "type": "signal_state_condition",
            "mention": f"{signal_mention} {operator} {str(state.get('canonical_name') or state.get('mention'))}",
            "signal": signal_name,
            "operator": operator,
            "required_state": str(state.get("canonical_name") or state.get("mention")),
            "need_review": False,
        }
        for state in ordered_states
    ]
    return [
        {
            "type": "condition_group",
            "logic": logic,
            "mention": text,
            "children": children,
            "need_review": False,
        }
    ]


def parse_multi_signal_single_state_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse a list of signals that share one state predicate."""

    if not normalized_entities:
        return []

    signals = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "SIGNAL"))
    states = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "STATE"))
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if len(signals) < 2 or len(states) != 1:
        return []

    ordered_signals = _ordered_entities_by_position(text, signals)
    logic = _entity_list_logic(text, ordered_signals)
    if not logic:
        return []

    if not operator:
        operator = _implicit_list_relation_operator(text, ordered_signals[-1], states[0])
    if operator not in STATE_COMPARISON_OPERATORS:
        return []

    required_state = str(states[0].get("canonical_name") or states[0].get("mention"))
    children = [
        {
            "type": "signal_state_condition",
            "mention": f"{_display_entity_mention(text, signal)} {operator} {required_state}",
            "signal": str(signal.get("canonical_name") or signal.get("mention")),
            "operator": operator,
            "required_state": required_state,
            "need_review": False,
        }
        for signal in ordered_signals
    ]
    return [
        {
            "type": "condition_group",
            "logic": logic,
            "mention": text,
            "children": children,
            "need_review": False,
        }
    ]


def parse_single_signal_value_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse entity-driven numeric predicates such as S_X is equal to zero."""

    if not normalized_entities:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    values = _matching_entities(text, normalized_entities, "VALUE")
    operator = (
        _operator_from_entities(text, normalized_entities)
        or _operator_from_text(text)
        or _implicit_single_entity_relation_operator(text, signals, values)
    )
    if len(signals) != 1 or len(values) != 1 or not operator:
        return []

    parsed_value = _value_from_entity(values[0])
    if parsed_value is None:
        return [
            {
                "type": "threshold_condition",
                "mention": text,
                "need_review": True,
                "review_reason": "value was not parsed",
                "candidates": {"values": [_candidate_entity(value) for value in values]},
            }
        ]

    signal_mention = _clean_braced_mention(str(signals[0].get("mention") or signals[0].get("canonical_name") or ""))
    value_mention = f"{parsed_value['value']}{parsed_value['unit'] or ''}"
    condition = {
        "type": "threshold_condition",
        "mention": f"{signal_mention} {operator} {value_mention}",
        "signal": str(signals[0].get("canonical_name") or signals[0].get("mention")),
        "transform": None,
        "operator": operator,
        "value": parsed_value["value"],
        "unit": parsed_value["unit"],
        "need_review": False,
    }
    qualifiers = _duration_qualifiers(text, normalized_entities)
    if qualifiers:
        condition["qualifiers"] = qualifiers
    return [condition]


def parse_signal_state_and_parameter_threshold_conditions(
    text: str,
    normalized_entities: List[JsonDict],
) -> List[JsonDict]:
    """Parse combined predicates such as S_X is valid and greater than P_MIN."""

    if not normalized_entities:
        return []

    signal = _select_preferred_signal(text, _matching_entities(text, normalized_entities, "SIGNAL"))
    states = _matching_entities(text, normalized_entities, "STATE")
    parameters = _comparison_parameters(text, normalized_entities)
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if not signal or len(states) != 1 or len(parameters) != 1 or not operator:
        return []
    if operator in STATE_COMPARISON_OPERATORS:
        return []

    signal_name = str(signal.get("canonical_name") or signal.get("mention"))
    state_name = str(states[0].get("canonical_name") or states[0].get("mention"))
    parameter_name = str(parameters[0].get("canonical_name") or parameters[0].get("mention"))
    signal_mention = _display_entity_mention(text, signal)
    parameter_mention = _display_entity_mention(text, parameters[0])
    return [
        {
            "type": "condition_group",
            "logic": "AND",
            "mention": text,
            "children": [
                {
                    "type": "signal_state_condition",
                    "mention": f"{signal_mention} == {state_name}",
                    "signal": signal_name,
                    "operator": "==",
                    "required_state": state_name,
                    "need_review": False,
                },
                {
                    "type": "parameter_threshold_condition",
                    "mention": f"{signal_mention} {operator} {parameter_mention}",
                    "signal": signal_name,
                    "operator": operator,
                    "parameter": parameter_name,
                    "need_review": False,
                },
            ],
            "need_review": False,
        }
    ]


def parse_signal_comparison_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse signal-to-signal comparisons, optionally qualified by duration."""

    if not normalized_entities:
        return []
    if _matching_entities(text, normalized_entities, "VALUE") or _matching_entities(text, normalized_entities, "STATE"):
        return []

    signals = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "SIGNAL"))
    if len(signals) < 2:
        return []

    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if not operator:
        return []

    left_signal, left_transform = _left_signal_comparison_operand(text, signals)
    right_signal = _right_signal_comparison_operand(text, signals, left_signal)
    if not left_signal or not right_signal:
        return []
    if not _right_signal_after_operator(text, right_signal, operator):
        return []

    left_name = str(left_signal.get("canonical_name") or left_signal.get("mention"))
    right_name = str(right_signal.get("canonical_name") or right_signal.get("mention"))
    left_mention = _display_entity_mention(text, left_signal)
    right_mention = _display_entity_mention(text, right_signal)
    left_display = f"{left_transform}({left_mention})" if left_transform else left_mention
    condition = {
        "type": "signal_comparison_condition",
        "mention": _signal_comparison_mention(text, left_display, operator, right_mention),
        "left_signal": left_name,
        "operator": operator,
        "right_signal": right_name,
        "qualifiers": _duration_qualifiers(text, normalized_entities),
        "need_review": False,
    }
    if left_transform:
        condition["left_transform"] = left_transform
    return [condition]


def parse_single_signal_parameter_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse parameter thresholds such as S_X >= P_MIN_VALUE."""

    if not normalized_entities:
        return []

    signal = _select_preferred_signal(text, _matching_entities(text, normalized_entities, "SIGNAL"))
    parameters = _comparison_parameters(text, normalized_entities)
    signal_candidates = [signal] if signal else []
    operator = (
        _operator_from_entities(text, normalized_entities)
        or _operator_from_text(text)
        or _implicit_single_entity_relation_operator(text, signal_candidates, parameters)
    )
    if not signal or len(parameters) != 1 or not operator:
        return []

    signal_name = str(signal.get("canonical_name") or signal.get("mention"))
    parameter_name = str(parameters[0].get("canonical_name") or parameters[0].get("mention"))
    signal_mention = _display_entity_mention(text, signal)
    parameter_mention = _display_entity_mention(text, parameters[0])
    transform = _transform_for_signal_parameter_condition(text, signal, normalized_entities)
    mention_signal = f"{transform}({signal_mention})" if transform else signal_mention
    condition = {
        "type": "parameter_threshold_condition",
        "mention": f"{mention_signal} {operator} {parameter_mention}",
        "signal": signal_name,
        "operator": operator,
        "parameter": parameter_name,
        "need_review": False,
    }
    if transform:
        condition["transform"] = transform
    qualifiers = _duration_qualifiers(text, normalized_entities)
    if qualifiers:
        condition["qualifiers"] = qualifiers
    return [
        condition
    ]


def parse_suffix_quantified_signal_parameter_conditions(
    text: str,
    normalized_entities: List[JsonDict],
) -> List[JsonDict]:
    """Parse S_ABCn/m OP PARAMETER using base signal members."""

    if not normalized_entities:
        return []

    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    parameters = _comparison_parameters(text, normalized_entities)
    if len(parameters) != 1 or not operator:
        return []

    for base_signal, suffix_signal, suffix in _suffix_quantified_signal_matches(text, normalized_entities):
        quantifier, logic = ("ALL", "AND") if suffix.lower() == "n" else ("ANY_ONE", "OR")
        source_signal = str(base_signal.get("canonical_name") or base_signal.get("mention"))
        parameter_name = str(parameters[0].get("canonical_name") or parameters[0].get("mention"))
        parameter_mention = _display_entity_mention(text, parameters[0])
        members = [str(member) for member in base_signal.get("members", []) if str(member).strip()]
        if not members:
            return [
                {
                    "type": "condition_group",
                    "logic": logic,
                    "quantifier": quantifier,
                    "mention": f"{suffix_signal} {operator} {parameter_mention}",
                    "source_signal": source_signal,
                    "children": [],
                    "need_review": True,
                    "review_reason": "quantified suffix signal has no members to expand",
                }
            ]

        return [
            {
                "type": "condition_group",
                "logic": logic,
                "quantifier": quantifier,
                "mention": f"{suffix_signal} {operator} {parameter_mention}",
                "source_signal": source_signal,
                "children": [
                    {
                        "type": "parameter_threshold_condition",
                        "mention": f"{member} {operator} {parameter_mention}",
                        "signal": member,
                        "operator": operator,
                        "parameter": parameter_name,
                        "need_review": False,
                    }
                    for member in members
                ],
                "need_review": False,
            }
        ]

    return []


def parse_single_signal_value_state_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse enum labels such as S_X is equal to "0x1: Override"."""

    if not normalized_entities or ":" not in text:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    values = _matching_entities(text, normalized_entities, "VALUE")
    states = _matching_entities(text, normalized_entities, "STATE")
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if len(signals) != 1 or len(values) != 1 or len(states) != 1 or not operator:
        return []

    return _build_value_state_condition_group(text, signals, values[0], states[0], operator)


def parse_multi_signal_value_state_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse shared enum labels such as A and B are equal to "0x1: Valid"."""

    if not normalized_entities or ":" not in text:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    values = _matching_entities(text, normalized_entities, "VALUE")
    states = _matching_entities(text, normalized_entities, "STATE")
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if len(signals) < 2 or len(values) != 1 or len(states) != 1 or not operator:
        return []

    return _build_value_state_condition_group(text, signals, values[0], states[0], operator)


def _build_value_state_condition_group(
    text: str,
    signals: List[JsonDict],
    value: JsonDict,
    state: JsonDict,
    operator: str,
) -> List[JsonDict]:
    """Build condition_group children for VALUE: STATE labels."""

    parsed_value = _value_from_entity(value)
    if parsed_value is None:
        return []

    required_state = str(state.get("canonical_name") or state.get("mention"))
    per_signal_groups: List[JsonDict] = []
    for signal in signals:
        signal_name = str(signal.get("canonical_name") or signal.get("mention"))
        signal_mention = _clean_braced_mention(str(signal.get("mention") or signal_name))
        value_mention = f"{parsed_value['value']}{parsed_value['unit'] or ''}"
        signal_children = [
            {
                "type": "threshold_condition",
                "mention": f"{signal_mention} {operator} {value_mention}",
                "signal": signal_name,
                "transform": None,
                "operator": operator,
                "value": parsed_value["value"],
                "unit": parsed_value["unit"],
                "need_review": False,
            },
            {
                "type": "signal_state_condition",
                "mention": f"{signal_mention} {operator} {required_state}",
                "signal": signal_name,
                "operator": operator,
                "required_state": required_state,
                "need_review": False,
            },
        ]
        per_signal_groups.append(
            {
                "type": "condition_group",
                "logic": "AND",
                "mention": f"{signal_mention} {operator} {value_mention}:{required_state}",
                "children": signal_children,
                "need_review": False,
            }
        )

    if _has_or_between_signal_conditions(text) and len(per_signal_groups) > 1:
        return [
            {
                "type": "condition_group",
                "logic": "OR",
                "mention": text,
                "children": per_signal_groups,
                "need_review": False,
            }
        ]

    children: List[JsonDict] = []
    for group in per_signal_groups:
        children.extend(group["children"])

    return [
        {
            "type": "condition_group",
            "logic": "AND",
            "mention": text,
            "children": children,
            "need_review": False,
        }
    ]


def parse_multi_signal_value_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse shared numeric predicates such as {A} and {B} are equal to zero."""

    if not normalized_entities:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    values = _matching_entities(text, normalized_entities, "VALUE")
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if len(signals) < 2 or len(values) != 1 or not operator:
        return []

    parsed_value = _value_from_entity(values[0])
    if parsed_value is None:
        return [
            {
                "type": "condition_group",
                "logic": "AND",
                "mention": text,
                "need_review": True,
                "review_reason": "shared value was not parsed",
                "candidates": {"values": [_candidate_entity(value) for value in values]},
            }
        ]

    children = []
    for signal in signals:
        signal_mention = _clean_braced_mention(str(signal.get("mention") or signal.get("canonical_name") or ""))
        children.append(
            {
                "type": "threshold_condition",
                "mention": f"{signal_mention} {operator} {parsed_value['value']}",
                "signal": str(signal.get("canonical_name") or signal.get("mention")),
                "transform": None,
                "operator": operator,
                "value": parsed_value["value"],
                "unit": parsed_value["unit"],
                "need_review": False,
            }
        )

    return [
        {
            "type": "condition_group",
            "logic": "AND",
            "mention": text,
            "children": children,
            "need_review": False,
        }
    ]


def parse_fault_state_conditions(text: str) -> List[JsonDict]:
    """Parse DEM fault Active/Inactive predicates."""

    conditions: List[JsonDict] = []
    for match in re.finditer(r"\b(?P<fault>DEM_[A-Z0-9_]+)\s+is\s+(?P<state>Active|Inactive)\b", text):
        conditions.append(
            {
                "type": "fault_state_condition",
                "mention": match.group(0),
                "fault_signal": match.group("fault"),
                "required_state": match.group("state"),
                "need_review": False,
            }
        )
    return conditions


def _matching_entities(text: str, entities: List[JsonDict], entity_type: str) -> List[JsonDict]:
    return [
        entity
        for entity in entities
        if str(entity.get("type", "")).upper() == entity_type and _entity_appears_in_text(text, entity)
    ]


def _matching_expandable_signals(text: str, entities: List[JsonDict]) -> List[JsonDict]:
    signals = [
        entity
        for entity in entities
        if str(entity.get("type", "")).upper() in {"SIGNAL", "SIGNAL_GROUP"}
        and _entity_appears_in_text(text, entity)
    ]
    return _unique_entities_by_canonical(signals)


def _quantified_signal_state_match(text: str, signal: JsonDict) -> re.Match[str] | None:
    signal_pattern = _entity_alias_pattern(signal)
    if not signal_pattern:
        return None
    quantifier_pattern = (
        r"(?P<quantifier>"
        r"both(?:\s+(?:of|lanes?(?:\s+of)?))?|"
        r"all(?:\s+(?:of|lanes?(?:\s+of)?))?|"
        r"one\s+(?:of|lanes?(?:\s+of)?)|"
        r"any(?:\s+(?:one\s+of|of|lanes?(?:\s+of)?))"
        r")"
    )
    article_pattern = r"(?:the\s+)?"
    pattern = re.compile(
        rf"\b{quantifier_pattern}\s+{article_pattern}{signal_pattern}\s+(?:is|are)\s+"
        r"(?P<state>not\s+valid|valid|invalid|active|inactive|available|unavailable|full)\b",
        flags=re.IGNORECASE,
    )
    return pattern.search(text)


def _entity_alias_pattern(entity: JsonDict) -> str:
    aliases = []
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if value:
            aliases.append(value)
    unique_aliases = sorted(set(aliases), key=len, reverse=True)
    if not unique_aliases:
        return ""
    alternatives = "|".join(rf"(?:{re.escape(alias)})" for alias in unique_aliases)
    return rf"(?:{alternatives})"


def _quantifier_logic(quantifier_text: str) -> tuple[str, str]:
    normalized = re.sub(r"\s+", " ", quantifier_text.strip().lower())
    if normalized.startswith(("both", "all")):
        return "ALL", "AND"
    return "ANY_ONE", "OR"


def _unique_entities_by_canonical(entities: List[JsonDict]) -> List[JsonDict]:
    unique: List[JsonDict] = []
    seen = set()
    for entity in entities:
        key = str(entity.get("canonical_name") or entity.get("mention") or "").upper()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(entity)
    return unique


def _select_preferred_signal(text: str, signals: List[JsonDict]) -> JsonDict | None:
    unique_signals = _unique_entities_by_canonical(signals)
    if len(unique_signals) == 1:
        return unique_signals[0]

    for bracketed_text in re.findall(r"\(([^()]*)\)", text):
        bracketed_signals = [
            signal
            for signal in unique_signals
            if _entity_appears_in_text(bracketed_text, signal)
        ]
        bracketed_signals = _unique_entities_by_canonical(bracketed_signals)
        if len(bracketed_signals) == 1:
            return bracketed_signals[0]
    return None


def _entity_appears_in_text(text: str, entity: JsonDict) -> bool:
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE):
            return True
    return False


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


def _clean_braced_mention(mention: str) -> str:
    return mention.strip().strip("{}").strip()


def _display_entity_mention(text: str, entity: JsonDict) -> str:
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if value and re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE):
            return _clean_braced_mention(value)
    return _clean_braced_mention(str(entity.get("mention") or entity.get("canonical_name") or ""))


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


def _ordered_entities_by_position(text: str, entities: List[JsonDict]) -> List[JsonDict]:
    return sorted(entities, key=lambda entity: _first_entity_position(text, entity))


def _entity_list_logic(text: str, entities: List[JsonDict]) -> str | None:
    if len(entities) < 2:
        return None

    has_and = False
    has_or = False
    for left, right in zip(entities, entities[1:]):
        left_span = _entity_span(text, left)
        right_span = _entity_span(text, right)
        if not left_span or not right_span or right_span[0] <= left_span[1]:
            return None
        separator = text[left_span[1] : right_span[0]]
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


def _outer_bracketed_definition(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.endswith(")"):
        return None

    depth = 0
    closing_index = len(stripped) - 1
    for index in range(closing_index, -1, -1):
        char = stripped[index]
        if char == ")":
            depth += 1
        elif char == "(":
            depth -= 1
            if depth == 0:
                main_clause = stripped[:index].strip()
                definition_text = stripped[index + 1 : closing_index].strip()
                return main_clause, definition_text
    return None


def _bracketed_signal_state_definition_group(
    text: str,
    main_clause: str,
    definition: JsonDict,
    normalized_entities: List[JsonDict],
) -> JsonDict | None:
    signals = _unique_entities_by_canonical(
        [
            entity
            for entity in normalized_entities
            if str(entity.get("type", "")).upper() == "SIGNAL" and _entity_appears_in_text(main_clause, entity)
        ]
    )
    states = [
        entity
        for entity in normalized_entities
        if str(entity.get("type", "")).upper() == "STATE" and _entity_appears_in_text(main_clause, entity)
    ]
    if len(states) > 1:
        states = _longest_non_status_states(states)
    if len(signals) != 1 or len(states) != 1:
        return None

    signal = signals[0]
    state = states[0]
    signal_mention = _display_entity_mention(main_clause, signal)
    signal_state_condition = {
        "type": "signal_state_condition",
        "mention": f"{signal_mention} == {state.get('canonical_name') or state.get('mention')}",
        "signal": str(signal.get("canonical_name") or signal.get("mention")),
        "operator": "==",
        "required_state": str(state.get("canonical_name") or state.get("mention")),
        "need_review": False,
    }
    return {
        "type": "condition_group",
        "logic": "AND",
        "mention": text,
        "children": [signal_state_condition, definition],
        "need_review": bool(signal_state_condition.get("need_review") or definition.get("need_review")),
    }


def _suffix_quantified_signal_matches(
    text: str,
    normalized_entities: List[JsonDict],
) -> List[tuple[JsonDict, str, str]]:
    matches: List[tuple[JsonDict, str, str]] = []
    signals = _unique_entities_by_canonical(
        [
            entity
            for entity in normalized_entities
            if str(entity.get("type", "")).upper() == "SIGNAL"
        ]
    )
    for signal in signals:
        for field_name in ("canonical_name", "mention"):
            base = str(signal.get(field_name, "")).strip()
            if not base:
                continue
            pattern = re.compile(rf"(?<!\w)(?P<suffix_signal>{re.escape(base)}(?P<suffix>[nm]))(?!\w)", flags=re.IGNORECASE)
            for match in pattern.finditer(text):
                matches.append((signal, match.group("suffix_signal"), match.group("suffix")))
                break
            if matches and matches[-1][0] is signal:
                break
    return matches


def _left_signal_comparison_operand(text: str, signals: List[JsonDict]) -> tuple[JsonDict | None, str | None]:
    for signal in signals:
        signal_alias = _entity_alias_pattern(signal)
        if not signal_alias:
            continue
        abs_patterns = [
            rf"\|\s*\{{\s*{signal_alias}\s*\}}\s*\|",
            rf"\babs\s*[\(\{{]\s*{signal_alias}\s*[\)\}}]",
            rf"\babsolute\s*[\(\{{]\s*{signal_alias}\s*[\)\}}]",
        ]
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in abs_patterns):
            return signal, "ABS"

    ordered = sorted(
        signals,
        key=lambda signal: _first_entity_position(text, signal),
    )
    return (ordered[0], None) if ordered else (None, None)


def _right_signal_comparison_operand(
    text: str,
    signals: List[JsonDict],
    left_signal: JsonDict | None,
) -> JsonDict | None:
    candidates = [signal for signal in signals if signal is not left_signal]
    if not candidates:
        return None
    return sorted(candidates, key=lambda signal: _first_entity_position(text, signal))[0]


def _right_signal_after_operator(text: str, right_signal: JsonDict, operator: str) -> bool:
    right_position = _first_entity_position(text, right_signal)
    operator_position = _operator_position(text, operator)
    return operator_position >= 0 and right_position > operator_position


def _operator_position(text: str, operator: str) -> int:
    operator_aliases = [
        alias
        for alias, canonical in OPERATOR_ALIASES.items()
        if canonical == operator
    ]
    for alias in sorted(operator_aliases, key=len, reverse=True):
        match = re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE)
        if match:
            return match.start()
    return -1


def _first_entity_position(text: str, entity: JsonDict) -> int:
    positions = []
    for field_name in ("mention", "canonical_name"):
        value = str(entity.get(field_name, "")).strip()
        if not value:
            continue
        match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE)
        if match:
            positions.append(match.start())
    return min(positions) if positions else len(text) + 1


def _duration_qualifiers(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    parameters = _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "PARAMETER"))
    qualifiers: List[JsonDict] = []
    for parameter in parameters:
        parameter_name = str(parameter.get("canonical_name") or parameter.get("mention"))
        parameter_pattern = _entity_alias_pattern(parameter)
        if not parameter_pattern:
            continue
        pattern = re.compile(
            rf"\bfor\s+(?:a\s+)?period\s+of\s+(?P<parameter>{parameter_pattern})\b",
            flags=re.IGNORECASE,
        )
        match = pattern.search(text)
        if not match:
            continue
        qualifiers.append(
            {
                "type": "duration",
                "mention": match.group(0),
                "parameter": parameter_name,
            }
        )
    return qualifiers


def _comparison_parameters(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    duration_parameter_names = {
        str(qualifier.get("parameter"))
        for qualifier in _duration_qualifiers(text, normalized_entities)
    }
    return [
        parameter
        for parameter in _unique_entities_by_canonical(_matching_entities(text, normalized_entities, "PARAMETER"))
        if str(parameter.get("canonical_name") or parameter.get("mention")) not in duration_parameter_names
    ]


def _signal_comparison_mention(text: str, left_display: str, operator: str, right_mention: str) -> str:
    qualifiers = re.search(r"\bfor\s+(?:a\s+)?period\s+of\s+\S+\b", text, flags=re.IGNORECASE)
    base = f"{left_display} {operator} {right_mention}"
    return f"{base} {qualifiers.group(0)}" if qualifiers else base


def _transform_for_signal_parameter_condition(
    text: str,
    signal: JsonDict,
    normalized_entities: List[JsonDict],
) -> str | None:
    signal_alias = _entity_alias_pattern(signal)
    if signal_alias:
        transform_patterns = [
            rf"\|\s*\{{\s*{signal_alias}\s*\}}\s*\|",
            rf"\babs\s*\{{\s*{signal_alias}\s*\}}",
            rf"\babsolute\s*\{{\s*{signal_alias}\s*\}}",
        ]
        for pattern in transform_patterns:
            if re.search(pattern, text, flags=re.IGNORECASE):
                return "ABS"

    transforms = [
        entity
        for entity in normalized_entities
        if str(entity.get("type", "")).upper() == "TRANSFORM"
        and _entity_appears_in_text(text, entity)
    ]
    for transform in transforms:
        canonical = str(transform.get("canonical_name") or transform.get("mention") or "").upper()
        if canonical == "ABS":
            return "ABS"
    return None


def _has_or_between_signal_conditions(text: str) -> bool:
    return bool(re.search(r"\b(?:or|and/or)\b", text, flags=re.IGNORECASE))


def _first_confident_definition(candidates: List[JsonDict]) -> JsonDict | None:
    for candidate in candidates:
        if not candidate.get("need_review"):
            return candidate
    return candidates[0] if candidates else None


def _definition_confidence(definition: JsonDict) -> float:
    if definition.get("need_review"):
        return 0.6
    if definition.get("type") in {
        "condition_group",
        "threshold_condition",
        "parameter_threshold_condition",
        "signal_state_condition",
    }:
        return 0.95
    return 0.75


def _apply_signal_entity_canonical(threshold: JsonDict, text: str, entities: List[JsonDict]) -> None:
    signals = _matching_entities(text, entities, "SIGNAL")
    if len(signals) == 1:
        threshold["signal"] = str(signals[0].get("canonical_name") or signals[0].get("mention"))


def _state_name_from_main_clause(main_clause: str, normalized_entities: List[JsonDict]) -> tuple[str, str, float]:
    states = [
        entity
        for entity in normalized_entities
        if str(entity.get("type", "")).upper() == "STATE" and _entity_appears_in_text(main_clause, entity)
    ]
    if len(states) > 1:
        states = _longest_non_status_states(states)
    if len(states) == 1:
        return str(states[0].get("canonical_name") or states[0].get("mention")), "dictionary", 0.9

    return _pascal_case_name(main_clause), "inferred_from_text", 0.45


def _longest_non_status_states(states: List[JsonDict]) -> List[JsonDict]:
    status_words = {"active", "inactive", "valid", "invalid", "available", "unavailable", "full", "detected"}
    filtered = [
        state
        for state in states
        if str(state.get("canonical_name") or state.get("mention") or "").strip().lower() not in status_words
    ]
    candidates = filtered or states
    max_length = max(len(str(state.get("mention") or state.get("canonical_name") or "")) for state in candidates)
    return [
        state
        for state in candidates
        if len(str(state.get("mention") or state.get("canonical_name") or "")) == max_length
    ]


def _pascal_case_name(text: str) -> str:
    cleaned = re.sub(r"[{}()\"']", " ", text)
    cleaned = re.sub(r"\b(?:no|the|a|an|and|or|condition|conditions)\b", " ", cleaned, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9]+", cleaned)
    return "".join(word[:1].upper() + word[1:].lower() for word in words) or "UnnamedCondition"


def _operator_from_entities(text: str, entities: List[JsonDict]) -> str | None:
    compound_operator = _compound_operator_from_text(text)
    if compound_operator:
        return compound_operator

    for entity in entities:
        if str(entity.get("type", "")).upper() != "OPERATOR" or not _entity_appears_in_text(text, entity):
            continue
        operator_text = str(entity.get("canonical_name") or entity.get("mention") or "").lower()
        operator = OPERATOR_ALIASES.get(operator_text)
        if operator:
            return operator
    return None


def _operator_from_text(text: str) -> str | None:
    compound_operator = _compound_operator_from_text(text)
    if compound_operator:
        return compound_operator

    match = re.search(OPERATOR_PATTERN, text, flags=re.IGNORECASE)
    if not match:
        return None
    return OPERATOR_ALIASES[match.group(0).lower()]


def _implicit_state_operator(text: str, signals: List[JsonDict], states: List[JsonDict]) -> str | None:
    if len(signals) != 1 or len(states) != 1:
        return None
    signal_pattern = _entity_alias_pattern(signals[0])
    state_pattern = _entity_alias_pattern(states[0])
    if not signal_pattern or not state_pattern:
        return None
    pattern = re.compile(
        rf"{signal_pattern}\s+(?:is|are)\s+{state_pattern}\b",
        flags=re.IGNORECASE,
    )
    return "==" if pattern.search(text) else None


def _implicit_single_entity_relation_operator(
    text: str,
    left_entities: List[JsonDict],
    right_entities: List[JsonDict],
) -> str | None:
    if len(left_entities) != 1 or len(right_entities) != 1:
        return None
    return _implicit_list_relation_operator(text, left_entities[0], right_entities[0])


def _implicit_list_relation_operator(text: str, left_entity: JsonDict, right_entity: JsonDict) -> str | None:
    left_span = _entity_span(text, left_entity)
    right_span = _entity_span(text, right_entity)
    if not left_span or not right_span or right_span[0] <= left_span[1]:
        return None
    relation_text = text[left_span[1] : right_span[0]]
    return "==" if re.search(r"\b(?:is|are)\b", relation_text, flags=re.IGNORECASE) else None


def _compound_operator_from_text(text: str) -> str | None:
    for pattern, operator in COMPOUND_OPERATOR_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return operator
    return None


def _candidate_entity(entity: JsonDict) -> JsonDict:
    return {
        "mention": entity.get("mention"),
        "canonical_name": entity.get("canonical_name"),
        "type": entity.get("type"),
    }
