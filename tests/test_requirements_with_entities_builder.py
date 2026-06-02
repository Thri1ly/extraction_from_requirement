import json

from src.requirements_with_entities_builder import build_requirements_with_entities


def test_build_requirements_with_entities_merges_by_requirement_id():
    requirements = [
        {"requirement_id": "REQ_1", "raw_text": "Vehicle speed shall be valid."},
        {"requirement_id": "REQ_2", "raw_text": "EPS shall set MIL on."},
    ]
    rule_rows = [
        {"requirement_id": "REQ_2", "entities": [{"mention": "MIL", "type": "indicator"}]},
        {"requirement_id": "REQ_1", "entities": [{"mention": "vehicle speed", "type": "signal"}]},
    ]
    ner_rows = [
        {"requirement_id": "REQ_1", "entities": [{"mention": "Vehicle speed", "type": "SIGNAL"}]},
        {"requirement_id": "REQ_2", "entities": [{"mention": "EPS", "type": "component"}]},
    ]

    merged = build_requirements_with_entities(requirements, rule_rows=rule_rows, ner_rows=ner_rows)

    assert merged[0]["rule_entities"] == [{"mention": "vehicle speed", "type": "SIGNAL"}]
    assert merged[0]["ner_entities"] == [{"mention": "Vehicle speed", "type": "SIGNAL"}]
    assert merged[1]["rule_entities"] == [{"mention": "MIL", "type": "INDICATOR"}]
    assert merged[1]["ner_entities"] == [{"mention": "EPS", "type": "COMPONENT"}]


def test_build_requirements_with_entities_merges_by_row_order_when_no_ids():
    requirements = [
        {"raw_text": "Vehicle speed shall be valid."},
        {"raw_text": "EPS shall set MIL on."},
    ]
    rule_rows = [
        [{"mention": "vehicle speed", "type": "signal"}],
        [{"mention": "MIL", "type": "indicator"}],
    ]

    merged = build_requirements_with_entities(requirements, rule_rows=rule_rows, ner_rows=[])

    assert merged[0]["rule_entities"] == [{"mention": "vehicle speed", "type": "SIGNAL"}]
    assert merged[1]["rule_entities"] == [{"mention": "MIL", "type": "INDICATOR"}]
    assert merged[0]["ner_entities"] == []


def test_build_requirements_with_entities_preserves_extra_entity_fields_and_dedupes():
    requirements = [{"requirement_id": "REQ_1", "raw_text": "Vehicle speed shall be valid."}]
    rule_rows = [
        {
            "requirement_id": "REQ_1",
            "entities": [
                {"mention": "vehicle speed", "type": "signal", "start": 0, "end": 13},
                {"mention": "vehicle speed", "type": "SIGNAL", "start": 0, "end": 13},
            ],
        }
    ]

    merged = build_requirements_with_entities(requirements, rule_rows=rule_rows, ner_rows=[])

    assert merged[0]["rule_entities"] == [
        {"mention": "vehicle speed", "type": "SIGNAL", "start": 0, "end": 13}
    ]
