# Condition Semantic Chunking Debug Report

## Summary

* Total records: 5
* Parsed records: 5
* Skipped records: 0
* Total chunks: 7
* Chunk type distribution:
  * atomic_condition: 1
  * duration_constraint: 1
  * explicit_signal_definition: 1
  * natural_language_condition: 4

## Records

### 1. C001

Original Condition:

```text
vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT
```

Chunks:

| # | chunk_type | source | span | confidence | need_review | text |
| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |
| 1 | natural_language_condition | pre_parenthesis | [0, 24] | 0.8 | false | vehicle speed is invalid |
| 2 | explicit_signal_definition | parenthesis | [26, 61] | 0.9 | false | S_VEHICLE_SPEED is equal to INVALID |
| 3 | duration_constraint | temporal_phrase | [63, 88] | 0.9 | false | for a duration of P_LIMIT |

Entities per Chunk:

#### CHUNK_1

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

#### CHUNK_2

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

#### CHUNK_3

```json
[
  {
    "mention": "P_LIMIT",
    "type": "PARAMETER",
    "canonical_name": "P_LIMIT"
  }
]
```

Raw Chunk Result:

```json
{
  "raw_text": "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT",
  "chunks": [
    {
      "chunk_id": "CHUNK_1",
      "chunk_type": "natural_language_condition",
      "text": "vehicle speed is invalid",
      "span": [
        0,
        24
      ],
      "entities": [
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
      ],
      "source": "pre_parenthesis",
      "confidence": 0.8,
      "need_review": false
    },
    {
      "chunk_id": "CHUNK_2",
      "chunk_type": "explicit_signal_definition",
      "text": "S_VEHICLE_SPEED is equal to INVALID",
      "span": [
        26,
        61
      ],
      "entities": [
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
      ],
      "source": "parenthesis",
      "confidence": 0.9,
      "need_review": false
    },
    {
      "chunk_id": "CHUNK_3",
      "chunk_type": "duration_constraint",
      "text": "for a duration of P_LIMIT",
      "span": [
        63,
        88
      ],
      "entities": [
        {
          "mention": "P_LIMIT",
          "type": "PARAMETER",
          "canonical_name": "P_LIMIT"
        }
      ],
      "source": "temporal_phrase",
      "confidence": 0.9,
      "need_review": false
    }
  ],
  "debug_info": {
    "chunk_count": 3,
    "chunk_rules": [
      {
        "chunk_id": "CHUNK_1",
        "source": "pre_parenthesis",
        "chunk_type": "natural_language_condition"
      },
      {
        "chunk_id": "CHUNK_2",
        "source": "parenthesis",
        "chunk_type": "explicit_signal_definition"
      },
      {
        "chunk_id": "CHUNK_3",
        "source": "temporal_phrase",
        "chunk_type": "duration_constraint"
      }
    ],
    "text_preprocessing": {
      "original_text": "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT",
      "cleaned_text": "vehicle speed is invalid (S_VEHICLE_SPEED is equal to INVALID) for a duration of P_LIMIT",
      "changed": false,
      "cleaning_actions": [],
      "need_review": false
    }
  }
}
```

### 2. C002

Original Condition:

```text
S_VEHICLE_SPEED is valid
```

Chunks:

| # | chunk_type | source | span | confidence | need_review | text |
| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |
| 1 | atomic_condition | main_clause | [0, 24] | 0.8 | false | S_VEHICLE_SPEED is valid |

Entities per Chunk:

#### CHUNK_1

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

Raw Chunk Result:

```json
{
  "raw_text": "S_VEHICLE_SPEED is valid",
  "chunks": [
    {
      "chunk_id": "CHUNK_1",
      "chunk_type": "atomic_condition",
      "text": "S_VEHICLE_SPEED is valid",
      "span": [
        0,
        24
      ],
      "entities": [
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
      ],
      "source": "main_clause",
      "confidence": 0.8,
      "need_review": false
    }
  ],
  "debug_info": {
    "chunk_count": 1,
    "chunk_rules": [
      {
        "chunk_id": "CHUNK_1",
        "source": "main_clause",
        "chunk_type": "atomic_condition"
      }
    ],
    "text_preprocessing": {
      "original_text": "S_VEHICLE_SPEED is valid",
      "cleaned_text": "S_VEHICLE_SPEED is valid",
      "changed": false,
      "cleaning_actions": [],
      "need_review": false
    }
  }
}
```

### 3. C003

Original Condition:

```text
vehicle speed is in range of 50kph and 100kph
```

Chunks:

| # | chunk_type | source | span | confidence | need_review | text |
| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |
| 1 | natural_language_condition | main_clause | [0, 45] | 0.8 | false | vehicle speed is in range of 50kph and 100kph |

Entities per Chunk:

#### CHUNK_1

```json
[
  {
    "mention": "vehicle speed",
    "type": "SIGNAL",
    "canonical_name": "S_VEHICLE_SPEED"
  }
]
```

Raw Chunk Result:

```json
{
  "raw_text": "vehicle speed is in range of 50kph and 100kph",
  "chunks": [
    {
      "chunk_id": "CHUNK_1",
      "chunk_type": "natural_language_condition",
      "text": "vehicle speed is in range of 50kph and 100kph",
      "span": [
        0,
        45
      ],
      "entities": [
        {
          "mention": "vehicle speed",
          "type": "SIGNAL",
          "canonical_name": "S_VEHICLE_SPEED"
        }
      ],
      "source": "main_clause",
      "confidence": 0.8,
      "need_review": false
    }
  ],
  "debug_info": {
    "chunk_count": 1,
    "chunk_rules": [
      {
        "chunk_id": "CHUNK_1",
        "source": "main_clause",
        "chunk_type": "natural_language_condition"
      }
    ],
    "text_preprocessing": {
      "original_text": "vehicle speed is in range of 50kph and 100kph",
      "cleaned_text": "vehicle speed is in range of 50kph and 100kph",
      "changed": false,
      "cleaning_actions": [],
      "need_review": false
    }
  }
}
```

### 4. C004

Original Condition:

```text
the rack is moving to the right end stop
```

Chunks:

| # | chunk_type | source | span | confidence | need_review | text |
| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |
| 1 | natural_language_condition | main_clause | [0, 40] | 0.8 | false | the rack is moving to the right end stop |

Entities per Chunk:

#### CHUNK_1

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

Raw Chunk Result:

```json
{
  "raw_text": "the rack is moving to the right end stop",
  "chunks": [
    {
      "chunk_id": "CHUNK_1",
      "chunk_type": "natural_language_condition",
      "text": "the rack is moving to the right end stop",
      "span": [
        0,
        40
      ],
      "entities": [
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
      ],
      "source": "main_clause",
      "confidence": 0.8,
      "need_review": false
    }
  ],
  "debug_info": {
    "chunk_count": 1,
    "chunk_rules": [
      {
        "chunk_id": "CHUNK_1",
        "source": "main_clause",
        "chunk_type": "natural_language_condition"
      }
    ],
    "text_preprocessing": {
      "original_text": "the rack is moving to the right end stop",
      "cleaned_text": "the rack is moving to the right end stop",
      "changed": false,
      "cleaning_actions": [],
      "need_review": false
    }
  }
}
```

### 5. C005

Original Condition:

```text
both vehicle speed signals are valid
```

Chunks:

| # | chunk_type | source | span | confidence | need_review | text |
| - | ---------- | ------ | ---- | ---------- | ----------- | ---- |
| 1 | natural_language_condition | main_clause | [0, 36] | 0.8 | false | both vehicle speed signals are valid |

Entities per Chunk:

#### CHUNK_1

```json
[
  {
    "mention": "vehicle speed signals",
    "type": "SIGNAL",
    "canonical_name": "VehicleSpeedGroup",
    "members": [
      "S_MAIN_VEHICLE_SPEED",
      "S_SECONDARY_VEHICLE_SPEED"
    ]
  },
  {
    "mention": "valid",
    "type": "STATE",
    "canonical_name": "valid"
  }
]
```

Raw Chunk Result:

```json
{
  "raw_text": "both vehicle speed signals are valid",
  "chunks": [
    {
      "chunk_id": "CHUNK_1",
      "chunk_type": "natural_language_condition",
      "text": "both vehicle speed signals are valid",
      "span": [
        0,
        36
      ],
      "entities": [
        {
          "mention": "vehicle speed signals",
          "type": "SIGNAL",
          "canonical_name": "VehicleSpeedGroup",
          "members": [
            "S_MAIN_VEHICLE_SPEED",
            "S_SECONDARY_VEHICLE_SPEED"
          ]
        },
        {
          "mention": "valid",
          "type": "STATE",
          "canonical_name": "valid"
        }
      ],
      "source": "main_clause",
      "confidence": 0.8,
      "need_review": false
    }
  ],
  "debug_info": {
    "chunk_count": 1,
    "chunk_rules": [
      {
        "chunk_id": "CHUNK_1",
        "source": "main_clause",
        "chunk_type": "natural_language_condition"
      }
    ],
    "text_preprocessing": {
      "original_text": "both vehicle speed signals are valid",
      "cleaned_text": "both vehicle speed signals are valid",
      "changed": false,
      "cleaning_actions": [],
      "need_review": false
    }
  }
}
```

