import json

from src.normalize_requirements_entities import normalize_requirement_rows
from src.normalizer import normalize_entities


def test_normalize_entities_uses_external_dictionary():
    dictionary = [
        {
            "canonical_name": "S_VEHICLE_SPEED",
            "type": "SIGNAL",
            "aliases": ["vehicle speed", "S_VEHICLE_SPEED"],
            "members": [],
            "unit": "kph",
        },
        {
            "canonical_name": "MIL",
            "type": "INDICATOR",
            "aliases": ["MIL"],
            "members": [],
        },
    ]

    normalized = normalize_entities(
        "EPS shall set MIL on when vehicle speed is valid.",
        rule_entities=[{"mention": "vehicle speed", "type": "SIGNAL"}],
        ner_entities=[{"mention": "MIL", "type": "INDICATOR"}],
        dictionary=dictionary,
    )

    by_mention = {entity["mention"]: entity for entity in normalized}
    assert by_mention["vehicle speed"]["canonical_name"] == "S_VEHICLE_SPEED"
    assert by_mention["vehicle speed"]["type"] == "SIGNAL"
    assert by_mention["vehicle speed"]["unit"] == "kph"
    assert by_mention["MIL"]["canonical_name"] == "MIL"
    assert by_mention["MIL"]["type"] == "INDICATOR"


def test_normalize_requirement_rows_only_adds_normalized_entities():
    requirements = [
        {
            "requirement_id": "REQ_1",
            "raw_text": "EPS shall set MIL on when vehicle speed is valid.",
            "rule_entities": [{"mention": "vehicle speed", "type": "SIGNAL"}],
            "ner_entities": [{"mention": "MIL", "type": "INDICATOR"}],
        }
    ]
    dictionary = [
        {
            "canonical_name": "S_VEHICLE_SPEED",
            "type": "SIGNAL",
            "aliases": ["vehicle speed"],
            "members": [],
        },
        {
            "canonical_name": "MIL",
            "type": "INDICATOR",
            "aliases": ["MIL"],
            "members": [],
        },
    ]

    rows = normalize_requirement_rows(requirements, dictionary)

    assert rows[0]["requirement_id"] == "REQ_1"
    assert "parsed_conditions" not in rows[0]
    assert "parsed_actions" not in rows[0]
    assert "coreference" not in rows[0]
    by_mention = {entity["mention"]: entity for entity in rows[0]["normalized_entities"]}
    assert by_mention["vehicle speed"]["canonical_name"] == "S_VEHICLE_SPEED"
    assert by_mention["MIL"]["canonical_name"] == "MIL"


def test_normalize_requirements_writes_unknown_candidates_when_requested(tmp_path):
    requirements = [
        {
            "requirement_id": "REQ_2",
            "raw_text": "EPS shall calculate steering wheel torque.",
            "ner_entities": [{"mention": "steering wheel torque", "type": "SIGNAL"}],
        }
    ]
    candidates_path = tmp_path / "unknown.jsonl"

    normalized = normalize_requirement_rows(requirements, dictionary=[], unknown_candidates_path=candidates_path)

    rows = [json.loads(line) for line in candidates_path.read_text(encoding="utf-8").splitlines()]
    assert normalized[0]["normalized_entities"] == [
        {
            "mention": "steering wheel torque",
            "type": "SIGNAL",
            "canonical_name": "steering wheel torque",
            "members": [],
            "source": "ner",
            "dictionary_match": False,
            "normalization_confidence": 0.4,
            "need_review": True,
            "review_reason": "entity was not found in dictionary",
        }
    ]
    assert rows == [
        {
            "mention": "steering wheel torque",
            "suggested_canonical": "",
            "type": "SIGNAL",
            "status": "pending",
            "source": "ner",
            "evidence": ["REQ_2"],
        }
    ]
