import re
from typing import List

from src.normalizer import canonical_for_mention
from src.schemas import JsonDict, number_value


ACTION_TARGETS = {
    "torque demand": "S_TORQUE_DEMAND",
    "assist torque": "S_ASSIST_TORQUE",
    "Driver Torque": "S_DRIVER_TORQUE",
    "Column Torque": "S_COLUMN_TORQUE",
    "MIL": "MIL",
}

TREND_WORDS = {
    "reduce": "decrease",
    "decrease": "decrease",
    "increase": "increase",
}


def parse_calculate_signal_actions(text: str) -> List[JsonDict]:
    """Parse calculate-signal actions."""

    actions: List[JsonDict] = []
    pattern = re.compile(r"\bcalculate\s+the\s+(?P<target>torque demand|assist torque|S_[A-Z0-9_]+)\b", re.IGNORECASE)
    for match in pattern.finditer(text):
        actions.append(
            {
                "type": "calculate_signal",
                "mention": match.group(0),
                "target_mention": match.group("target"),
                "target": canonical_for_mention(match.group("target")),
                "need_review": False,
            }
        )
    return actions


def parse_limit_value_actions(text: str) -> List[JsonDict]:
    """Parse value limiting actions, including unresolved pronoun targets."""

    actions: List[JsonDict] = []
    pattern = re.compile(
        r"\blimit\s+(?P<target>it|this signal|the signal|torque demand|assist torque|S_[A-Z0-9_]+)\s+to\s+"
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>Nm|kph)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        target_mention = match.group("target")
        needs_coreference = target_mention.lower() in {"it", "this signal", "the signal"}
        actions.append(
            {
                "type": "limit_value",
                "mention": match.group(0),
                "target_mention": target_mention,
                "target": None if needs_coreference else canonical_for_mention(target_mention),
                "value": number_value(match.group("value")),
                "unit": match.group("unit"),
                "needs_coreference": needs_coreference,
                "need_review": False,
            }
        )
    return actions


def parse_adjust_signal_actions(text: str) -> List[JsonDict]:
    """Parse increase/decrease actions on known signals."""

    actions: List[JsonDict] = []
    pattern = re.compile(
        r"\b(?P<trend>reduce|decrease|increase)\s+(?:the\s+)?(?P<target>assist torque|torque demand|S_[A-Z0-9_]+)\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        actions.append(
            {
                "type": "adjust_signal",
                "mention": match.group(0),
                "target_mention": match.group("target"),
                "target": canonical_for_mention(match.group("target")),
                "target_trend": TREND_WORDS[match.group("trend").lower()],
                "need_review": False,
            }
        )
    return actions


def parse_state_transition_actions(text: str) -> List[JsonDict]:
    """Parse transition and return actions between named states."""

    actions: List[JsonDict] = []
    pattern = re.compile(
        r"\b(?:transition|return)\s+from\s+(?P<from>[A-Za-z]+)\s+state\s+to\s+(?P<to>[A-Za-z]+)\s+state\b",
        re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        actions.append(
            {
                "type": "state_transition",
                "mention": match.group(0),
                "from_state": match.group("from"),
                "to_state": match.group("to"),
                "need_review": False,
            }
        )
    return actions


def parse_set_fault_actions(text: str) -> List[JsonDict]:
    """Parse actions that raise a DEM fault."""

    actions: List[JsonDict] = []
    for match in re.finditer(r"\braise\s+the\s+fault\s+(?P<fault>DEM_[A-Z0-9_]+)\b", text):
        actions.append(
            {
                "type": "set_fault",
                "mention": match.group(0),
                "target_mention": match.group("fault"),
                "target": match.group("fault"),
                "expected_state": "Active",
                "need_review": False,
            }
        )
    return actions


def parse_indicator_actions(text: str) -> List[JsonDict]:
    """Parse indicator set/clear actions for MIL."""

    actions: List[JsonDict] = []
    for match in re.finditer(r"\bset\s+the\s+(?P<target>MIL)\s+(?P<state>on|off)\b", text, flags=re.IGNORECASE):
        actions.append(
            {
                "type": "set_indicator",
                "mention": match.group(0),
                "target_mention": match.group("target"),
                "target": canonical_for_mention(match.group("target")),
                "expected_state": match.group("state").title(),
                "need_review": False,
            }
        )
    for match in re.finditer(r"\bclear\s+the\s+(?P<target>MIL)\b", text, flags=re.IGNORECASE):
        actions.append(
            {
                "type": "clear_indicator",
                "mention": match.group(0),
                "target_mention": match.group("target"),
                "target": canonical_for_mention(match.group("target")),
                "expected_state": "Off",
                "need_review": False,
            }
        )
    return actions


def parse_actions(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse Layer5 action objects from a requirement sentence."""

    del normalized_entities
    actions: List[JsonDict] = []
    actions.extend(parse_calculate_signal_actions(text))
    actions.extend(parse_limit_value_actions(text))
    actions.extend(parse_adjust_signal_actions(text))
    actions.extend(parse_state_transition_actions(text))
    actions.extend(parse_set_fault_actions(text))
    actions.extend(parse_indicator_actions(text))
    if not actions:
        return [{"type": "unparsed_action", "mention": text, "need_review": True}]
    return actions
