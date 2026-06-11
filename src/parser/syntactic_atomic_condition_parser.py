import re
from typing import Callable, List

from src.parser.atomic_condition_parser import (
    OPERATOR_ALIASES,
    VALUE_ALIASES,
    VALUE_UNIT_PATTERN,
    parse_atomic_conditions as legacy_parse_atomic_conditions,
    parse_condition_line as legacy_parse_condition_line,
)
from src.schemas import JsonDict, number_value


SUPPORTED_ENTITY_TYPES = {"SIGNAL", "STATE", "VALUE", "PARAMETER"}
RELATION_PATTERN = re.compile(
    r"\b(?:is|are|be|shall\s+be|should\s+be|must\s+be|become|becomes|remain|remains)\b",
    flags=re.IGNORECASE,
)


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
    right_entities = _right_relation_entities(placeholder_map)

    conditions: List[JsonDict] = []
    conditions.extend(_parse_single_signal_multi_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_multi_signal_single_right(text, placeholder_text, signals, right_entities, placeholder_map))
    conditions.extend(_parse_single_signal_single_right(text, placeholder_text, signals, right_entities, placeholder_map))
    return conditions


def build_syntax_analysis(text: str, normalized_entities: List[JsonDict]) -> JsonDict:
    """Replace known entities with placeholders and attach optional local spaCy syntax info."""

    placeholder_text, placeholder_map = _placeholderize_entities(text, normalized_entities)
    return {
        "placeholder_text": placeholder_text,
        "placeholder_map": placeholder_map,
        "syntax_engine": _available_syntax_engine(),
        "syntax_tokens": _spacy_tokens(placeholder_text),
    }


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


def _placeholderize_entities(text: str, entities: List[JsonDict]) -> tuple[str, JsonDict]:
    spans = []
    counters: dict[str, int] = {}
    for entity in entities:
        entity_type = str(entity.get("type", "")).upper()
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            continue
        span = _entity_span(text, entity)
        if not span:
            continue
        counters[entity_type] = counters.get(entity_type, 0) + 1
        placeholder = f"{entity_type}_{counters[entity_type]}"
        spans.append((span[0], span[1], placeholder, entity))

    selected = []
    occupied_until = -1
    for start, end, placeholder, entity in sorted(spans, key=lambda item: (item[0], -(item[1] - item[0]))):
        if start < occupied_until:
            continue
        selected.append((start, end, placeholder, entity))
        occupied_until = end

    pieces = []
    cursor = 0
    placeholder_map: JsonDict = {}
    for start, end, placeholder, entity in selected:
        pieces.append(text[cursor:start])
        pieces.append(placeholder)
        cursor = end
        placeholder_map[placeholder] = {"entity": entity, "span": [start, end], "text": text[start:end]}
    pieces.append(text[cursor:])
    return "".join(pieces), placeholder_map


def _right_relation_entities(placeholder_map: JsonDict) -> List[str]:
    return [
        placeholder
        for placeholder, payload in placeholder_map.items()
        if str(payload["entity"].get("type", "")).upper() in {"STATE", "VALUE", "PARAMETER"}
    ]


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


def _has_relation_between(text: str, left_placeholder: str, right_placeholder: str) -> bool:
    left_end = text.find(left_placeholder) + len(left_placeholder)
    right_start = text.find(right_placeholder)
    if right_start <= left_end:
        return False
    return bool(RELATION_PATTERN.search(text[left_end:right_start]))


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
    aliases = sorted(OPERATOR_ALIASES, key=len, reverse=True)
    for alias in aliases:
        if re.search(rf"(?<!\w){re.escape(alias)}(?!\w)", text, flags=re.IGNORECASE):
            return OPERATOR_ALIASES[alias]
    return None


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
