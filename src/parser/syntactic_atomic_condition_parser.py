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


SUPPORTED_ENTITY_TYPES = {"SIGNAL", "STATE", "VALUE", "PARAMETER", "COMPONENT", "FAULT", "FEATURE", "ACTION"}
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

    normalized_entities = normalized_entities or []
    parsed = parse_syntactic_atomic_conditions(text, normalized_entities)
    if parsed:
        return parsed[0]
    legacy = legacy_parse_condition_line(text, normalized_entities)
    if legacy.get("type") in {"unparsed_condition", "syntactic_fallback_condition"}:
        return build_syntactic_fallback_condition(text, normalized_entities)
    return legacy


def parse_syntactic_atomic_conditions(text: str, normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Extract simple subject-predicate relations from placeholderized entity syntax."""

    if not normalized_entities:
        return []

    normalized_entities = _augment_entities_with_enum_value_state(text, normalized_entities)
    analysis = build_syntax_analysis(text, normalized_entities)
    placeholder_text = str(analysis["placeholder_text"])
    placeholder_map = analysis["placeholder_map"]
    signals = _placeholders_by_type(placeholder_map, "SIGNAL")
    components = _placeholders_by_type(placeholder_map, "COMPONENT")
    faults = _placeholders_by_type(placeholder_map, "FAULT")
    features = _placeholders_by_type(placeholder_map, "FEATURE")
    actions = _placeholders_by_type(placeholder_map, "ACTION")
    right_entities = _right_relation_entities(placeholder_map)

    conditions: List[JsonDict] = []
    conditions.extend(_parse_fault_in_component_condition(text, placeholder_text, faults, components, placeholder_map))
    conditions.extend(_parse_quantified_component_member_state(text, placeholder_text, components, right_entities, placeholder_map))
    conditions.extend(_parse_component_state_condition(text, placeholder_text, components, right_entities, placeholder_map))
    conditions.extend(_parse_feature_state_condition(text, placeholder_text, features, right_entities, placeholder_map))
    conditions.extend(_parse_feature_action_condition(text, placeholder_text, features, actions, placeholder_map))
    conditions.extend(_parse_signal_action_condition(text, placeholder_text, signals, actions, components, placeholder_map))
    conditions.extend(_parse_parenthesized_event_with_signal_comparison(text, placeholder_text, signals, components, placeholder_map))
    conditions.extend(_parse_parenthesized_signal_state_with_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_explicit_parenthesized_condition(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_parenthesized_independent_signal_conditions(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_parenthesized_signal_trend_condition(text, placeholder_text, signals, placeholder_map))
    conditions.extend(_parse_bracketed_range_condition(text, placeholder_text, signals, placeholder_map))
    conditions.extend(_parse_signal_value_state_clause_group(text, placeholder_text, signals, placeholder_map))
    conditions.extend(_parse_quantified_signal_member_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_parenthesized_signal_state_without_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_state_without_predicate(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_right_duration_qualifier(text, placeholder_text, signals, right_entities, placeholder_map))
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
    state_modifier = _component_state_modifier_between(placeholder_text, component_placeholder, state_placeholder)
    if state_modifier is None:
        return []

    condition = _condition_for_component_state(
        original_text,
        placeholder_map[component_placeholder]["entity"],
        placeholder_map[state_placeholder]["entity"],
        state_modifier=state_modifier,
    )
    if not condition:
        return []
    condition["parser"] = "syntactic"
    return [condition]


def _parse_feature_state_condition(
    original_text: str,
    placeholder_text: str,
    features: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(features) != 1 or len(right_entities) != 1:
        return []

    state_placeholder = right_entities[0]
    if str(placeholder_map[state_placeholder]["entity"].get("type", "")).upper() != "STATE":
        return []
    feature_placeholder = features[0]
    if not _has_relation_or_operator_between(placeholder_text, feature_placeholder, state_placeholder):
        return []

    feature = placeholder_map[feature_placeholder]["entity"]
    state = placeholder_map[state_placeholder]["entity"]
    operator = _operator_for_right_placeholder(placeholder_text, feature_placeholder, [state_placeholder], state_placeholder)
    return [
        {
            "type": "feature_state_condition",
            "mention": f"{_display_entity_mention(original_text, feature)} {operator} {state.get('canonical_name') or state.get('mention')}",
            "feature": str(feature.get("canonical_name") or feature.get("mention")),
            "operator": operator,
            "required_state": str(state.get("canonical_name") or state.get("mention")),
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_feature_action_condition(
    original_text: str,
    placeholder_text: str,
    features: List[str],
    actions: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(features) != 1 or len(actions) != 1:
        return []
    feature_placeholder = features[0]
    action_placeholder = actions[0]
    if placeholder_text.find(action_placeholder) <= placeholder_text.find(feature_placeholder):
        return []

    feature = placeholder_map[feature_placeholder]["entity"]
    action = placeholder_map[action_placeholder]["entity"]
    return [
        {
            "type": "feature_action_condition",
            "mention": f"{_display_entity_mention(original_text, feature)} -> {action.get('canonical_name') or action.get('mention')}",
            "feature": str(feature.get("canonical_name") or feature.get("mention")),
            "action": str(action.get("canonical_name") or action.get("mention")),
            "parser": "syntactic",
            "need_review": False,
        }
    ]


def _parse_signal_action_condition(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    actions: List[str],
    components: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1 or len(actions) != 1:
        return []
    signal_placeholder = signals[0]
    action_placeholder = actions[0]
    if placeholder_text.find(action_placeholder) <= placeholder_text.find(signal_placeholder):
        return []

    signal = placeholder_map[signal_placeholder]["entity"]
    action = placeholder_map[action_placeholder]["entity"]
    condition: JsonDict = {
        "type": "signal_action_condition",
        "mention": f"{_display_entity_mention(original_text, signal)} -> {action.get('canonical_name') or action.get('mention')}",
        "signal": str(signal.get("canonical_name") or signal.get("mention")),
        "action": str(action.get("canonical_name") or action.get("mention")),
        "parser": "syntactic",
        "need_review": False,
    }
    if len(components) == 1:
        component = placeholder_map[components[0]]["entity"]
        condition["component"] = str(component.get("canonical_name") or component.get("mention"))
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


def _parse_parenthesized_event_with_signal_comparison(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    components: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) < 2 or len(components) != 1:
        return []

    for match in re.finditer(r"\((?P<body>[^()]*)\)", placeholder_text):
        outer_text = placeholder_text[: match.start()].strip()
        body = match.group("body").strip()
        outer_nlp_condition = _nlp_condition_from_segment(
            original_text.split("(", 1)[0].strip(),
            outer_text,
            placeholder_map,
        )
        if not outer_nlp_condition:
            continue
        body_condition = _signal_comparison_condition_from_segment(original_text, body, signals, placeholder_map)
        if not body_condition:
            continue

        need_review = bool(outer_nlp_condition.get("need_review") or body_condition.get("need_review"))
        return [
            {
                "type": "condition_group",
                "logic": "AND",
                "mention": original_text,
                "children": [outer_nlp_condition, body_condition],
                "parser": "syntactic",
                "need_review": need_review,
            }
        ]

    return []


def _nlp_condition_from_segment(
    original_segment_text: str,
    segment_text: str,
    placeholder_map: JsonDict,
) -> JsonDict | None:
    segment_text = segment_text.strip()
    original_segment_text = original_segment_text.strip()
    if not segment_text or not original_segment_text:
        return None

    detected = _detected_nlp_condition_from_segment(original_segment_text, segment_text, placeholder_map)
    if detected:
        return detected

    return _raw_nlp_condition_from_segment(original_segment_text, segment_text, placeholder_map)


def _detected_nlp_condition_from_segment(
    original_segment_text: str,
    segment_text: str,
    placeholder_map: JsonDict,
) -> JsonDict | None:
    entity_placeholders = [placeholder for placeholder in placeholder_map if placeholder in segment_text]
    component_placeholders = [
        placeholder
        for placeholder in entity_placeholders
        if str(placeholder_map[placeholder]["entity"].get("type", "")).upper() == "COMPONENT"
    ]
    subject_placeholders = [placeholder for placeholder in entity_placeholders if placeholder not in component_placeholders]
    if len(subject_placeholders) != 1 or len(component_placeholders) != 1:
        return None

    subject_placeholder = subject_placeholders[0]
    location_placeholder = component_placeholders[0]
    match = re.fullmatch(
        rf"\s*(?:(?P<determiner>a|an|the)\s+)?{re.escape(subject_placeholder)}\s+"
        rf"(?:is|are|was|were|be|been|being)\s+detected\s+"
        rf"(?P<location_relation>in)\s+{re.escape(location_placeholder)}\s*",
        segment_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None

    subject = placeholder_map[subject_placeholder]["entity"]
    location = placeholder_map[location_placeholder]["entity"]
    subject_chunk = _semantic_entity_chunk("subject", original_segment_text, subject)
    location_chunk = _semantic_entity_chunk("location", original_segment_text, location)
    location_chunk["relation"] = match.group("location_relation").lower()
    location_field = {key: value for key, value in location_chunk.items() if key != "role"}
    condition: JsonDict = {
        "type": "nlp_condition",
        "mention": original_segment_text,
        "text": original_segment_text,
        "subject": str(subject.get("canonical_name") or subject.get("mention")),
        "predicate": "detect",
        "voice": "passive",
        "locations": [location_field],
        "semantic_chunks": [],
        "known_entities": [_fallback_known_entity(subject), _fallback_known_entity(location)],
        "syntax_source": _nlp_syntax_source(original_segment_text),
        "parser": "syntactic",
        "need_review": False,
    }
    determiner = match.group("determiner")
    if determiner:
        condition["semantic_chunks"].append({"role": "determiner", "text": determiner.lower()})
    condition["semantic_chunks"].extend(
        [
            subject_chunk,
            {"role": "predicate", "text": "is detected", "lemma": "detect", "voice": "passive"},
            location_chunk,
        ]
    )
    return condition


def _raw_nlp_condition_from_segment(
    original_segment_text: str,
    segment_text: str,
    placeholder_map: JsonDict,
) -> JsonDict:
    known_entities = [
        _fallback_known_entity(payload["entity"])
        for placeholder, payload in placeholder_map.items()
        if placeholder in segment_text
    ]
    condition: JsonDict = {
        "type": "nlp_condition",
        "mention": original_segment_text,
        "text": original_segment_text,
        "predicate": _fallback_predicate(original_segment_text),
        "semantic_chunks": [{"role": "raw_text", "text": original_segment_text}],
        "known_entities": known_entities,
        "syntax_source": _nlp_syntax_source(original_segment_text),
        "parser": "syntactic",
        "need_review": True,
        "review_reason": _nlp_review_reason(original_segment_text),
    }
    quantifier = _fallback_quantifier(original_segment_text)
    if quantifier:
        condition["quantifier"] = quantifier
    return condition


def _signal_comparison_condition_from_segment(
    original_text: str,
    segment_text: str,
    signals: List[str],
    placeholder_map: JsonDict,
) -> JsonDict | None:
    segment_signals = _ordered_placeholders(segment_text, [signal for signal in signals if signal in segment_text])
    if len(segment_signals) != 2:
        return None

    match = re.search(
        rf"\b(?P<left>{re.escape(segment_signals[0])})\s*"
        rf"(?P<operator>>=|<=|==|!=|>|<|=)\s*"
        rf"(?P<right>{re.escape(segment_signals[1])})\b",
        segment_text,
    )
    if not match:
        return None

    left = placeholder_map[match.group("left")]["entity"]
    right = placeholder_map[match.group("right")]["entity"]
    left_name = str(left.get("canonical_name") or left.get("mention"))
    right_name = str(right.get("canonical_name") or right.get("mention"))
    operator = _operator_from_text(match.group("operator")) or match.group("operator")
    condition: JsonDict = {
        "type": "signal_comparison_condition",
        "mention": f"{_display_entity_mention(original_text, left)} {operator} {_display_entity_mention(original_text, right)}",
        "left_signal": left_name,
        "operator": operator,
        "right_signal": right_name,
        "qualifiers": [],
        "need_review": False,
    }
    duration = _duration_qualifier_from_placeholder_text(original_text, segment_text, placeholder_map)
    if duration:
        condition["qualifiers"].append(duration["qualifier"])
    return condition


def build_syntax_analysis(text: str, normalized_entities: List[JsonDict]) -> JsonDict:
    """Replace known entities with placeholders and attach optional local spaCy syntax info."""

    normalized_entities = _augment_entities_with_enum_value_state(text, normalized_entities)
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


def _parse_parenthesized_independent_signal_conditions(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    """Parse separate outer and parenthesized signal predicates without cross-pairing."""

    if len(signals) < 2:
        return []

    for match in re.finditer(r"\((?P<body>[^()]*)\)", placeholder_text):
        outer_text = placeholder_text[: match.start()]
        body = match.group("body")
        outer_condition = _signal_condition_from_segment(original_text, outer_text, signals, right_entities, placeholder_map)
        body_condition = _signal_condition_from_segment(original_text, body, signals, right_entities, placeholder_map)
        if not outer_condition or not body_condition:
            continue
        if outer_condition.get("signal") == body_condition.get("signal"):
            continue

        need_review = bool(outer_condition.get("need_review") or body_condition.get("need_review"))
        result: JsonDict = {
            "type": "condition_group",
            "logic": "AND",
            "mention": original_text,
            "children": [outer_condition, body_condition],
            "parser": "syntactic",
            "need_review": need_review,
        }
        if need_review:
            result["review_reason"] = "one or more states inferred from syntax"
        return [result]

    return []


def _parse_parenthesized_signal_trend_condition(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 2:
        return []

    match = re.search(
        r"\b(?P<outer>SIGNAL_\d+)\s*\(\s*(?P<inner>SIGNAL_\d+)\s*\)\s+"
        r"(?P<trend>increases?|decreases?|rises?|falls?)\b",
        placeholder_text,
        flags=re.IGNORECASE,
    )
    if not match:
        return []

    trend = match.group("trend").lower()
    trend_value = "decrease" if trend.startswith(("decreas", "fall")) else "increase"
    inner = placeholder_map[match.group("inner")]["entity"]
    outer = placeholder_map[match.group("outer")]["entity"]
    return [
        {
            "type": "signal_trend_condition",
            "mention": f"{_display_entity_mention(original_text, inner)} {match.group('trend')}",
            "signal": str(inner.get("canonical_name") or inner.get("mention")),
            "trend": trend_value,
            "context_signal": str(outer.get("canonical_name") or outer.get("mention")),
            "parser": "syntactic",
            "need_review": False,
        }
    ]


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
    state = placeholder_map[clause["state"]]["entity"]
    operator = _operator_for_right_placeholder(placeholder_text, clause["signal"], [clause["value"]], clause["value"])
    state_condition = _condition_for_right_entity(original_text, signal, state, operator=operator)
    if not state_condition:
        return None
    return state_condition


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


def _parse_single_signal_right_duration_qualifier(
    original_text: str,
    placeholder_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> List[JsonDict]:
    if len(signals) != 1:
        return []

    duration = _duration_qualifier_from_placeholder_text(original_text, placeholder_text, placeholder_map)
    if not duration:
        return []

    duration_placeholder = str(duration["placeholder"])
    comparison_rights = [right for right in right_entities if right != duration_placeholder]
    if len(comparison_rights) != 1:
        return []
    signal_placeholder = signals[0]
    right_placeholder = comparison_rights[0]
    if not _has_relation_or_operator_between(placeholder_text, signal_placeholder, right_placeholder):
        return []

    duration_start = placeholder_text.find(duration_placeholder)
    right_end = placeholder_text.find(right_placeholder) + len(right_placeholder)
    if duration_start <= right_end:
        return []

    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[signal_placeholder]["entity"],
        placeholder_map[right_placeholder]["entity"],
        operator=_operator_for_right_placeholder(placeholder_text, signal_placeholder, [right_placeholder], right_placeholder),
    )
    if not condition:
        return []
    condition["qualifiers"] = [duration["qualifier"]]
    condition["parser"] = "syntactic"
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
    inferred_states = _inferred_state_items_after_right_list(placeholder_text, ordered_rights)
    first_operator = _operator_for_right_placeholder(placeholder_text, signals[0], ordered_rights, ordered_rights[0])
    children.extend(
        _condition_for_right_entity(
            original_text,
            signal,
            _synthetic_state_entity(state_text),
            operator=first_operator,
        )
        for state_text in inferred_states
    )
    if any(child is None for child in children):
        return []
    need_review = any(bool(child.get("need_review")) for child in children)

    result: JsonDict = {
        "type": "condition_group",
        "logic": logic,
        "mention": original_text,
        "children": children,
        "parser": "syntactic",
        "need_review": need_review,
    }
    if need_review:
        result["review_reason"] = "one or more states inferred from syntax"
    return [result]


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


def _signal_condition_from_segment(
    original_text: str,
    segment_text: str,
    signals: List[str],
    right_entities: List[str],
    placeholder_map: JsonDict,
) -> JsonDict | None:
    segment_signals = [signal for signal in signals if signal in segment_text]
    if len(segment_signals) != 1:
        return None

    signal_placeholder = segment_signals[0]
    segment_rights = [right for right in right_entities if right in segment_text]
    if len(segment_rights) > 1:
        return None

    if len(segment_rights) == 1:
        right_placeholder = segment_rights[0]
        if not _has_relation_or_operator_between(segment_text, signal_placeholder, right_placeholder):
            return None
        condition = _condition_for_right_entity(
            original_text,
            placeholder_map[signal_placeholder]["entity"],
            placeholder_map[right_placeholder]["entity"],
            operator=_operator_for_right_placeholder(segment_text, signal_placeholder, [right_placeholder], right_placeholder),
        )
        return condition

    inferred = _inferred_state_after_signal(segment_text, signal_placeholder)
    if not inferred:
        return None
    state_entity = _synthetic_state_entity(inferred["state"])
    condition = _condition_for_right_entity(
        original_text,
        placeholder_map[signal_placeholder]["entity"],
        state_entity,
        operator=str(inferred["operator"]),
    )
    if not condition:
        return None
    return condition


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
        inferred_from_syntax = bool(right_entity.get("inferred_from_syntax") or right_entity.get("inferred_from_enum"))
        condition: JsonDict = {
            "type": "signal_state_condition",
            "mention": f"{signal_mention} {operator} {required_state}",
            "signal": signal_name,
            "operator": operator,
            "required_state": required_state,
            "need_review": inferred_from_syntax,
        }
        if inferred_from_syntax:
            condition["review_reason"] = str(right_entity.get("review_reason") or "state inferred from syntax")
            condition["confidence"] = {"overall": 0.7, "structure": 0.8, "normalization": 0.4}
        if right_entity.get("enum_value"):
            condition["enum_value"] = str(right_entity["enum_value"])
        return condition

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
    state_modifier: str = "",
) -> JsonDict | None:
    if str(state.get("type", "")).upper() != "STATE":
        return None

    component_name = str(component.get("canonical_name") or component.get("mention"))
    component_mention = _display_entity_mention(original_text, component)
    required_state = str(state.get("canonical_name") or state.get("mention"))
    state_phrase = f"{state_modifier} {required_state}".strip()
    condition: JsonDict = {
        "type": "component_state_condition",
        "mention": f"{component_mention} == {state_phrase}",
        "component": component_name,
        "operator": "==",
        "required_state": required_state,
        "need_review": False,
    }
    if state_modifier:
        condition["state_phrase"] = state_phrase
        condition["state_modifier"] = state_modifier
    return condition


def _placeholderize_entities(text: str, entities: List[JsonDict]) -> tuple[str, JsonDict]:
    spans = []
    for entity in entities:
        entity = _clean_entity_for_parsing(entity)
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


def _clean_entity_for_parsing(entity: JsonDict) -> JsonDict:
    cleaned = dict(entity)
    for field_name in ("mention", "canonical_name"):
        if field_name in cleaned:
            cleaned[field_name] = _clean_unbalanced_entity_wrapper(str(cleaned[field_name]))
    return cleaned


def _clean_unbalanced_entity_wrapper(text: str) -> str:
    cleaned = text.strip()
    pairs = {"(": ")", "[": "]", "{": "}"}
    for left, right in pairs.items():
        if cleaned.startswith(left) and not cleaned.endswith(right):
            cleaned = cleaned[1:].strip()
        if cleaned.endswith(right) and not cleaned.startswith(left):
            cleaned = cleaned[:-1].strip()
    return cleaned


def _augment_entities_with_enum_value_state(text: str, entities: List[JsonDict]) -> List[JsonDict]:
    augmented = [dict(entity) for entity in entities]
    existing_spans = {
        (str(entity.get("mention", "")).strip().lower(), str(entity.get("type", "")).upper())
        for entity in augmented
    }
    for match in re.finditer(r"\b(?P<value>0x[0-9a-f]+)\s*:\s*(?P<state>[A-Za-z][A-Za-z0-9_ /-]*)", text, flags=re.IGNORECASE):
        value = match.group("value")
        state = match.group("state").strip().strip("\"'")
        state = re.split(r"[\")\];,]", state, maxsplit=1)[0].strip()
        if (value.lower(), "VALUE") not in existing_spans:
            augmented.append(
                {
                    "mention": value,
                    "type": "VALUE",
                    "canonical_name": value,
                    "inferred_from_enum": True,
                    "need_review": True,
                }
            )
            existing_spans.add((value.lower(), "VALUE"))
        if state and (state.lower(), "STATE") not in existing_spans:
            augmented.append(
                {
                    "mention": state,
                    "type": "STATE",
                    "canonical_name": state,
                    "inferred_from_enum": True,
                    "need_review": True,
                    "review_reason": "state inferred from enum label",
                    "enum_value": value,
                }
            )
            existing_spans.add((state.lower(), "STATE"))
    return augmented


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


def _inferred_state_items_after_right_list(text: str, ordered_rights: List[str]) -> List[str]:
    if len(ordered_rights) < 2:
        return []
    inferred: List[str] = []
    last_right = ordered_rights[-1]
    cursor = text.find(last_right) + len(last_right)
    tail = text[cursor:]
    for match in re.finditer(r"\b(?:or|and/or|and)\b|,", tail, flags=re.IGNORECASE):
        candidate = tail[match.end() :].strip()
        if not candidate:
            continue
        candidate = re.split(r"\b(?:or|and/or|and)\b|,", candidate, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        candidate = _clean_inferred_state_text(candidate)
        if _is_safe_inferred_state_text(candidate):
            inferred.append(candidate)
    return inferred


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
    return _component_state_modifier_between(text, component_placeholder, state_placeholder) is not None


def _component_state_modifier_between(text: str, component_placeholder: str, state_placeholder: str) -> str | None:
    component_end = text.find(component_placeholder) + len(component_placeholder)
    state_start = text.find(state_placeholder)
    if state_start <= component_end:
        return None
    separator = text[component_end:state_start]
    match = re.search(
        rf"^\s*(?:{RELATION_PATTERN.pattern}|in)\b(?P<tail>.*?)$",
        separator,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    tail = re.sub(r"^\s*in\b", "", match.group("tail"), flags=re.IGNORECASE).strip()
    return tail


def _has_relation_or_operator_between(text: str, left_placeholder: str, right_placeholder: str) -> bool:
    left_end = text.find(left_placeholder) + len(left_placeholder)
    right_start = text.find(right_placeholder)
    if right_start <= left_end:
        return False
    separator = text[left_end:right_start]
    return bool(RELATION_PATTERN.search(separator) or _operator_from_text(separator) or re.search(r"\bin\s*$", separator, flags=re.IGNORECASE))


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


def _inferred_state_after_signal(text: str, signal_placeholder: str) -> JsonDict | None:
    signal_end = text.find(signal_placeholder) + len(signal_placeholder)
    if signal_end < len(signal_placeholder):
        return None
    tail = text[signal_end:]
    match = _state_relation_tail_match(tail)
    if not match:
        return None
    operator_text = match.group("operator")
    state_text = _clean_inferred_state_text(match.group("state"))
    operator = _operator_from_text(operator_text) or "=="
    if state_text.lower().startswith("not "):
        operator = "!="
        state_text = state_text[4:].strip()
    state_text = _strip_leading_operator_words(state_text)
    if not _is_safe_inferred_state_text(state_text):
        return None
    return {"state": state_text, "operator": operator}


def _state_relation_tail_match(text: str) -> re.Match[str] | None:
    operator_aliases = [
        "not equal to",
        "not equals",
        "not equal",
        "equal to",
        "equals",
        "==",
        "!=",
        "=",
    ]
    operator_pattern = "|".join(re.escape(alias) for alias in operator_aliases)
    return re.search(
        rf"^\s*(?P<operator>{operator_pattern}|{RELATION_PATTERN.pattern}|in)\s+(?P<state>.+?)\s*$",
        text,
        flags=re.IGNORECASE,
    )


def _clean_inferred_state_text(text: str) -> str:
    cleaned = text.strip().strip("\"'")
    cleaned = re.split(r"\s*(?:\)|;)\s*$", cleaned)[0].strip()
    return cleaned


def _strip_leading_operator_words(text: str) -> str:
    cleaned = text.strip()
    for pattern in (
        r"^(?:equal\s+to|equals?)\s+",
        r"^(?:be|in)\s+",
    ):
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE).strip()
    return cleaned


def _is_safe_inferred_state_text(text: str) -> bool:
    if not text or re.search(r"\b(?:and|or|and/or)\b", text, flags=re.IGNORECASE):
        return False
    if re.fullmatch(r"[-+]?\d+(?:\.\d+)?(?:\s*[A-Za-z/%]+)?", text):
        return False
    if re.fullmatch(r"P_[A-Z0-9_]+", text, flags=re.IGNORECASE):
        return False
    return bool(re.search(r"[A-Za-z]", text))


def _synthetic_state_entity(state_text: str) -> JsonDict:
    return {
        "mention": state_text,
        "type": "STATE",
        "canonical_name": state_text,
        "dictionary_match": False,
        "normalization_confidence": 0.4,
        "inferred_from_syntax": True,
        "need_review": True,
        "review_reason": "state inferred from syntax",
    }


def _duration_qualifier_from_placeholder_text(
    original_text: str,
    placeholder_text: str,
    placeholder_map: JsonDict,
) -> JsonDict | None:
    for parameter_placeholder in _placeholders_by_type(placeholder_map, "PARAMETER"):
        operator = _duration_operator_from_text(placeholder_text, parameter_placeholder)
        if operator is None and not _has_duration_phrase_without_operator(placeholder_text, parameter_placeholder):
            continue
        qualifier = _duration_qualifier_from_text(
            original_text,
            placeholder_map[parameter_placeholder]["entity"],
        )
        if not qualifier:
            continue
        return {"placeholder": parameter_placeholder, "qualifier": qualifier}
    return None


def _duration_qualifier_from_text(text: str, parameter: JsonDict) -> JsonDict | None:
    parameter_name = str(parameter.get("canonical_name") or parameter.get("mention"))
    for field_name in ("mention", "canonical_name"):
        value = str(parameter.get(field_name, "")).strip()
        if not value:
            continue
        for pattern, operator in _duration_qualifier_patterns(re.escape(value)):
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            qualifier: JsonDict = {
                "type": "duration",
                "mention": match.group(0),
                "parameter": parameter_name,
            }
            if operator:
                qualifier["operator"] = operator
            return qualifier
    return None


def _duration_operator_from_text(text: str, parameter_pattern: str) -> str | None:
    for pattern, operator in _duration_qualifier_patterns(re.escape(parameter_pattern)):
        if operator and re.search(pattern, text, flags=re.IGNORECASE):
            return operator
    return None


def _has_duration_phrase_without_operator(text: str, parameter_pattern: str) -> bool:
    return any(
        operator is None and re.search(pattern, text, flags=re.IGNORECASE)
        for pattern, operator in _duration_qualifier_patterns(re.escape(parameter_pattern))
    )


def _duration_qualifier_patterns(parameter_pattern: str) -> List[tuple[str, str | None]]:
    return [
        (rf"\bwithin\s+{parameter_pattern}\b", "<="),
        (rf"\bfor\s+(?:more|longer)\s+than\s+{parameter_pattern}\b", ">"),
        (rf"\bexceeds?\s+(?:the\s+)?{parameter_pattern}\b", ">"),
        (rf"\bexceeding\s+(?:the\s+)?{parameter_pattern}\b", ">"),
        (rf"\bfor\s+[^()]*?\s+of\s+at\s+least\s+{parameter_pattern}\b", ">="),
        (rf"\bfor\s+[^()]*?\s+of\s+no\s+less\s+than\s+{parameter_pattern}\b", ">="),
        (rf"\bfor\s+[^()]*?\s+of\s+at\s+most\s+{parameter_pattern}\b", "<="),
        (rf"\bfor\s+[^()]*?\s+of\s+no\s+more\s+than\s+{parameter_pattern}\b", "<="),
        (rf"\bfor\s+[^()]*?\s+of\s+(?:greater|more|longer)\s+than\s+{parameter_pattern}\b", ">"),
        (rf"\bfor\s+[^()]*?\s+of\s+(?:less|shorter)\s+than\s+{parameter_pattern}\b", "<"),
        (rf"\bfor\s+[^()]*?\s+of\s+{parameter_pattern}\b", None),
        (rf"\bfor\s+(?:a|the)?\s*period\s+of\s+{parameter_pattern}\b", None),
        (rf"\bfor\s+(?:a|the)?\s*duration(?:\s+time)?\s+of\s+{parameter_pattern}\b", None),
        (rf"\bfor\s+(?:a|the)?\s*duration(?:\s+time)?\s+greater\s+than\s+{parameter_pattern}\b", ">"),
        (rf"\bfor\s+(?:a|the)?\s*duration(?:\s+time)?\s+less\s+than\s+{parameter_pattern}\b", "<"),
        (rf"\bfor\s+>=\s*{parameter_pattern}\b", ">="),
        (rf"\bfor\s+>\s*{parameter_pattern}\b", ">"),
        (rf"\bfor\s+<=\s*{parameter_pattern}\b", "<="),
        (rf"\bfor\s+<\s*{parameter_pattern}\b", "<"),
    ]


def build_syntactic_fallback_condition(text: str, normalized_entities: List[JsonDict] | None = None) -> JsonDict:
    """Return a reviewable fallback condition instead of dropping an unparsable sentence."""

    normalized_entities = normalized_entities or []
    analysis = build_syntax_analysis(text, normalized_entities)
    placeholder_text = str(analysis["placeholder_text"])
    placeholder_map = analysis["placeholder_map"]
    if _should_use_nlp_fallback(text):
        return _raw_nlp_condition_from_segment(text, placeholder_text, placeholder_map)

    known_entities = [_fallback_known_entity(entity) for entity in normalized_entities]
    condition: JsonDict = {
        "type": "syntactic_fallback_condition",
        "mention": text,
        "predicate": _fallback_predicate(text),
        "unknown_candidates": _fallback_unknown_candidates(text, normalized_entities),
        "known_entities": known_entities,
        "parser": "syntactic_fallback",
        "need_review": True,
        "review_reason": "condition parsed by syntactic fallback",
        "confidence": {"overall": 0.25, "structure": 0.45, "normalization": 0.25},
    }
    quantifier = _fallback_quantifier(text)
    if quantifier:
        condition["quantifier"] = quantifier
    if placeholder_text and placeholder_text != text:
        condition["placeholder_text"] = placeholder_text
    return condition


def _should_use_nlp_fallback(text: str) -> bool:
    if _operator_from_text(text):
        return False
    return bool(text.strip())


def _nlp_review_reason(text: str) -> str:
    if re.match(r"^\s*(?:in|on|at|from|to|within|without|with)\b", text, flags=re.IGNORECASE):
        return "incomplete natural-language condition"
    return "natural-language condition parsed by nlp fallback"


def _semantic_entity_chunk(role: str, text: str, entity: JsonDict) -> JsonDict:
    chunk: JsonDict = {
        "role": role,
        "text": _display_entity_mention(text, entity),
        "entity_type": str(entity.get("type", "")).upper(),
    }
    if entity.get("canonical_name"):
        chunk["canonical_name"] = str(entity["canonical_name"])
    return chunk


def _nlp_syntax_source(text: str) -> str:
    return "spacy" if _spacy_tokens(text) else "placeholder"


def _fallback_known_entity(entity: JsonDict) -> JsonDict:
    return {
        key: entity[key]
        for key in ("mention", "type", "canonical_name")
        if key in entity
    }


def _fallback_quantifier(text: str) -> str | None:
    if re.search(r"\b(?:both|all)\b", text, flags=re.IGNORECASE):
        return "ALL"
    if re.search(r"\b(?:one|any)\b", text, flags=re.IGNORECASE):
        return "ANY_ONE"
    return None


def _fallback_predicate(text: str) -> str:
    operator = _operator_from_text(text)
    if operator:
        return operator
    predicate_patterns = [
        (r"\brequests?\s+to\s+exit\b", "request_exit"),
        (r"\bexits?\b", "exit"),
        (r"\bsends?\b", "send"),
        (r"\bis\s+set\b", "set"),
        (r"\bincreases?\b", "increase"),
        (r"\bdecreases?\b", "decrease"),
        (r"\benables?\b", "enable"),
        (r"\bdisables?\b", "disable"),
    ]
    for pattern, predicate in predicate_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            return predicate
    return "unknown_relation"


def _fallback_unknown_candidates(text: str, normalized_entities: List[JsonDict]) -> List[str]:
    candidate_text = text
    for entity in normalized_entities:
        for field_name in ("mention", "canonical_name"):
            value = _clean_unbalanced_entity_wrapper(str(entity.get(field_name, "")).strip())
            if value:
                candidate_text = re.sub(rf"(?<!\w){re.escape(value)}(?!\w)", " ", candidate_text, flags=re.IGNORECASE)

    candidate_text = re.sub(
        r"\b(?:both|all|one|any|the|a|an|is|are|be|to|from|than|less|greater|equal|valid|invalid|state\d*)\b",
        " ",
        candidate_text,
        flags=re.IGNORECASE,
    )
    candidate_text = re.sub(r"\b(?:send|sends|request|requests|exit|exits|set|increases?|decreases?)\b", " ", candidate_text, flags=re.IGNORECASE)
    candidates = [
        item.strip(" ,.;:()[]{}\"'")
        for item in re.split(r"\s{2,}|,|;|\band\b|\bor\b", candidate_text, flags=re.IGNORECASE)
        if item.strip(" ,.;:()[]{}\"'")
    ]
    if candidates:
        return candidates
    return [text.strip()] if text.strip() else []


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
