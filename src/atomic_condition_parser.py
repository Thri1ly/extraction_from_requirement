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
SIGNAL_PATTERN = r"S_[A-Z0-9_]+|vehicle speed|Column Torque|Driver Torque|assist torque|torque demand"
VALUE_UNIT_PATTERN = r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>kph|Nm)"


def parse_atomic_conditions(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse all supported atomic condition forms from text."""

    del normalized_entities
    conditions: List[JsonDict] = []
    conditions.extend(parse_state_definition_conditions(text))
    conditions.extend(parse_range_conditions(text))
    conditions.extend(parse_redundant_signal_validity(text))
    conditions.extend(parse_fault_state_conditions(text))
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
        rf"(?P<signal>\|\{{[^}}]+\}}\||abs\{{[^}}]+\}}|absolute\s*\{{[^}}]+\}}|{SIGNAL_PATTERN})"
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
        rf"(?P<expr>(?:\|\{{[^}}]+\}}\||abs\{{[^}}]+\}}|absolute\s*\{{[^}}]+\}}|{SIGNAL_PATTERN})"
        rf"\s+(?:is\s+)?(?:{OPERATOR_PATTERN})\s+\d+(?:\.\d+)?\s*(?:kph|Nm))",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        parsed = _parse_threshold_fragment(match.group("expr"))
        if parsed:
            conditions.append(parsed)
    return unique_dicts(conditions, ["type", "signal", "operator", "value", "unit", "transform"])


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
