# Atomic Condition Parser Rules

This document summarizes the current atomic condition parser contract so a new thread can continue without reading the full conversation history.

## Purpose

The atomic parser converts one normalized condition line into structured condition dictionaries. It is currently rule based, with a syntactic placeholder parser first and the legacy atomic parser as fallback.

Primary entry points:

- `src/parser/syntactic_atomic_condition_parser.py`
- `src/parser/atomic_condition_parser.py`
- `scripts/debug_atomic_condition_line.py`
- `scripts/batch_debug_atomic_conditions.py`

## Inputs

The parser expects:

- `text`: one atomic condition line.
- `normalized_entities`: a list of entity dictionaries.

Typical entity fields:

```json
{
  "mention": "vehicle speed",
  "type": "SIGNAL",
  "canonical_name": "S_VEHICLE_SPEED",
  "members": ["S_VEHICLE_SPEED_1", "S_VEHICLE_SPEED_2"],
  "dictionary_match": true,
  "normalization_confidence": 1.0
}
```

Supported entity types in the syntactic parser:

- `SIGNAL`
- `STATE`
- `VALUE`
- `PARAMETER`
- `COMPONENT`
- `FAULT`

Dictionary misses are allowed to enter parsing. They should carry `dictionary_match=false`, `normalization_confidence=0.4`, and `need_review=true` from the normalizer.

## Placeholder Layer

The syntactic parser first replaces recognized entities with placeholders such as:

- `SIGNAL_1`
- `STATE_1`
- `VALUE_1`
- `PARAMETER_1`
- `COMPONENT_1`
- `FAULT_1`

Important behavior:

- The same normalized entity may be replaced more than once if it appears multiple times in the text.
- Placeholder numbering follows text order.
- `mention` match is preferred over `canonical_name` match when spans overlap.
- Non-semantic entity wrapper braces are removed after placeholderization. For example, `{S_SPEED}` should become `SIGNAL_1`, not `{SIGNAL_1}`.
- Brace cleanup is intentionally narrow. It targets standalone `{PLACEHOLDER}` wrappers and should not rewrite the full original text or transform-like forms such as `|{SIGNAL}|`.

Example:

```text
assist capability is zero (S_ASSIST_CAPABILITY is equal to zero)
```

becomes:

```text
SIGNAL_1 is VALUE_1 (SIGNAL_2 is equal to VALUE_2)
```

## Rule Order

The syntactic parser applies rules in this order:

1. `FAULT in COMPONENT`
2. quantified `COMPONENT` members in `STATE`
3. single `COMPONENT is/are/in STATE`
4. `SIGNAL_ALIAS (SIGNAL_EXPLICIT) is STATE`
5. explicit parenthesized signal definition, for example `alias is zero (S_X is equal to zero)`
6. bracketed range, for example `0 < S_SPEED < 100` and `P_MAX >= S_SPEED > 0`
7. signal value-state clause groups, for example `S_X is equal to "0x1: Valid"`
8. quantified `SIGNAL` members in `STATE`
9. parenthesized `SIGNAL` state without predicate, for example `alias (S_X) invalid`
10. single `SIGNAL STATE` without predicate
11. single signal with multiple right-side states/values/parameters
12. multiple signals with one right-side state/value/parameter
13. single signal with one right-side state/value/parameter
14. legacy parser fallback

This order matters. More specific and safer rules should stay before broader rules.

## Supported Patterns

### Signal Conditions

Examples:

```text
S_SPEED > 10kph
S_STATUS is valid
S_STATUS is not valid
S_MODE is equal to "0x1: Valid"
S_K_FACTOR_REQUEST is equal to or greater than P_LIMIT
S_COLUMN_TORQUE_QF invalid
Column Torque QF (S_COLUMN_TORQUE_QF) invalid
LDW request (S_LDW_HAPTIC_AVL) is Available
```

Expected outputs include:

- `threshold_condition`
- `parameter_threshold_condition`
- `signal_state_condition`
- `condition_group`

### Range Conditions

Supported forms:

```text
0 < S_SPEED < 100
0 < {S_SPEED} < 100
P_MIN <= S_SPEED <= P_MAX
100 >= S_SPEED >= 0
P_MAX > S_SPEED > P_MIN
P_MAX >= S_SPEED > 0
```

Output type:

```text
range_condition
```

### Quantified Signal Members

Supported forms include:

```text
both vehicle speed signal are valid
both of the vehicle speed signal are valid
one of the vehicle speed signal is valid
at least one of the vehicle speed signal is valid
```

The source entity must contain `members`. The parser expands:

- `both` / `all` into `logic=AND`, `quantifier=ALL`
- `one of` / `at least one of` into `logic=OR`, `quantifier=ANY_ONE`

### Component Conditions

Supported forms:

```text
EPS is Degraded
EPS is in Degraded
EPS are Active
```

Only `COMPONENT` to `STATE` is supported. `COMPONENT` to `VALUE` or `PARAMETER` is intentionally not parsed.

Output type:

```text
component_state_condition
```

### Quantified Component Members

Supported forms:

```text
both steering channels are Active
one of the steering channels is Active
```

The component entity must contain `members`. Expansion follows the same `ALL`/`ANY_ONE` logic as signals.

### Fault In Component

Supported form:

```text
Critical failure in CAN1
DEM_COLUMN_TORQUE_IMPLAUSIBLE in EPS
{DEM_COLUMN_TORQUE_IMPLAUSIBLE} in {EPS}
```

Input must include a `FAULT` entity and a `COMPONENT` entity. Dictionary misses are acceptable if the entity still reaches the parser with `type=FAULT`.

Output type:

```text
fault_component_condition
```

## Confidence And Review

Rules may set `confidence` directly. Debug scripts also compute `parse_confidence`.

Current conventions:

- Clear parenthesized explicit definitions: around `0.95`
- `SIGNAL_ALIAS (SIGNAL_EXPLICIT) is STATE`: around `0.93`
- Parenthesized signal state without predicate: around `0.90`
- Bare `SIGNAL STATE`: around `0.80`
- Unknown dictionary entities lower normalization confidence, usually to `0.40`

`need_review=true` is used when:

- A required member list is missing.
- A range bound cannot be parsed cleanly.
- A parenthesized signal canonical differs from the leading signal canonical.
- Normalization preserved an entity that was not found in the dictionary.
- The condition is ultimately `unparsed_condition`.

## Debug Workflow

Single line:

```powershell
E:\App\Anaconda\python.exe scripts\debug_atomic_condition_line.py --condition-line "S_STATUS is valid" --entities-json "[{\"mention\":\"S_STATUS\",\"type\":\"SIGNAL\"},{\"mention\":\"valid\",\"type\":\"STATE\"}]" --dictionary-path data\signals.jsonl
```

Batch report:

```powershell
E:\App\Anaconda\python.exe scripts\batch_debug_atomic_conditions.py --input data\condition_lines.jsonl --output reports\atomic_condition_report.md --dictionary-path data\signals.jsonl
```

When syntactic syntax analysis is available, the main batch Markdown report and its category subreports show `Placeholder Text` for each row. They do not show `placeholder_map`; inspect JSONL output or the single-line debug script if map-level span/entity details are needed.

Validation:

```powershell
E:\App\Anaconda\python.exe -m pytest tests -q
```

## When Adding New Rules

Use this order:

1. Add a failing test in `tests/test_syntactic_atomic_condition_parser.py`.
2. Reproduce that the test fails for the expected reason.
3. Add the narrowest parser rule possible.
4. Put the rule before broader rules only when necessary.
5. Run the targeted test file.
6. Run all tests.

Avoid broad rules that parse `COMPONENT VALUE`, bare `SIGNAL VALUE`, or other ambiguous forms unless the input pattern has a strong delimiter or operator.
