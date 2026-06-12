import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from src.entity_dictionary_builder import load_dictionary, load_jsonl, normalize_entity_type, write_jsonl
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

    mention = clean_entity_wrapper(mention)
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
        type="UNKNOWN",
        canonical_name=mention,
        members=[],
        source="rule",
    ).to_dict()


def build_dictionary_index(dictionary: Sequence[JsonDict]) -> Dict[str, JsonDict]:
    """Build a case-insensitive lookup over canonical names and aliases."""

    index: Dict[str, JsonDict] = {}
    for entity in dictionary:
        aliases = [entity.get("canonical_name", "")] + list(entity.get("aliases", []))
        for alias in aliases:
            key = match_key(str(alias))
            if key:
                index[key] = entity
    return index


def normalize_mention_with_dictionary(
    mention: str,
    dictionary_index: Dict[str, JsonDict],
    source: str,
) -> JsonDict | None:
    """Normalize one mention using an external entity dictionary."""

    mention = clean_entity_wrapper(mention)
    entity = dictionary_index.get(match_key(mention))
    if not entity:
        return None

    normalized = {
        "mention": mention,
        "type": normalize_entity_type(entity.get("type", "UNKNOWN")),
        "canonical_name": str(entity.get("canonical_name", mention)),
        "members": list(entity.get("members", [])),
        "source": source,
        "dictionary_match": True,
        "normalization_confidence": 1.0,
    }
    for field_name in ("unit", "component", "description"):
        if entity.get(field_name):
            normalized[field_name] = entity[field_name]
    return normalized


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
    dictionary: Sequence[JsonDict] | None = None,
    dictionary_path: str | Path | None = None,
    unknown_candidates_path: str | Path | None = None,
    requirement_id: str | None = None,
    include_unknown_entities: bool = True,
) -> List[JsonDict]:
    """Normalize rule/NER entities plus mentions discovered from raw text."""

    if dictionary_path:
        dictionary = load_dictionary(Path(dictionary_path))
    uses_external_dictionary = dictionary is not None or dictionary_path is not None
    dictionary_index = build_dictionary_index(dictionary or [])
    normalized: List[JsonDict] = [] if uses_external_dictionary else list(find_known_mentions(text))
    unknown_candidates: List[JsonDict] = []
    for source_name, source_entities in (("rule", rule_entities or []), ("ner", ner_entities or [])):
        for entity in source_entities:
            mention = clean_entity_wrapper(str(entity.get("mention") or entity.get("text") or entity.get("name") or ""))
            if not mention:
                continue
            item = normalize_mention_with_dictionary(mention, dictionary_index, source_name) if dictionary_index else None
            if item is None:
                item = normalize_mention(mention)
                item["type"] = normalize_entity_type(entity.get("type") or item.get("type"))
                if uses_external_dictionary:
                    unknown_candidates.append(
                        build_unknown_candidate(mention, item["type"], source_name, requirement_id=requirement_id)
                    )
                    if not include_unknown_entities:
                        continue
                    item.update(
                        {
                            "dictionary_match": False,
                            "normalization_confidence": 0.4,
                            "need_review": True,
                            "review_reason": "entity was not found in dictionary",
                        }
                    )
            item["source"] = source_name
            normalized.append(item)

    if unknown_candidates_path and unknown_candidates:
        write_unknown_candidates(Path(unknown_candidates_path), unknown_candidates)

    return unique_dicts(normalized, ["mention", "canonical_name", "source"])


def canonical_for_mention(mention: str) -> str:
    """Return the canonical name for a mention."""

    return normalize_mention(mention)["canonical_name"]


def build_unknown_candidate(
    mention: str,
    entity_type: str,
    source: str,
    requirement_id: str | None = None,
) -> JsonDict:
    """Build a pending candidate for a dictionary miss."""

    candidate: JsonDict = {
        "mention": mention,
        "suggested_canonical": "",
        "type": normalize_entity_type(entity_type),
        "status": "pending",
        "source": source,
        "evidence": [],
    }
    if requirement_id:
        candidate["evidence"].append(requirement_id)
    return candidate


def write_unknown_candidates(path: Path, candidates: Sequence[JsonDict]) -> None:
    """Merge unknown candidates into JSONL without duplicating mention/type pairs."""

    existing = load_jsonl(path) if path.exists() else []
    by_key: Dict[tuple[str, str], JsonDict] = {}
    for candidate in existing + list(candidates):
        mention = str(candidate.get("mention", ""))
        entity_type = normalize_entity_type(candidate.get("type", "UNKNOWN"))
        key = (match_key(mention), entity_type)
        if key not in by_key:
            item = dict(candidate)
            item["type"] = entity_type
            item.setdefault("status", "pending")
            item.setdefault("suggested_canonical", "")
            item.setdefault("evidence", [])
            by_key[key] = item
            continue
        target = by_key[key]
        target.setdefault("evidence", [])
        for evidence in candidate.get("evidence", []):
            if evidence not in target["evidence"]:
                target["evidence"].append(evidence)

    write_jsonl(path, by_key.values())


def match_key(value: str) -> str:
    """Normalize text for alias lookup."""

    return re.sub(r"\s+", " ", value.strip().lower())


def clean_entity_wrapper(mention: str) -> str:
    """Remove a non-semantic outer entity wrapper from extractor mentions."""

    stripped = mention.strip()
    if stripped.startswith("{") and stripped.endswith("}"):
        inner = stripped[1:-1].strip()
        if inner and "{" not in inner and "}" not in inner:
            return inner
    return stripped
