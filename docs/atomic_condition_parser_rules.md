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
- `FEATURE`
- `ACTION`

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

1. complete `AND`/`OR` clause groups where each side is a full condition, for example `SIGNAL is STATE and COMPONENT is STATE`
2. `FAULT in COMPONENT`
3. quantified `COMPONENT` members in `STATE`
4. single `COMPONENT is/are/in STATE`
5. single `FEATURE is/are/in STATE`
6. single `FEATURE ACTION`
7. single `SIGNAL ACTION`, including action target ranges
8. parenthesized semantic/expression composition, for example `outer natural-language phrase (S1 < S2 for ... of at least P_TIME)`
9. `SIGNAL_ALIAS (SIGNAL_EXPLICIT) is STATE`
10. explicit parenthesized signal definition, for example `alias is zero (S_X is equal to zero)`
11. independent outer and parenthesized signal predicates, for example `SIGNAL1 is STATE1(SIGNAL2 == FULL)`
12. parenthesized signal trend, for example `SIGNAL_1(SIGNAL_2) increases`
13. bracketed range, for example `0 < S_SPEED < 100` and `P_MAX >= S_SPEED > 0`
14. `range between/of PARAMETER and PARAMETER`
15. signal value-state clause groups, for example `S_X is equal to "0x1: Valid"`
16. quantified `SIGNAL` members in `STATE`
17. parenthesized `SIGNAL` state without predicate, for example `alias (S_X) invalid`
18. single `SIGNAL STATE` without predicate
19. single signal-state predicate with duration qualifier, for example `S_STATUS is valid for a period of P_TIME`
20. single signal with adjacent parameter tokens, for example `SIGNAL > PARAMETER PARAMETER`
21. single signal with multiple right-side states/values/parameters
22. multiple signals with one right-side state/value/parameter
23. single signal with one right-side state/value/parameter
24. legacy parser fallback

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
SIGNAL1 is STATE1(SIGNAL2 == FULL)
S_STATUS shall be Active or Degraded or fail operation
S_STATUS is equal to valid for a period of P_DURATION_TIME
S_STATUS is zero within P_DURATION_TIME
S_SPEED > P_SPEED_LIMIT for >= P_DURATION_TIME
SIGNAL_1(SIGNAL_2) increases
a FAULT is detected in COMPONENT (SIGNAL1 < SIGNAL2 for a calibrated window of at least PARAMETER)
at least one SIGNAL is STATE
SIGNAL is STATE and COMPONENT is STATE
SIGNAL > parameter parameter
SIGNAL is in range between PARAMETER and PARAMETER
SIGNAL increases to the range between PARAMETER and PARAMETER
```

Expected outputs include:

- `threshold_condition`
- `parameter_threshold_condition`
- `signal_state_condition`
- `condition_group`
- `range_condition`
- `signal_action_condition`

For value-state enum text such as `S_MODE is equal to "0x1: Valid"`, the current syntactic output keeps only the state condition (`S_MODE == Valid`). The numeric enum value is treated as parsing evidence and is not emitted as a threshold child.

If NER did not split enum text, the syntactic parser can infer `VALUE` and `STATE` from `0x1: Valid`. The inferred state condition carries review metadata and `enum_value`.

When a state-like right-side phrase follows a clear relation/operator but was not normalized as `STATE`, the syntactic parser may create a low-confidence inferred `STATE` with `need_review=true`, for example `FULL` in `SIGNAL2 == FULL` or `fail operation` in `STATE_1 or STATE_2 or fail operation`.

When adjacent `PARAMETER` placeholders form one threshold phrase, for example `speed threshold`,
the parser combines them into one canonical parameter name with a `P_` prefix such as
`P_SPEED_THRESHOLD`. Non-`P_` parameter canonical names are normalized to the same `P_...`
style in final parser output.

For single-signal predicates with a duration phrase, the syntactic parser can attach duration qualifiers to `signal_state_condition`, `threshold_condition`, and `parameter_threshold_condition`.
For detected-event parenthetical signal comparisons, the syntactic parser can also attach the duration qualifier to the `signal_comparison_condition` child.

Supported duration suffix examples:

```text
SIGNAL is STATE for a period of PARAMETER
SIGNAL is VALUE within PARAMETER
SIGNAL > PARAMETER for >= PARAMETER
SIGNAL is STATE for more than PARAMETER
SIGNAL is STATE for longer than PARAMETER
SIGNAL is STATE exceeds the duration time
SIGNAL is STATE exceeding debounce time
SIGNAL is STATE for a duration of PARAMETER
SIGNAL is STATE for the duration time of PARAMETER
SIGNAL is STATE for a duration greater than PARAMETER
SIGNAL is STATE for the duration time less than PARAMETER
SIGNAL is STATE for > PARAMETER
SIGNAL is STATE for < PARAMETER
SIGNAL is STATE for <= PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of at least PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of no less than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of at most PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of no more than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of greater than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of more than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of longer than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of less than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of shorter than PARAMETER
SIGNAL1 < SIGNAL2 for any descriptive phrase of PARAMETER
```

The output keeps the base condition type and adds:

```json
{
  "qualifiers": [
    {"type": "duration", "mention": "within P_DURATION_TIME", "parameter": "P_DURATION_TIME", "operator": "<="}
  ]
}
```

Duration operators are included when the suffix states one explicitly or implies one (`within` -> `<=`, `more/longer than` and `exceeds/exceeding` -> `>`). The duration parameter is not emitted as a separate threshold/parameter child.
For generic `for ... of ... PARAMETER` forms, the words after `of` determine the operator: `at least` and `no less than` -> `>=`; `at most` and `no more than` -> `<=`; `greater than`, `more than`, and `longer than` -> `>`; `less than` and `shorter than` -> `<`. Plain `of PARAMETER` has no operator. The phrase before `of` is treated as the duration parameter's descriptive attribute phrase and is not restricted to words such as `period`, `duration`, or `debounce`.

### Parenthesized Semantic/Expression Conditions

Supported forms:

```text
xxx1 (xxx2)
a xxx is detected in ECU1 (SIGNAL1 < SIGNAL2 for a xxx period of at least P_TIME)
```

Output type:

```text
condition_group
```

When `xxx2` is a formal expression, the group uses `logic=AND` and exposes two explicit
top-level labels:

- `outer_condition` for the outer segment. The parser first tries existing formal rules;
  if no formal rule matches, it falls back to an `nlp_condition`.
- `expression_condition` for the parenthesized formal condition.

`children` is `[outer_condition, expression_condition]`. If `outer_condition` is an
`nlp_condition`, the group also exposes the compatibility label `nlp_condition` pointing
to the same object. The two parts are parsed independently and must not infer fields from
each other. For passive detected events, the outer semantic fallback may include fields
such as `text`, `subject`, `predicate=detect`, `voice=passive`, `locations`,
`semantic_chunks`, and `known_entities`. If the inner expression is a signal comparison,
a trailing duration phrase is attached in `qualifiers` and is not emitted as a separate
parameter threshold condition.

The parser public entry points do not emit `state_definition_condition`. Legacy
parenthesized expression helpers return this same `condition_group` shape.

Parentheses are only decomposed this way when the parenthesized segment contains a formal
condition expression. Alias/entity forms such as `Driver torque (S_COLUMN_TORQUE) invalid`
stay with the existing signal-state parenthesis rules.

### Natural-Language Conditions

Natural-language condition segments that do not match a formal condition rule are preserved
as `nlp_condition`. When a sentence can be segmented, semantic chunks identify roles such
as `subject`, `predicate`, and `location`. When the text is incomplete, for example:

```text
in ECU1
```

the parser preserves the fragment itself:

```json
{
  "type": "nlp_condition",
  "mention": "in ECU1",
  "text": "in ECU1",
  "semantic_chunks": [{"role": "raw_text", "text": "in ECU1"}],
  "need_review": true
}
```

Unsupported formal-looking lines can still return `syntactic_fallback_condition` so they
remain reviewable without being mislabeled as natural-language semantics.

### Range Conditions

Supported forms:

```text
0 < S_SPEED < 100
0 < {S_SPEED} < 100
P_MIN <= S_SPEED <= P_MAX
100 >= S_SPEED >= 0
P_MAX > S_SPEED > P_MIN
P_MAX >= S_SPEED > 0
S_SPEED is in range between P_MIN and P_MAX
S_SPEED is in range between the minimum speed and the maximum speed
S_SPEED increases to the range between P_MIN and P_MAX
```

Output type:

```text
range_condition
```

For `range between/of PARAMETER and PARAMETER`, the parser emits `relation=in_range`,
`lower_operator=>=`, and `upper_operator=<=`. If the range is the target of a signal action
such as `SIGNAL increases to the range between P_MIN and P_MAX`, the action condition keeps
the full mention and stores the range under `target`.

### Quantified Signal Members

Supported forms include:

```text
both vehicle speed signal are valid
both of the vehicle speed signal are valid
one of the vehicle speed signal is valid
at least one of the vehicle speed signal is valid
at least one vehicle speed signal is valid
```

The source entity must contain `members`. The parser expands:

- `both` / `all` into `logic=AND`, `quantifier=ALL`
- `one of` / `at least one of` / `at least one` into `logic=OR`, `quantifier=ANY_ONE`

### Complete Clause Groups

Supported forms:

```text
SIGNAL is STATE and COMPONENT is STATE
SIGNAL is STATE or COMPONENT is STATE
```

When both sides of `AND`/`OR` are complete conditions, each side is parsed independently
before the group is assembled. This prevents the right-hand clause from being incorrectly
attached to the left-hand signal.

### Component Conditions

Supported forms:

```text
EPS is Degraded
EPS is in Degraded
EPS are Active
EPS Initialization is completely finished
```

Only `COMPONENT` to `STATE` is supported. `COMPONENT` to `VALUE` or `PARAMETER` is intentionally not parsed.

If a modifier appears between the relation and state, it is preserved as `state_modifier` and `state_phrase` so the output does not lose information, while `required_state` remains the normalized state.

Output type:

```text
component_state_condition
```

### Feature And Action Conditions

Supported forms:

```text
ADS torque control is Active
ADS torque control exits
steering torque enable signal requests to exit from COMPONENT1
S_SPEED increases to the range between P_SPEED_MIN and P_SPEED_MAX
```

Expected output types:

```text
feature_state_condition
feature_action_condition
signal_action_condition
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
- Syntax-inferred right-side states: around `0.70`
- Unknown dictionary entities lower normalization confidence, usually to `0.40`

`need_review=true` is used when:

- A required member list is missing.
- A range bound cannot be parsed cleanly.
- A parenthesized signal canonical differs from the leading signal canonical.
- Normalization preserved an entity that was not found in the dictionary.
- A right-side state phrase was inferred from syntax because no `STATE` entity was available.
- A condition is parsed only by the generic syntactic fallback.

The parser should no longer emit `unparsed_condition` from the atomic parser public entry points. If no explicit rule matches, it returns:

```json
{
  "type": "syntactic_fallback_condition",
  "need_review": true,
  "predicate": "unknown_relation",
  "unknown_candidates": []
}
```

This fallback preserves candidates for ontology construction instead of dropping the condition.

## Legacy Fallback Pruning

The first migration batch removed active legacy fallback calls for rules that are now covered by syntactic parsing:

- `parse_signal_state_and_parameter_threshold_conditions`
- `parse_single_signal_value_state_conditions`
- `parse_multi_signal_value_conditions`
- `parse_single_signal_multi_state_conditions`
- `parse_multi_signal_single_state_conditions`
- `parse_signal_state_conditions`

The old implementations remain in `src/parser/atomic_condition_parser.py` for reference, and the full pre-pruning file is archived at `src/parser/legacy_archive/atomic_condition_parser_legacy_full.py`.

Detailed migration status is tracked in `docs/legacy_to_syntactic_migration.md`.

### Active Legacy Suffix Quantifier Rule

`parse_suffix_quantified_signal_parameter_conditions` remains active in legacy fallback.
It supports signal quantifier suffixes `n` and `m` for parameter comparisons:

- `n` means `ALL` / `AND`
- `m` means `ANY_ONE` / `OR`

The suffix can appear at the end or inside the signal token. The parser removes the
quantifier character to derive the base signal and then uses that base signal's `members`
when available.

Examples:

```text
S_ASSIST_CAPABILITYn >= P_ASSIST_LIMIT
S_ASSIST_CAPABILITYm >= P_ASSIST_LIMIT
S_ASSISTn_CAPABILITY >= P_ASSIST_LIMIT
S_ASSISTm_CAPABILITY >= P_ASSIST_LIMIT
```

If the inferred base signal is not present or has no members, the parser returns a
review-needed `condition_group` using `all of BASE_SIGNAL ...` or `one of BASE_SIGNAL ...`
as the group mention instead of silently dropping the condition.

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

Batch subreports are limited to:

- `parsed_without_review`
- `parsed_with_review`

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
