import re
from typing import List

from src.normalizer import canonical_for_mention
from src.schemas import JsonDict, number_value, unique_dicts


OPERATOR_ALIASES = {
    "greater than or equal to": ">=",
    "less than or equal to": "<=",
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

OPERATOR_PATTERN = "|".join(re.escape(operator) for operator in sorted(OPERATOR_ALIASES, key=len, reverse=True))
SIGNAL_PATTERN = r"S_[A-Z0-9_]+|vehicle speed|Column Torque|Column Velocity|Driver Torque|assist torque|torque demand"
VALUE_UNIT_PATTERN = r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kph|Nm|rev/s)"
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
    conditions.extend(parse_fault_state_conditions(text))
    conditions.extend(parse_single_signal_value_conditions(text, normalized_entities))
    conditions.extend(parse_multi_signal_value_conditions(text, normalized_entities))
    conditions.extend(parse_signal_state_conditions(text, normalized_entities))
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

    match = re.fullmatch(r"\s*(?P<main>.+?)\s*\((?P<definition>[^()]*)\)\s*", text)
    if not match:
        return []

    main_clause = match.group("main").strip()
    definition_text = match.group("definition").strip()
    if not main_clause or not definition_text:
        return []

    definition_entities = [
        entity
        for entity in normalized_entities
        if _entity_appears_in_text(definition_text, entity)
    ]
    definition_candidates = []
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
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
    if not signals or not states or not operator:
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

    return [
        {
            "type": "signal_state_condition",
            "mention": text,
            "signal": str(signals[0].get("canonical_name") or signals[0].get("mention")),
            "operator": operator,
            "required_state": str(states[0].get("canonical_name") or states[0].get("mention")),
            "need_review": False,
        }
    ]


def parse_single_signal_value_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Parse entity-driven numeric predicates such as S_X is equal to zero."""

    if not normalized_entities:
        return []

    signals = _matching_entities(text, normalized_entities, "SIGNAL")
    values = _matching_entities(text, normalized_entities, "VALUE")
    operator = _operator_from_entities(text, normalized_entities) or _operator_from_text(text)
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
    return [
        {
            "type": "threshold_condition",
            "mention": f"{signal_mention} {operator} {value_mention}",
            "signal": str(signals[0].get("canonical_name") or signals[0].get("mention")),
            "transform": None,
            "operator": operator,
            "value": parsed_value["value"],
            "unit": parsed_value["unit"],
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
        value_unit = re.fullmatch(r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kph|Nm|rev/s)", raw_value, flags=re.IGNORECASE)
        if value_unit:
            return {"value": number_value(value_unit.group("value")), "unit": value_unit.group("unit")}
        if re.fullmatch(r"\d+(?:\.\d+)?", raw_value):
            return {"value": number_value(raw_value), "unit": entity.get("unit")}
    return None


def _clean_braced_mention(mention: str) -> str:
    return mention.strip().strip("{}").strip()


def _first_confident_definition(candidates: List[JsonDict]) -> JsonDict | None:
    for candidate in candidates:
        if not candidate.get("need_review"):
            return candidate
    return candidates[0] if candidates else None


def _definition_confidence(definition: JsonDict) -> float:
    if definition.get("need_review"):
        return 0.6
    if definition.get("type") in {"condition_group", "threshold_condition", "signal_state_condition"}:
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
    if len(states) == 1:
        return str(states[0].get("canonical_name") or states[0].get("mention")), "dictionary", 0.9

    return _pascal_case_name(main_clause), "inferred_from_text", 0.45


def _pascal_case_name(text: str) -> str:
    cleaned = re.sub(r"[{}()\"']", " ", text)
    cleaned = re.sub(r"\b(?:no|the|a|an|and|or|condition|conditions)\b", " ", cleaned, flags=re.IGNORECASE)
    words = re.findall(r"[A-Za-z0-9]+", cleaned)
    return "".join(word[:1].upper() + word[1:].lower() for word in words) or "UnnamedCondition"


def _operator_from_entities(text: str, entities: List[JsonDict]) -> str | None:
    for entity in entities:
        if str(entity.get("type", "")).upper() != "OPERATOR" or not _entity_appears_in_text(text, entity):
            continue
        operator_text = str(entity.get("canonical_name") or entity.get("mention") or "").lower()
        return OPERATOR_ALIASES.get(operator_text)
    return None


def _operator_from_text(text: str) -> str | None:
    match = re.search(OPERATOR_PATTERN, text, flags=re.IGNORECASE)
    if not match:
        return None
    return OPERATOR_ALIASES[match.group(0).lower()]


def _candidate_entity(entity: JsonDict) -> JsonDict:
    return {
        "mention": entity.get("mention"),
        "canonical_name": entity.get("canonical_name"),
        "type": entity.get("type"),
    }
