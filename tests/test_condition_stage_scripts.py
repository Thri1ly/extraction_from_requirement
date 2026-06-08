import json

from scripts.run_atomic_condition_parser import run_atomic_condition_parser
from scripts.run_condition_block_extractor import run_condition_block_extractor
from scripts.run_condition_logic_parser import run_condition_logic_parser
from scripts.run_condition_parser_stage import run_condition_parser_stage


def write_jsonl(path, rows):
    path.write_text("\n".join(json.dumps(row, ensure_ascii=False) for row in rows), encoding="utf-8")


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_condition_stage_scripts_write_chainable_jsonl_and_review_md(tmp_path):
    source = tmp_path / "requirements.jsonl"
    block_jsonl = tmp_path / "condition_blocks.jsonl"
    block_md = tmp_path / "condition_blocks.md"
    logic_jsonl = tmp_path / "condition_groups.jsonl"
    logic_md = tmp_path / "condition_groups.md"
    parsed_jsonl = tmp_path / "parsed_conditions.jsonl"
    parsed_md = tmp_path / "parsed_conditions.md"
    atomic_jsonl = tmp_path / "atomic_conditions.jsonl"
    atomic_md = tmp_path / "atomic_conditions.md"

    write_jsonl(
        source,
        [
            {
                "requirement_id": "REQ_STAGE",
                "conditions": "when ALL below conditions are met:\nS_VEHICLE_SPEED > 10kph\nAND\nDEM_X is Active",
            }
        ],
    )

    block_rows = run_condition_block_extractor(source, block_jsonl, block_md)
    logic_rows = run_condition_logic_parser(block_jsonl, logic_jsonl, logic_md)
    parsed_rows = run_condition_parser_stage(logic_jsonl, parsed_jsonl, parsed_md)
    atomic_rows = run_atomic_condition_parser(logic_jsonl, atomic_jsonl, atomic_md)

    assert block_rows[0]["condition_blocks"][0]["condition_lines"] == ["S_VEHICLE_SPEED > 10kph", "DEM_X is Active"]
    assert logic_rows[0]["condition_groups"][0]["type"] == "condition_group"
    assert parsed_rows[0]["parsed_condition_groups"][0]["children"][0]["type"] == "threshold_condition"
    assert parsed_rows[0]["parsed_conditions"][0]["signal"] == "S_VEHICLE_SPEED"
    assert atomic_rows[0]["atomic_conditions"][0]["parsed"]["type"] == "threshold_condition"

    assert read_jsonl(block_jsonl)[0]["condition_blocks"]
    assert read_jsonl(logic_jsonl)[0]["condition_groups"]
    assert read_jsonl(parsed_jsonl)[0]["parsed_conditions"]
    assert read_jsonl(atomic_jsonl)[0]["atomic_conditions"]

    assert "REQ_STAGE" in block_md.read_text(encoding="utf-8")
    assert "condition_group" in logic_md.read_text(encoding="utf-8")
    assert "threshold_condition" in parsed_md.read_text(encoding="utf-8")
    assert "S_VEHICLE_SPEED > 10kph" in atomic_md.read_text(encoding="utf-8")
