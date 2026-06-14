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
- `tests/test_legacy_to_syntactic_migration.py`
- `tests/test_debug_atomic_condition_line.py`
- `tests/test_batch_debug_atomic_conditions.py`
- `tests/test_normalize_requirements_entities.py`

Rule reference:

- `docs/atomic_condition_parser_rules.md`
- `docs/legacy_to_syntactic_migration.md`

## Environment

Python command used in this workspace:

```powershell
E:\App\Anaconda\python.exe
```

Run all tests:

```powershell
E:\App\Anaconda\python.exe -m pytest tests -q
```

Latest known full test result after the first legacy-to-syntactic pruning batch:

```text
165 passed
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
- `FEATURE`
- `ACTION`

Extractor-only curly wrappers around entity mentions are non-semantic. The normalizer now strips one complete outer `{...}` wrapper from incoming entity mentions before dictionary lookup, and the syntactic parser removes standalone `{PLACEHOLDER}` wrappers from `placeholder_text`. This prevents forms such as `{S_SPEED}` or `{EPS}` from breaking exact placeholder rules. Do not strip wrappers from the full original text, and avoid changing transform-like forms such as `|{SIGNAL}|`.

Dictionary misses should not be dropped by default. They should pass into parsing with lower confidence and review metadata.

`COMPONENT` currently only connects to `STATE`, not `VALUE` or `PARAMETER`.

`COMPONENT is/are/in STATE` now tolerates relation-state modifiers such as `EPS Initialization is completely finished`. The normalized `required_state` stays as the state entity, and modifier text is preserved in `state_modifier` / `state_phrase`.

Parenthesized semantic/expression forms are kept as independent parts in one group.
For `xxx1 (xxx2)`, when `xxx2` is a formal expression, the output is a `condition_group`
with top-level `outer_condition` for `xxx1`, top-level `expression_condition` for `xxx2`,
and `children=[outer_condition, expression_condition]`. The outer segment first tries
existing formal rules; if none match, it falls back to `nlp_condition`. When that fallback
is used, the group also exposes `nlp_condition` as a compatibility alias for
`outer_condition`. The two parts must not infer fields from each other. For example,
`SIGNAL1 is STATE1(SIGNAL2 == FULL)` now emits a formal outer `signal_state_condition`
and an inner `SIGNAL2 == FULL` expression condition, not a cross-pair of `SIGNAL2` with
`STATE1`.

Passive detection events with parenthesized signal comparisons are kept as one `condition_group`
with top-level `outer_condition` and `expression_condition` rather than only returning the
parenthesized expression. For example,
`a xxx is detected in ECU1 (SIGNAL1 < SIGNAL2 for a xxx period of at least P_TIME)`
emits an outer `nlp_condition` via `outer_condition` (`subject=xxx`, `predicate=detect`, `voice=passive`,
`locations=[{relation=in, text=ECU1}]`, plus `semantic_chunks`) and an inner
`signal_comparison_condition`.
The duration phrase is attached to the comparison as a `duration` qualifier.

The parser public entry points should not emit `state_definition_condition`. Legacy
parenthesized helpers now return the same `condition_group` shape with `outer_condition`
and `expression_condition` instead of exposing the old type.

Value-state enum clauses such as `S_MODE is equal to "0x1: Valid"` now emit only the signal-state condition; enum values are parsing evidence and are not emitted as threshold children.

When a clear relation/operator is followed by a state-like phrase that was not normalized as `STATE`, selected syntactic rules may infer a low-confidence `STATE` with `need_review=true`, for example `FULL` after `==` or `fail operation` in a right-side state list.

Complete `AND`/`OR` clauses are parsed clause-by-clause when each side is a full condition,
for example `S_STATUS is Active and EPS is Degraded` becomes an `AND` group with a
`signal_state_condition` child and a `component_state_condition` child. This avoids
cross-pairing the second right-side state with the first signal.

Quantified signal and component member rules support `at least one SIGNAL is STATE` in
addition to `at least one of SIGNAL is STATE`; `at least one` maps to
`quantifier=ANY_ONE`, `logic=OR`.

Adjacent `PARAMETER` placeholders such as `speed threshold` are combined into one final
parameter output with a `P_` prefix, for example `P_SPEED_THRESHOLD`. Plain parameter
canonical names are normalized to `P_...` in parser outputs.

`range between/of (the) PARAMETER and (the) PARAMETER` is parsed as an `in_range`
`range_condition` with `lower_operator=>=` and `upper_operator=<=`. If it appears after a
signal action, for example `S_SPEED increases to the range between P_SPEED_MIN and
P_SPEED_MAX`, the `signal_action_condition` preserves the full action phrase and stores the
range under `target` with `target_relation=to`.

Single-signal predicates with duration qualifiers are syntactic now. The qualifier can attach to state, value, or parameter conditions:

```text
S_STATUS is equal to valid for a period of P_DURATION_TIME
-> signal_state_condition + qualifiers=[duration(P_DURATION_TIME)]
S_STATUS is zero within P_DURATION_TIME
-> threshold_condition + qualifiers=[duration(P_DURATION_TIME, operator=<=)]
S_SPEED > P_SPEED_LIMIT for >= P_DURATION_TIME
-> parameter_threshold_condition + qualifiers=[duration(P_DURATION_TIME, operator=>=)]
```

Supported duration suffix families include `within PARAMETER`, `for more/longer than PARAMETER`, `exceeds/exceeding (the) duration/debounce time`, `for (a/the) duration (time) of PARAMETER`, `for (a/the) duration (time) greater/less than PARAMETER`, and `for >=/>/</<= PARAMETER`.
Generic segment-level duration syntax `for ... of ... PARAMETER` is also supported without
hard-coding the noun before `of`. Operators are derived from the words after `of`:
`at least` / `no less than` -> `>=`, `at most` / `no more than` -> `<=`,
`greater than` / `more than` / `longer than` -> `>`, and `less than` / `shorter than` -> `<`.
Plain `of PARAMETER` has no explicit operator.

`FAULT in COMPONENT` is supported if the `FAULT` entity reaches the parser, even when the fault was not found in the dictionary.

`FEATURE` and `ACTION` are supported in the syntactic parser. Current basic outputs include:

```text
FEATURE is STATE -> feature_state_condition
FEATURE ACTION -> feature_action_condition
SIGNAL ACTION -> signal_action_condition
```

`SIGNAL_1(SIGNAL_2) increases/decreases` is parsed as a `signal_trend_condition`, using the inner signal as the trend target and the outer signal as context.

Enum labels such as `0x1: Valid` are split at parser time if NER did not split them. The value becomes enum evidence and the state becomes an inferred `STATE` with `need_review=true`.

Parser-side entity mention cleanup now strips a single unbalanced wrapper from entity mentions, for example `(vehicle speed` -> `vehicle speed` and `valid)` -> `valid`, before placeholder matching.

Atomic parser public entry points should not emit `unparsed_condition`. Natural-language
condition lines that do not match a formal parser rule should return `nlp_condition`.
Incomplete fragments such as `in ECU1` are preserved as their own raw-text semantic chunk
with `need_review=true`. Unsupported formal-looking condition lines should return
`syntactic_fallback_condition` with `need_review=true`, `predicate`, `known_entities`, and
`unknown_candidates`.

Legacy fallback rule `parse_suffix_quantified_signal_parameter_conditions` remains active.
It now supports `n/m` quantifier suffixes at the end or inside a signal token. For example,
`S_ASSIST_CAPABILITYm >= P_LIMIT` and `S_ASSISTm_CAPABILITY >= P_LIMIT` both derive base
signal `S_ASSIST_CAPABILITY`; `m` maps to `ANY_ONE`/`OR`, and `n` maps to `ALL`/`AND`.
If the base signal cannot be matched to members, it emits a review-needed group using
`one of BASE_SIGNAL ...` or `all of BASE_SIGNAL ...`.

## Legacy Fallback Pruning Status

The full pre-pruning legacy parser file is archived at:

```text
src/parser/legacy_archive/atomic_condition_parser_legacy_full.py
```

The following legacy rules remain defined but are no longer actively called from
`src/parser/atomic_condition_parser.py::parse_atomic_conditions` because syntactic parsing
covers them:

- `parse_signal_state_and_parameter_threshold_conditions`
- `parse_single_signal_value_state_conditions`
- `parse_multi_signal_value_conditions`
- `parse_single_signal_multi_state_conditions`
- `parse_multi_signal_single_state_conditions`
- `parse_signal_state_conditions`

The migration table is in `docs/legacy_to_syntactic_migration.md`.

## Useful Debug Checks

When a condition fails, inspect these first:

1. `normalized_entities`
2. `placeholder_text`
3. final parsed output

Batch atomic debug Markdown reports include `Placeholder Text` in the main report and category subreports (`parsed_without_review`, `parsed_with_review`) when syntactic syntax analysis is available. They intentionally do not include `placeholder_map`, so the reports stay readable while still showing the sentence pattern seen by parser rules.

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
