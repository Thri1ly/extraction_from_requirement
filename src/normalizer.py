import re
from typing import Dict, Iterable, List

from src.schemas import JsonDict, NormalizedEntity, unique_dicts


VEHICLE_SPEED_MEMBERS = ["S_MAIN_VEHICLE_SPEED", "S_SECONDARY_VEHICLE_SPEED"]


ENTITY_DEFINITIONS: List[Dict[str, object]] = [
    {
        "type": "signal_group",
        "canonical_name": "VehicleSpeedGroup",
        "members": VEHICLE_SPEED_MEMBERS,
        "patterns": [r"\bvehicle speed signals\b", r"\bboth vehicle speed signals\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_VEHICLE_SPEED",
        "members": [],
        "patterns": [r"\bS_VEHICLE_SPEED\b", r"\bvehicle speed\b", r"\bvehicle speed signal\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_MAIN_VEHICLE_SPEED",
        "members": [],
        "patterns": [r"\bS_MAIN_VEHICLE_SPEED\b", r"\bmain vehicle speed\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_SECONDARY_VEHICLE_SPEED",
        "members": [],
        "patterns": [r"\bS_SECONDARY_VEHICLE_SPEED\b", r"\bsecondary vehicle speed\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_ASSIST_TORQUE",
        "members": [],
        "patterns": [r"\bassist torque\b", r"\bS_ASSIST_TORQUE\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_TORQUE_DEMAND",
        "members": [],
        "patterns": [r"\btorque demand\b", r"\bS_TORQUE_DEMAND\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_DRIVER_TORQUE",
        "members": [],
        "patterns": [r"\bDriver Torque\b", r"\bdriver torque\b", r"\bS_DRIVER_TORQUE\b"],
    },
    {
        "type": "signal",
        "canonical_name": "S_COLUMN_TORQUE",
        "members": [],
        "patterns": [r"\bColumn Torque\b", r"\bcolumn torque\b", r"\bS_COLUMN_TORQUE\b"],
    },
    {
        "type": "indicator",
        "canonical_name": "MIL",
        "members": [],
        "patterns": [r"\bMIL\b"],
    },
]


def normalize_mention(mention: str) -> JsonDict:
    """Normalize one natural-language or signal-code mention."""

    for definition in ENTITY_DEFINITIONS:
        for pattern in definition["patterns"]:
            if re.fullmatch(pattern, mention, flags=re.IGNORECASE):
                return NormalizedEntity(
                    mention=mention,
                    type=str(definition["type"]),
                    canonical_name=str(definition["canonical_name"]),
                    members=list(definition["members"]),
                    source="rule",
                ).to_dict()
    if mention.upper().startswith("DEM_"):
        return NormalizedEntity(
            mention=mention,
            type="fault",
            canonical_name=mention.upper(),
            members=[],
            source="rule",
        ).to_dict()
    return NormalizedEntity(
        mention=mention,
        type="unknown",
        canonical_name=mention,
        members=[],
        source="rule",
    ).to_dict()


def find_known_mentions(text: str) -> Iterable[JsonDict]:
    """Yield normalized entities found directly in requirement text."""

    for definition in ENTITY_DEFINITIONS:
        for pattern in definition["patterns"]:
            for match in re.finditer(pattern, text, flags=re.IGNORECASE):
                yield NormalizedEntity(
                    mention=match.group(0),
                    type=str(definition["type"]),
                    canonical_name=str(definition["canonical_name"]),
                    members=list(definition["members"]),
                    source="rule",
                ).to_dict()

    for match in re.finditer(r"\bDEM_[A-Z0-9_]+\b", text):
        yield NormalizedEntity(
            mention=match.group(0),
            type="fault",
            canonical_name=match.group(0),
            members=[],
            source="rule",
        ).to_dict()


def normalize_entities(
    text: str,
    rule_entities: List[JsonDict] | None = None,
    ner_entities: List[JsonDict] | None = None,
) -> List[JsonDict]:
    """Normalize rule/NER entities plus mentions discovered from raw text."""

    normalized: List[JsonDict] = list(find_known_mentions(text))
    for source_name, source_entities in (("rule", rule_entities or []), ("ner", ner_entities or [])):
        for entity in source_entities:
            mention = str(entity.get("mention") or entity.get("text") or entity.get("name") or "")
            if not mention:
                continue
            item = normalize_mention(mention)
            item["source"] = source_name
            normalized.append(item)

    return unique_dicts(normalized, ["mention", "canonical_name", "source"])


def canonical_for_mention(mention: str) -> str:
    """Return the canonical name for a mention."""

    return normalize_mention(mention)["canonical_name"]
