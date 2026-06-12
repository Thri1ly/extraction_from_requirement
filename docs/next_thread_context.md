# Next Thread Context

Use this file when continuing the project in a new conversation.

## Project Goal

Build an automotive steering-system requirement knowledge base. The pipeline converts English system requirements into enhanced JSONL with high-quality `embedding_text` for RAG retrieval and later test-case generation.

The current active focus is atomic condition parsing after entity extraction and normalization.

## Current Pipeline Shape

High-level flow:

```text
raw/preprocessed requirement
-> extracted entities from rule extractor and NER
-> normalized entities using dictionary
-> condition block extraction
-> condition logic parsing
-> atomic condition parsing
-> parsed conditions
-> enhanced_jsonl
-> embedding_text
```

The user often runs stages independently and reviews intermediate JSONL/MD reports before moving to the next stage.

## Important Files

Parser files:

- `src/parser/condition_block_extractor.py`
- `src/parser/condition_logic_parser.py`
- `src/parser/condition_parser.py`
- `src/parser/atomic_condition_parser.py`
- `src/parser/syntactic_atomic_condition_parser.py`

Normalization:

- `src/normalizer.py`

Debug scripts:

- `scripts/debug_atomic_condition_line.py`
- `scripts/batch_debug_atomic_conditions.py`
- `scripts/run_condition_block_extractor.py`
- `scripts/run_condition_logic_parser.py`
- `scripts/run_condition_parser.py`
- `scripts/run_atomic_condition_parser.py`

Tests:

- `tests/test_syntactic_atomic_condition_parser.py`
- `tests/test_debug_atomic_condition_line.py`
- `tests/test_batch_debug_atomic_conditions.py`
- `tests/test_normalize_requirements_entities.py`

Rule reference:

- `docs/atomic_condition_parser_rules.md`

## Environment

Python command used in this workspace:

```powershell
E:\App\Anaconda\python.exe
```

Run all tests:

```powershell
E:\App\Anaconda\python.exe -m pytest tests -q
```

Latest known full test result when this file was created:

```text
140 passed
```

## Current Parser Assumptions

The syntactic atomic parser should be tried before the legacy parser.

Supported placeholder entity types:

- `SIGNAL`
- `STATE`
- `VALUE`
- `PARAMETER`
- `COMPONENT`
- `FAULT`

Extractor-only curly wrappers around entity mentions are non-semantic. The normalizer now strips one complete outer `{...}` wrapper from incoming entity mentions before dictionary lookup, and the syntactic parser removes standalone `{PLACEHOLDER}` wrappers from `placeholder_text`. This prevents forms such as `{S_SPEED}` or `{EPS}` from breaking exact placeholder rules. Do not strip wrappers from the full original text, and avoid changing transform-like forms such as `|{SIGNAL}|`.

Dictionary misses should not be dropped by default. They should pass into parsing with lower confidence and review metadata.

`COMPONENT` currently only connects to `STATE`, not `VALUE` or `PARAMETER`.

`FAULT in COMPONENT` is supported if the `FAULT` entity reaches the parser, even when the fault was not found in the dictionary.

## Useful Debug Checks

When a condition fails, inspect these first:

1. `normalized_entities`
2. `placeholder_text`
3. final parsed output

If a rule should match but placeholder text does not contain the expected placeholders, the issue is usually entity extraction or normalization, not the atomic parser.

Example expected placeholder:

```text
Critical failure in CAN1
-> FAULT_1 in COMPONENT_1
```

Braced entity wrappers should also disappear at the placeholder layer:

```text
{DEM_COLUMN_TORQUE_IMPLAUSIBLE} in {EPS}
-> FAULT_1 in COMPONENT_1
```

If it becomes plain text plus `COMPONENT_1`, the `FAULT` did not enter parser input.

## Git Notes

The repository has local generated data and research artifacts. Do not stage broad `git add -A`.

Tracked generated data that may be dirty:

- `data/enhanced_requirements.jsonl`

Prefer explicit staging of code/test/doc files.

GitHub remote:

```text
https://github.com/Thri1ly/extraction_from_requirement.git
```

The main branch currently used is:

```text
master
```

## Recommended Next-Step Workflow

For parser bug reports:

1. Reproduce with a small inline script using `parse_condition_line`.
2. Print `build_syntax_analysis(... )["placeholder_text"]`.
3. Add a focused failing test.
4. Implement the narrowest rule.
5. Run targeted test.
6. Run all tests.
7. Commit only relevant files.

For new rule design:

1. Decide whether the relation belongs to normalization, condition logic, or atomic parsing.
2. Confirm required input entities and canonical names.
3. Specify output schema first.
4. Add examples to `docs/atomic_condition_parser_rules.md`.
