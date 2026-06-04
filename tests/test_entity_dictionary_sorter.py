from src.entity_dictionary_sorter import sort_dictionary_entities


def test_sort_dictionary_entities_groups_by_type_and_sorts_by_canonical_name():
    entities = [
        {"canonical_name": "S_Z_SPEED", "type": "SIGNAL"},
        {"canonical_name": "MIL", "type": "INDICATOR"},
        {"canonical_name": "DEM_B_FAULT", "type": "FAULT"},
        {"canonical_name": "S_A_SPEED", "type": "SIGNAL"},
        {"canonical_name": "DEM_A_FAULT", "type": "FAULT"},
    ]

    sorted_entities = sort_dictionary_entities(entities)

    assert [(item["type"], item["canonical_name"]) for item in sorted_entities] == [
        ("FAULT", "DEM_A_FAULT"),
        ("FAULT", "DEM_B_FAULT"),
        ("INDICATOR", "MIL"),
        ("SIGNAL", "S_A_SPEED"),
        ("SIGNAL", "S_Z_SPEED"),
    ]


def test_sort_dictionary_entities_normalizes_type_labels_before_sorting():
    entities = [
        {"canonical_name": "S_B", "type": "signal"},
        {"canonical_name": "S_A", "type": "SIGNAL"},
    ]

    sorted_entities = sort_dictionary_entities(entities)

    assert sorted_entities == [
        {"canonical_name": "S_A", "type": "SIGNAL"},
        {"canonical_name": "S_B", "type": "SIGNAL"},
    ]
