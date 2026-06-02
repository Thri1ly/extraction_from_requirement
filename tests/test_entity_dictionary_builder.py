from src.entity_dictionary_builder import (
    build_signal_dictionary,
    extract_alias_candidates,
    humanize_signal_name,
    load_dictionary,
    merge_approved_aliases,
    suggest_canonical,
)


def test_humanize_signal_name_turns_s_code_into_alias():
    assert humanize_signal_name("S_VEHICLE_SPEED") == "vehicle speed"
    assert humanize_signal_name("S_COLUMN_TORQUE") == "column torque"


def test_build_signal_dictionary_from_signal_rows():
    rows = [
        {"Signal": "S_VEHICLE_SPEED", "Unit": "kph", "Component": "Vehicle"},
        {"Signal": "S_TORQUE_DEMAND", "Unit": "Nm", "Component": "EPS"},
    ]

    entities = build_signal_dictionary(rows, signal_column="Signal")

    speed = entities[0]
    assert speed["canonical_name"] == "S_VEHICLE_SPEED"
    assert speed["type"] == "signal"
    assert speed["unit"] == "kph"
    assert speed["component"] == "Vehicle"
    assert "S_VEHICLE_SPEED" in speed["aliases"]
    assert "vehicle speed" in speed["aliases"]
    assert "vehicle speed signal" in speed["aliases"]


def test_suggest_canonical_matches_humanized_alias():
    dictionary = build_signal_dictionary([{"Signal": "S_VEHICLE_SPEED"}], signal_column="Signal")

    suggestion = suggest_canonical("vehicle speed", dictionary)

    assert suggestion["canonical_name"] == "S_VEHICLE_SPEED"
    assert suggestion["confidence"] >= 0.8


def test_extract_alias_candidates_from_requirement_rows():
    dictionary = build_signal_dictionary(
        [
            {"Signal": "S_VEHICLE_SPEED"},
            {"Signal": "S_DRIVER_TORQUE"},
            {"Signal": "S_TORQUE_DEMAND"},
        ],
        signal_column="Signal",
    )
    requirements = [
        {
            "Req ID": "REQ_101",
            "Requirement": "When vehicle speed is greater than 3kph, EPS shall calculate the torque demand.",
        },
        {
            "Req ID": "REQ_102",
            "Requirement": "With increasing Driver Torque, EPS shall limit S_TORQUE_DEMAND to 2Nm.",
        },
    ]

    candidates = extract_alias_candidates(
        requirements,
        dictionary,
        text_column="Requirement",
        id_column="Req ID",
    )

    by_mention = {candidate["mention"]: candidate for candidate in candidates}
    assert "EPS shall calculate the torque" not in by_mention
    assert by_mention["vehicle speed"]["suggested_canonical"] == "S_VEHICLE_SPEED"
    assert by_mention["vehicle speed"]["status"] == "pending"
    assert by_mention["vehicle speed"]["evidence"] == ["REQ_101"]
    assert by_mention["torque demand"]["suggested_canonical"] == "S_TORQUE_DEMAND"
    assert by_mention["Driver Torque"]["suggested_canonical"] == "S_DRIVER_TORQUE"
    assert by_mention["S_TORQUE_DEMAND"]["suggested_canonical"] == "S_TORQUE_DEMAND"


def test_merge_approved_aliases_adds_only_approved_mentions():
    dictionary = build_signal_dictionary(
        [
            {"Signal": "S_VEHICLE_SPEED"},
            {"Signal": "S_DRIVER_TORQUE"},
        ],
        signal_column="Signal",
    )
    candidates = [
        {
            "mention": "vehicle speed signals",
            "suggested_canonical": "S_VEHICLE_SPEED",
            "type": "signal",
            "status": "approved",
            "evidence": ["REQ_101"],
        },
        {
            "mention": "driver input torque",
            "canonical_name": "S_DRIVER_TORQUE",
            "type": "signal",
            "status": "approved",
            "evidence": ["REQ_102"],
        },
        {
            "mention": "bad candidate",
            "suggested_canonical": "S_VEHICLE_SPEED",
            "type": "signal",
            "status": "rejected",
        },
    ]

    merged, report = merge_approved_aliases(dictionary, candidates)

    by_name = {entity["canonical_name"]: entity for entity in merged}
    assert "vehicle speed signals" in by_name["S_VEHICLE_SPEED"]["aliases"]
    assert "driver input torque" in by_name["S_DRIVER_TORQUE"]["aliases"]
    assert "bad candidate" not in by_name["S_VEHICLE_SPEED"]["aliases"]
    assert report["merged_aliases"] == 2
    assert report["skipped_candidates"] == 1


def test_merge_approved_aliases_creates_non_signal_entities_when_requested():
    dictionary = build_signal_dictionary([{"Signal": "S_VEHICLE_SPEED"}], signal_column="Signal")
    candidates = [
        {
            "mention": "column torque implausible fault",
            "canonical_name": "DEM_COLUMN_TORQUE_IMPLAUSIBLE",
            "type": "fault",
            "status": "approved",
        }
    ]

    merged, report = merge_approved_aliases(dictionary, candidates, create_missing=True)

    by_name = {entity["canonical_name"]: entity for entity in merged}
    assert by_name["DEM_COLUMN_TORQUE_IMPLAUSIBLE"]["type"] == "fault"
    assert "column torque implausible fault" in by_name["DEM_COLUMN_TORQUE_IMPLAUSIBLE"]["aliases"]
    assert report["created_entities"] == 1


def test_merge_approved_aliases_defaults_to_approved_jsonl_and_creates_missing_types():
    dictionary = build_signal_dictionary([{"Signal": "S_VEHICLE_SPEED"}], signal_column="Signal")
    approved_candidates = [
        {
            "mention": "MIL",
            "canonical_name": "MIL",
            "type": "indicator",
        },
        {
            "mention": "vehicle speed",
            "canonical_name": "S_VEHICLE_SPEED",
            "type": "signal",
        },
    ]

    merged, report = merge_approved_aliases(dictionary, approved_candidates)

    by_name = {entity["canonical_name"]: entity for entity in merged}
    assert by_name["MIL"]["type"] == "indicator"
    assert "MIL" in by_name["MIL"]["aliases"]
    assert "vehicle speed" in by_name["S_VEHICLE_SPEED"]["aliases"]
    assert report["created_entities"] == 1
    assert report["merged_aliases"] == 0


def test_load_dictionary_accepts_jsonl_dictionary(tmp_path):
    dictionary_path = tmp_path / "signals.jsonl"
    dictionary_path.write_text(
        '{"canonical_name":"S_VEHICLE_SPEED","type":"signal","aliases":["vehicle speed"]}\n',
        encoding="utf-8",
    )

    entities = load_dictionary(dictionary_path)

    assert entities == [{"canonical_name": "S_VEHICLE_SPEED", "type": "signal", "aliases": ["vehicle speed"]}]


def test_load_dictionary_accepts_utf8_bom(tmp_path):
    dictionary_path = tmp_path / "signals.json"
    dictionary_path.write_text(
        '\ufeff{"version":"initial","entities":[{"canonical_name":"S_VEHICLE_SPEED","aliases":[]}]}',
        encoding="utf-8",
    )

    entities = load_dictionary(dictionary_path)

    assert entities[0]["canonical_name"] == "S_VEHICLE_SPEED"
