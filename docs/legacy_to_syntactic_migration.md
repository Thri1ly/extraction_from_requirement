# Legacy To Syntactic Migration

This file tracks legacy atomic parser rules that have been evaluated for migration into
`src/parser/syntactic_atomic_condition_parser.py`.

## 2026-06-14 First Pruned Batch

The following legacy rules are now covered by syntactic parsing and are no longer called
from `src/parser/atomic_condition_parser.py::parse_atomic_conditions`.

The old implementations are still present in `src/parser/atomic_condition_parser.py` for
local reference, and the full pre-pruning file is archived at:

```text
src/parser/legacy_archive/atomic_condition_parser_legacy_full.py
```

| Legacy rule | Status | Syntactic coverage | Test |
| --- | --- | --- | --- |
| `parse_signal_state_and_parameter_threshold_conditions` | active call removed | `SIGNAL is STATE and OPERATOR PARAMETER` becomes an `AND` group with state and parameter children. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_signal_state_and_parameter_threshold_rule_to_syntactic` |
| `parse_single_signal_value_state_conditions` | active call removed | Enum labels such as `S_MODE is equal to "0x1: Valid"` emit only `signal_state_condition`; the enum value is evidence, not a threshold child. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_single_signal_value_state_rule_to_syntactic_state_only_output` |
| `parse_multi_signal_value_conditions` | active call removed | Multiple signals sharing one value become an `AND`/`OR` condition group based on list separators. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_multi_signal_value_rule_to_syntactic` |
| `parse_single_signal_multi_state_conditions` | active call removed | One signal with a state list becomes a logic group of `signal_state_condition` children. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_single_signal_multi_state_rule_to_syntactic` |
| `parse_multi_signal_single_state_conditions` | active call removed | A signal list sharing one state becomes a logic group of `signal_state_condition` children. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_multi_signal_single_state_rule_to_syntactic` |
| `parse_signal_state_conditions` | active call removed | Single signal-state predicates, including `is not`, are syntactic. Duration qualifiers are now covered by a narrow syntactic rule. | `tests/test_legacy_to_syntactic_migration.py::test_migrates_signal_state_rule_to_syntactic` and `test_migrates_signal_state_duration_qualifier_to_syntactic` |

## Still Active In Legacy Fallback

These rules remain in the active legacy fallback order because they are not fully migrated
or intentionally remain legacy-only for now:

- `parse_state_definition_conditions`
- `parse_range_conditions`
- `parse_redundant_signal_validity`
- `parse_quantified_signal_member_state_conditions`
- `parse_fault_state_conditions`
- `parse_signal_comparison_conditions`
- `parse_single_signal_value_conditions`
- `parse_multi_signal_value_state_conditions`
- `parse_suffix_quantified_signal_parameter_conditions`
- `parse_single_signal_parameter_conditions`
- `parse_threshold_conditions`

`parse_bracketed_definition_conditions` remains a pre-fallback early return in
`parse_atomic_conditions`.

## 2026-06-14 Second Batch In Progress

Duration qualifiers are now handled by a shared syntactic suffix rule for single-signal
state, value, and parameter predicates. This expands coverage for the still-active legacy
rules `parse_single_signal_value_conditions` and `parse_single_signal_parameter_conditions`
without removing their active fallback calls yet.

Covered duration phrase variants:

- `within P_DURATION_TIME` -> duration operator `<=`
- `for more than P_DURATION_TIME` -> duration operator `>`
- `for longer than P_DURATION_TIME` -> duration operator `>`
- `exceeds the duration time` -> duration operator `>`
- `exceeding debounce time` -> duration operator `>`
- `for a duration of P_DURATION_TIME`
- `for the duration time of P_DURATION_TIME`
- `for a duration greater than P_DURATION_TIME` -> duration operator `>`
- `for the duration time less than P_DURATION_TIME` -> duration operator `<`
- `for >= P_DURATION_TIME` -> duration operator `>=`
- `for > P_DURATION_TIME` -> duration operator `>`
- `for < P_DURATION_TIME` -> duration operator `<`
- `for <= P_DURATION_TIME` -> duration operator `<=`

Tests:

- `tests/test_legacy_to_syntactic_migration.py::test_migrates_signal_value_duration_qualifier_to_syntactic`
- `tests/test_legacy_to_syntactic_migration.py::test_migrates_signal_parameter_duration_qualifier_to_syntactic`
- `tests/test_legacy_to_syntactic_migration.py::test_migrates_duration_qualifier_phrase_variants_to_syntactic`

## 2026-06-14 Active Legacy Rule 25 Enhancement

`parse_suffix_quantified_signal_parameter_conditions` is still active in the legacy
fallback. It now supports `n/m` quantifier suffixes in the middle of a signal token, not
only at the end.

Examples:

- `S_ASSIST_CAPABILITYm >= P_ASSIST_LIMIT`
- `S_ASSISTm_CAPABILITY >= P_ASSIST_LIMIT`
- `S_ASSIST_CAPABILITYn >= P_ASSIST_LIMIT`
- `S_ASSISTn_CAPABILITY >= P_ASSIST_LIMIT`

The parser removes the `n` or `m` character to derive the base signal, then looks for that
base signal in `normalized_entities` and expands its `members` when available. If the base
signal or members are unavailable, it emits a review-needed group with mention
`one of BASE_SIGNAL ...` for `m` or `all of BASE_SIGNAL ...` for `n`.

Tests:

- `tests/test_condition_parser_architecture.py::test_parse_infix_suffix_any_parameter_threshold_condition`
- `tests/test_condition_parser_architecture.py::test_infix_suffix_quantified_signal_without_base_members_uses_quantified_source_signal`
