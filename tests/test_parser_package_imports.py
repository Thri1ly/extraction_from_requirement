def test_parser_package_imports_condition_modules():
    from src.parser.action_parser import parse_actions
    from src.parser.atomic_condition_parser import parse_condition_line
    from src.parser.condition_block_extractor import extract_condition_blocks
    from src.parser.condition_logic_parser import parse_condition_logic
    from src.parser.condition_parser import parse_conditions
    from src.parser.coreference_resolver import resolve_coreferences
    from src.parser.dependency_parser import parse_dependencies

    assert callable(parse_actions)
    assert callable(parse_condition_line)
    assert callable(extract_condition_blocks)
    assert callable(parse_condition_logic)
    assert callable(parse_conditions)
    assert callable(resolve_coreferences)
    assert callable(parse_dependencies)


def test_debug_atomic_condition_line_uses_parser_package():
    import scripts.debug_atomic_condition_line as debug_script
    import src.parser.atomic_condition_parser as parser_module

    assert debug_script.parse_condition_line is parser_module.parse_condition_line
