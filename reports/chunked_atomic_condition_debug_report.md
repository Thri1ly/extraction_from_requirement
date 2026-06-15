# Chunked Atomic Condition Debug Report

## Summary

- Total records: 6
- Parsed records: 6
- Skipped records: 0
- Error records: 0
- Total chunks: 10
- Chunk type distribution:
  - atomic_condition: 2
  - bracketed_condition_group: 1
  - duration_constraint: 2
  - explicit_signal_definition: 1
  - natural_language_condition: 3
  - quantified_parenthesized_member_group: 1
- Atomic parse type distribution:
  - bracketed_condition_group: 1
  - duration_constraint: 2
  - quantified_member_expression_group: 1
  - unknown: 6

## Records

### 1. C001

Original Condition:

```text
vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT
```

Entities Source: normalized_entities

Normalization Applied: false

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | natural_language_condition | vehicle speed is invalid | unknown | false |
| 2 | explicit_signal_definition | S_VEHICLE_SPEED is equal to INVALID | unknown | false |
| 3 | duration_constraint | for a duration of P_LIMIT | duration_constraint | false |

#### Chunk 1 Parse Result

Chunk Text:

```text
vehicle speed is invalid
```

Chunk Entities:

```json
[
  {
    "mention": "vehicle speed",
    "type": "SIGNAL",
    "canonical_name": "S_VEHICLE_SPEED"
  },
  {
    "mention": "INVALID",
    "type": "STATE",
    "canonical_name": "INVALID"
  }
]
```

Parse Result:

```json
{
  "type": "signal_state_condition",
  "mention": "vehicle speed == INVALID",
  "signal": "S_VEHICLE_SPEED",
  "operator": "==",
  "required_state": "INVALID",
  "need_review": false,
  "parser": "syntactic"
}
```


#### Chunk 2 Parse Result

Chunk Text:

```text
S_VEHICLE_SPEED is equal to INVALID
```

Chunk Entities:

```json
[
  {
    "mention": "S_VEHICLE_SPEED",
    "type": "SIGNAL",
    "canonical_name": "S_VEHICLE_SPEED"
  },
  {
    "mention": "INVALID",
    "type": "STATE",
    "canonical_name": "INVALID"
  }
]
```

Parse Result:

```json
{
  "type": "signal_state_condition",
  "mention": "S_VEHICLE_SPEED == INVALID",
  "signal": "S_VEHICLE_SPEED",
  "operator": "==",
  "required_state": "INVALID",
  "need_review": false,
  "parser": "syntactic"
}
```


#### Chunk 3 Parse Result

Chunk Text:

```text
for a duration of P_LIMIT
```

Chunk Entities:

```json
[
  {
    "mention": "P_LIMIT",
    "type": "PARAMETER",
    "canonical_name": "P_LIMIT"
  }
]
```

Parse Result:

```json
{
  "condition_type": "duration_constraint",
  "text": "for a duration of P_LIMIT",
  "duration": "P_LIMIT",
  "value": null,
  "unit": null,
  "operator": "for_duration",
  "timing_relation": "sustain_for",
  "confidence": 0.9,
  "need_review": false,
  "duration_type": "duration"
}
```

### 2. C002

Original Condition:

```text
S_VEHICLE_SPEED is valid
```

Entities Source: normalized_entities

Normalization Applied: false

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | atomic_condition | S_VEHICLE_SPEED is valid | unknown | false |

#### Chunk 1 Parse Result

Chunk Text:

```text
S_VEHICLE_SPEED is valid
```

Chunk Entities:

```json
[
  {
    "mention": "S_VEHICLE_SPEED",
    "type": "SIGNAL",
    "canonical_name": "S_VEHICLE_SPEED"
  },
  {
    "mention": "valid",
    "type": "STATE",
    "canonical_name": "valid"
  }
]
```

Parse Result:

```json
{
  "type": "signal_state_condition",
  "mention": "S_VEHICLE_SPEED == valid",
  "signal": "S_VEHICLE_SPEED",
  "operator": "==",
  "required_state": "valid",
  "need_review": false,
  "parser": "syntactic"
}
```

### 3. C003

Original Condition:

```text
angle request is out of range in normal operation[(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit')] for a duration greater than P_LIMIT
```

Entities Source: normalized_entities

Normalization Applied: false

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | natural_language_condition | angle request is out of range in normal operation | unknown | true |
| 2 | bracketed_condition_group | (S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit') | bracketed_condition_group | false |
| 3 | duration_constraint | for a duration greater than P_LIMIT | duration_constraint | false |

#### Chunk 1 Parse Result

Chunk Text:

```text
angle request is out of range in normal operation
```

Chunk Entities:

```json
[
  {
    "mention": "normal",
    "type": "STATE",
    "canonical_name": "normal"
  }
]
```

Parse Result:

```json
{
  "type": "unparsed_condition",
  "mention": "angle request is out of range in normal operation",
  "need_review": true
}
```


#### Chunk 2 Parse Result

Chunk Text:

```text
(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit')
```

Chunk Entities:

```json
[
  {
    "mention": "S_SPC_ANGLE_MODE_REQUEST",
    "type": "SIGNAL",
    "canonical_name": "S_SPC_ANGLE_MODE_REQUEST"
  },
  {
    "mention": "normal",
    "type": "STATE",
    "canonical_name": "normal"
  },
  {
    "mention": "S_SPC_ANGLE_REQUEST",
    "type": "SIGNAL",
    "canonical_name": "S_SPC_ANGLE_REQUEST"
  },
  {
    "mention": "static limit",
    "type": "PARAMETER",
    "canonical_name": "static limit"
  }
]
```

Parse Result:

```json
{
  "condition_type": "bracketed_condition_group",
  "raw_text": "(S_SPC_ANGLE_MODE_REQUEST is equal to normal) AND (S_SPC_ANGLE_REQUEST is greater than 'static limit')",
  "note": "special_chunk_not_atomic_parsed",
  "need_review": false
}
```


#### Chunk 3 Parse Result

Chunk Text:

```text
for a duration greater than P_LIMIT
```

Chunk Entities:

```json
[
  {
    "mention": "P_LIMIT",
    "type": "PARAMETER",
    "canonical_name": "P_LIMIT"
  }
]
```

Parse Result:

```json
{
  "condition_type": "duration_constraint",
  "text": "for a duration greater than P_LIMIT",
  "duration": "P_LIMIT",
  "value": null,
  "unit": null,
  "operator": ">",
  "timing_relation": "sustain_for",
  "confidence": 0.9,
  "need_review": false,
  "duration_type": "duration"
}
```

### 4. C004

Original Condition:

```text
the signal on both lane (S_LANE1 > P_LIMIT) and (S_LANE2 > P_LIMIT) are valid
```

Entities Source: normalized_entities

Normalization Applied: false

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | quantified_parenthesized_member_group | the signal on both lane (S_LANE1 > P_LIMIT) and (S_LANE2 > P_LIMIT) are valid | quantified_member_expression_group | false |

#### Chunk 1 Parse Result

Chunk Text:

```text
the signal on both lane (S_LANE1 > P_LIMIT) and (S_LANE2 > P_LIMIT) are valid
```

Chunk Entities:

```json
[
  {
    "mention": "S_LANE1",
    "type": "SIGNAL",
    "canonical_name": "S_LANE1"
  },
  {
    "mention": "S_LANE2",
    "type": "SIGNAL",
    "canonical_name": "S_LANE2"
  },
  {
    "mention": "P_LIMIT",
    "type": "PARAMETER",
    "canonical_name": "P_LIMIT"
  },
  {
    "mention": "valid",
    "type": "STATE",
    "canonical_name": "valid"
  }
]
```

Parse Result:

```json
{
  "condition_type": "quantified_member_expression_group",
  "group_mention": "the signal on both lane",
  "quantifier": "ALL",
  "logic": "AND",
  "shared_state": "valid",
  "member_conditions": [
    {
      "type": "parameter_threshold_condition",
      "mention": "S_LANE1 > P_LIMIT",
      "signal": "S_LANE1",
      "operator": ">",
      "parameter": "P_LIMIT",
      "need_review": false
    },
    {
      "type": "parameter_threshold_condition",
      "mention": "S_LANE2 > P_LIMIT",
      "signal": "S_LANE2",
      "operator": ">",
      "parameter": "P_LIMIT",
      "need_review": false
    }
  ],
  "need_review": false
}
```

### 5. C005

Original Condition:

```text
the rack is moving to the right end stop
```

Entities Source: normalized_entities

Normalization Applied: false

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | natural_language_condition | the rack is moving to the right end stop | unknown | true |

#### Chunk 1 Parse Result

Chunk Text:

```text
the rack is moving to the right end stop
```

Chunk Entities:

```json
[
  {
    "mention": "rack",
    "type": "MECHANICAL_COMPONENT",
    "canonical_name": "SteeringRack"
  },
  {
    "mention": "right end stop",
    "type": "POSITION",
    "canonical_name": "RackRightEndStop"
  }
]
```

Parse Result:

```json
{
  "type": "unparsed_condition",
  "mention": "the rack is moving to the right end stop",
  "need_review": true
}
```

### 6. C006

Original Condition:

```text
S_VEHICLE_SPEED is valid
```

Entities Source: extract_entities_for_condition

Normalization Applied: true

Dictionary Loaded: true

Chunks Overview:

| # | chunk_type | chunk_text | parse_type | need_review |
|---|------------|------------|------------|-------------|
| 1 | atomic_condition | S_VEHICLE_SPEED is valid | unknown | true |

#### Chunk 1 Parse Result

Chunk Text:

```text
S_VEHICLE_SPEED is valid
```

Chunk Entities:

```json
[]
```

Parse Result:

```json
{
  "type": "unparsed_condition",
  "mention": "S_VEHICLE_SPEED is valid",
  "need_review": true
}
```

