import re
from typing import List, Sequence

from src.parser.condition_text_preprocessor import clean_condition_text
from src.schemas import JsonDict


TIME_VALUE_PATTERN = r"(?:'[^\']+'|\"[^\"]+\"|P_[A-Z0-9_]+|\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|second|seconds|msec|milliseconds)?)"
DURATION_NOUN_PATTERN = (
    r"(?:duration\s+time|debounce\s+period|debounce\s+time|delay\s+time|time\s+window|"
    r"time\s+interval|duration|period|timer|timeout|time)"
)
DURATION_OPERATOR_PATTERN = (
    r"(?:is\s+equal\s+to\s+or\s+greater\s+than|equal\s+to\s+or\s+greater\s+than|"
    r"greater\s+than\s+or\s+equal\s+to|is\s+greater\s+than|greater\s+than|more\s+than|"
    r"longer\s+than|above|at\s+least|no\s+less\s+than|not\s+less\s+than|"
    r"is\s+equal\s+to\s+or\s+less\s+than|equal\s+to\s+or\s+less\s+than|"
    r"less\s+than\s+or\s+equal\s+to|is\s+less\s+than|less\s+than|shorter\s+than|"
    r"below|under|at\s+most|no\s+more\s+than|not\s+more\s+than|"
    r"is\s+equal\s+to|equals|equal\s+to|is)"
)
DURATION_PATTERN = re.compile(
    rf"\b(?:"
    rf"(?:and\s+)?(?:the\s+|a\s+)?{DURATION_NOUN_PATTERN}\s+{DURATION_OPERATOR_PATTERN}\s+{TIME_VALUE_PATTERN}|"
    rf"(?:and\s+)?for\s+(?:(?:a|the)\s+)?(?:[A-Za-z0-9_]+\s+)*{DURATION_NOUN_PATTERN}\s+(?:(?:[A-Za-z0-9_]+\s+)*of\s+(?:[A-Za-z0-9_]+\s+)*)?(?:{DURATION_OPERATOR_PATTERN}\s+)?{TIME_VALUE_PATTERN}|"
    rf"(?:and\s+)?for\s+(?:at\s+least|more\s+than|greater\s+than|longer\s+than|no\s+less\s+than|not\s+less\s+than|at\s+most|no\s+more\s+than|not\s+more\s+than|less\s+than|shorter\s+than)?\s*{TIME_VALUE_PATTERN}|"
    rf"(?:and\s+)?(?:within|in)\s+(?:(?:a|the)\s+)?(?:[A-Za-z0-9_]+\s+)*{DURATION_NOUN_PATTERN}\s+{TIME_VALUE_PATTERN}|"
    rf"(?:and\s+)?within\s+{TIME_VALUE_PATTERN}|"
    rf"(?:and\s+)?(?:exceeding|exceeds)\s+(?:(?:a|the)\s+)?(?:[A-Za-z0-9_]+\s+)*{DURATION_NOUN_PATTERN}\s+{TIME_VALUE_PATTERN}"
    rf")\b",
    flags=re.IGNORECASE,
)
EXPLICIT_SIGNAL_PATTERN = re.compile(r"\b(?:S_[A-Z0-9_]+|DEM_[A-Z0-9_]+)\b")
EXPLICIT_OPERATOR_PATTERN = re.compile(
    r"(?:\bis\s+equal\s+to\b|\bgreater\s+than\b|\bless\s+than\b|>=|<=|!=|==|>|<|=)",
    flags=re.IGNORECASE,
)
CONDITION_RELATION_PATTERN = re.compile(
    r"\b(?:is|are|be|shall\s+be|should\s+be|must\s+be|become|becomes|remain|remains)\b",
    flags=re.IGNORECASE,
)
CONDITION_STATUS_PATTERN = re.compile(
    r"\b(?:valid|invalid|active|inactive|available|unavailable|degraded|enabled|disabled|failed|faulted)\b",
    flags=re.IGNORECASE,
)
TOP_LEVEL_CONNECTOR_PATTERN = re.compile(r"\b(and|or|but)\b", flags=re.IGNORECASE)
PHASE_WORDS = [
    "normal operation",
    "activation",
    "initialization",
    "startup",
    "reset",
    "shutdown",
    "operation",
]
CONTEXT_WORDS = [
    "driving cycle",
    "ignition cycle",
    "operation cycle",
    "journey",
    "cycle",
    "trip",
]
PHASE_TIMING_PATTERN = re.compile(
    rf"\b(?P<marker>before|prior\s+to|ahead\s+of|after|following|subsequent\s+to)\s+"
    rf"(?P<phase>{'|'.join(re.escape(word) for word in PHASE_WORDS)})\b",
    flags=re.IGNORECASE,
)
TEMPORAL_CONTEXT_PATTERN = re.compile(
    rf"\b(?P<marker>during|in)\s+(?:(?:a|an|the)\s+)?"
    rf"(?:(?P<relative>previous|last|prior|current|present)\s+)?"
    rf"(?P<context_braced>\{{\s*(?P<braced_context>{'|'.join(re.escape(word) for word in CONTEXT_WORDS)})\s*\}}|"
    rf"(?P<context>{'|'.join(re.escape(word) for word in CONTEXT_WORDS)}))(?=\W|$)",
    flags=re.IGNORECASE,
)


def chunk_condition_sentence(
    text: str,
    normalized_entities: Sequence[JsonDict] | None = None,
) -> JsonDict:
    """Split a condition sentence into conservative semantic chunks."""

    entities = list(normalized_entities or [])
    clean_result = clean_condition_text(text)
    text_for_chunking = str(clean_result["cleaned_text"])
    chunk_text_source = _clean_condition_text(text_for_chunking)
    chunk_specs = _collect_chunk_specs(chunk_text_source)
    chunks = [_build_chunk_from_spec(index, chunk_text_source, spec) for index, spec in enumerate(chunk_specs, start=1)]
    chunks = assign_entities_to_chunks(chunks, entities)
    return {
        "raw_text": text,
        "chunks": chunks,
        "debug_info": {
            "chunk_count": len(chunks),
            "chunk_rules": _chunk_rules(chunks),
            "text_preprocessing": clean_result,
        },
    }


def assign_entities_to_chunks(
    chunks: Sequence[JsonDict],
    normalized_entities: Sequence[JsonDict],
) -> List[JsonDict]:
    """Assign each normalized entity only to chunks where it appears."""

    assigned_chunks: List[JsonDict] = []
    for chunk in chunks:
        item = dict(chunk)
        item["entities"] = [
            dict(entity)
            for entity in normalized_entities
            if _entity_matches_chunk(entity, item)
        ]
        assigned_chunks.append(item)
    return assigned_chunks


def entities_for_span(
    text: str,
    span: Sequence[int],
    normalized_entities: Sequence[JsonDict],
) -> List[JsonDict]:
    """Return normalized entities whose mention or canonical name appears inside a span."""

    start, end = int(span[0]), int(span[1])
    chunk_entities: List[JsonDict] = []
    for entity in normalized_entities:
        entity_span = _entity_span(text, entity)
        if not entity_span:
            continue
        entity_start, entity_end = entity_span
        if start <= entity_start and entity_end <= end:
            chunk_entities.append(dict(entity))
    return chunk_entities


def find_balanced_square_bracket_span(text: str) -> list[int] | None:
    """Return the outermost balanced square bracket span as [start, end]."""

    start: int | None = None
    depth = 0
    for index, char in enumerate(text):
        if char == "[":
            if depth == 0:
                start = index
            depth += 1
        elif char == "]" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                return [start, index + 1]
    return None


def split_square_bracket_condition_group(text: str) -> JsonDict | None:
    """Split one top-level square bracket group into prefix/content/suffix."""

    span = find_balanced_square_bracket_span(text)
    if span is None:
        return None
    start, end = span
    return {
        "prefix": text[:start].strip(),
        "bracket_content": text[start + 1 : end - 1].strip(),
        "suffix": text[end:].strip(),
        "span": span,
    }


def split_bracket_group_sub_chunks(bracket_content: str) -> JsonDict:
    """Split first-level parenthesized conditions inside a square bracket group."""

    sub_chunks: List[JsonDict] = []
    logic_values: List[str] = []
    parenthesis_spans = _parenthesis_spans(bracket_content)
    for index, span in enumerate(parenthesis_spans):
        inner_span = _trim_span(bracket_content, [span[0] + 1, span[1] - 1])
        if inner_span[0] < inner_span[1]:
            sub_chunks.append({"text": bracket_content[inner_span[0] : inner_span[1]], "span": inner_span})
        if index + 1 < len(parenthesis_spans):
            separator = bracket_content[span[1] : parenthesis_spans[index + 1][0]]
            logic_match = re.search(r"\b(AND|OR)\b", separator, flags=re.IGNORECASE)
            if logic_match:
                logic_values.append(logic_match.group(1).upper())
    logic = logic_values[0] if logic_values and all(value == logic_values[0] for value in logic_values) else None
    return {"logic": logic, "sub_chunks": sub_chunks}


def split_top_level_logical_clauses(text: str) -> list[JsonDict]:
    """Split only top-level logical clauses when both sides look condition-like."""

    clauses: list[JsonDict] = []
    cursor = 0
    for match in TOP_LEVEL_CONNECTOR_PATTERN.finditer(text):
        connector_span = [match.start(), match.end()]
        if is_protected_connector(text, connector_span) or not _is_top_level_span(text, connector_span):
            continue

        left_span = _trim_span(text, [cursor, match.start()])
        right_span = _trim_span(text, [match.end(), len(text)])
        if left_span[0] >= left_span[1] or right_span[0] >= right_span[1]:
            continue
        if not looks_like_complete_condition(text[left_span[0] : left_span[1]]):
            continue
        if not looks_like_complete_condition(text[right_span[0] : right_span[1]]):
            continue

        clauses.append(
            {
                "text": text[left_span[0] : left_span[1]],
                "span": left_span,
                "logic_after": match.group(1).upper(),
            }
        )
        cursor = match.end()

    if not clauses:
        return []

    tail_span = _trim_span(text, [cursor, len(text)])
    if tail_span[0] < tail_span[1]:
        clauses.append({"text": text[tail_span[0] : tail_span[1]], "span": tail_span})
    return clauses


def extract_phase_timing_constraint(text: str) -> JsonDict | None:
    match = PHASE_TIMING_PATTERN.search(text)
    if not match or not _is_top_level_span(text, [match.start(), match.end()]):
        return None
    return _phase_timing_constraint_from_match(match)


def extract_temporal_context_constraint(text: str) -> JsonDict | None:
    match = TEMPORAL_CONTEXT_PATTERN.search(text)
    if not match or not _is_top_level_span(text, [match.start(), match.end()]):
        return None
    return _temporal_context_constraint_from_match(match)


def is_protected_connector(text: str, connector_span: Sequence[int]) -> bool:
    left = text[: int(connector_span[0])]
    right = text[int(connector_span[1]) :]
    left_normalized = re.sub(r"\s+", " ", left).lower()
    right_normalized = re.sub(r"\s+", " ", right).lower()

    if re.search(r"\bin\s+range\s+of\b[^()]*$", left_normalized):
        return True
    if re.search(r"\bbetween\b[^()]*$", left_normalized):
        return True
    if re.search(r"\b(?:at\s+least\s+)?one\s+of\b[^()]*$", left_normalized):
        return True
    if re.search(r"\bboth\b[^()]*$", left_normalized) and re.search(r"\b(?:is|are|valid|invalid|active|inactive|available|degraded)\b", right_normalized):
        return True
    return False


def looks_like_complete_condition(text: str) -> bool:
    candidate = text.strip()
    return bool(
        CONDITION_RELATION_PATTERN.search(candidate)
        or EXPLICIT_OPERATOR_PATTERN.search(candidate)
        or CONDITION_STATUS_PATTERN.search(candidate)
        or EXPLICIT_SIGNAL_PATTERN.search(candidate)
        or re.search(r"\b(?:COMPONENT|SIGNAL)\b", candidate, flags=re.IGNORECASE)
    )


def _collect_chunk_specs(text: str, allow_logical_split: bool = True) -> List[tuple]:
    square_bracket_specs = _square_bracket_group_specs(text)
    if square_bracket_specs:
        return square_bracket_specs

    all_parenthesis_spans = _parenthesis_spans(text)
    parenthesis_duration_specs = _parenthesis_duration_chunk_specs(text, all_parenthesis_spans)
    if parenthesis_duration_specs:
        return parenthesis_duration_specs

    duration_spans = [_duration_match_span(text, match) for match in DURATION_PATTERN.finditer(text)]
    if duration_spans:
        parenthesis_spans = [
            span
            for span in all_parenthesis_spans
            if _should_split_parenthesis(text[span[0] + 1 : span[1] - 1])
        ]
        return _collect_occupied_span_specs(text, parenthesis_spans, duration_spans)

    temporal_specs = _temporal_constraint_specs(text)
    if temporal_specs:
        return temporal_specs

    if allow_logical_split:
        logical_specs = _logical_clause_specs(text)
        if logical_specs:
            return logical_specs

    parenthesis_spans = [
        span
        for span in all_parenthesis_spans
        if _should_split_parenthesis(text[span[0] + 1 : span[1] - 1])
    ]
    return _collect_occupied_span_specs(text, parenthesis_spans, [])


def _collect_occupied_span_specs(
    text: str,
    parenthesis_spans: Sequence[Sequence[int]],
    duration_spans: Sequence[Sequence[int]],
) -> List[tuple]:
    occupied_spans = sorted(parenthesis_spans + duration_spans, key=lambda span: span[0])

    if _parenthesis_spans(text) and not occupied_spans:
        span = _trim_span(text, [0, len(text)])
        return [(span, _classify_main_chunk(text[span[0] : span[1]], has_special_structure=False), "full_sentence")]

    specs: List[tuple[list[int], str, str]] = []
    cursor = 0
    first_parenthesis_start = parenthesis_spans[0][0] if parenthesis_spans else None
    for span in occupied_spans:
        if cursor < span[0]:
            specs.extend(_main_clause_specs(text, [cursor, span[0]], first_parenthesis_start))
        if span in parenthesis_spans:
            inner_span = _trim_span(text, [span[0] + 1, span[1] - 1])
            if inner_span[0] < inner_span[1]:
                specs.append((inner_span, _classify_parenthesis_chunk(text[inner_span[0] : inner_span[1]]), "parenthesis"))
        else:
            specs.append((span, "duration_constraint", "temporal_phrase"))
        cursor = max(cursor, span[1])

    if cursor < len(text):
        specs.extend(_main_clause_specs(text, [cursor, len(text)], first_parenthesis_start))

    cleaned_specs = []
    for span, chunk_type, source in specs:
        if span[0] >= span[1]:
            continue
        chunk_text = _clean_chunk_text(text[span[0] : span[1]])
        if not chunk_text or _is_trivial_punctuation_chunk(chunk_text):
            continue
        cleaned_specs.append((span, chunk_type, source))
    if cleaned_specs:
        return cleaned_specs

    span = _trim_span(text, [0, len(text)])
    return [(span, _classify_main_chunk(text[span[0] : span[1]], has_special_structure=False), "main_clause")]


def _temporal_constraint_specs(text: str) -> List[tuple]:
    constraints = [
        constraint
        for constraint in (
            extract_phase_timing_constraint(text),
            extract_temporal_context_constraint(text),
        )
        if constraint
    ]
    if not constraints:
        return []
    constraint = sorted(constraints, key=lambda item: item["span"][0])[0]
    span = constraint["span"]
    specs: List[tuple] = []
    if span[0] > 0:
        specs.extend(_main_clause_specs(text, [0, span[0]], None))
    metadata = dict(constraint)
    metadata.pop("span", None)
    metadata.pop("chunk_type", None)
    metadata.pop("source", None)
    metadata.pop("text", None)
    specs.append((span, constraint["chunk_type"], "temporal_phrase", metadata))
    if span[1] < len(text):
        specs.extend(_main_clause_specs(text, [span[1], len(text)], None))
    return _clean_specs(text, specs)


def _logical_clause_specs(text: str) -> List[tuple]:
    clauses = split_top_level_logical_clauses(text)
    if len(clauses) <= 1:
        return []

    specs: List[tuple] = []
    for clause in clauses:
        clause_span = clause["span"]
        clause_text = text[clause_span[0] : clause_span[1]]
        clause_specs = _collect_chunk_specs(clause_text, allow_logical_split=False)
        offset_specs: List[tuple] = []
        for spec in clause_specs:
            span, chunk_type, source, metadata = _normalize_spec(spec)
            offset_specs.append(([span[0] + clause_span[0], span[1] + clause_span[0]], chunk_type, source, metadata))
        if offset_specs and clause.get("logic_after"):
            span, chunk_type, source, metadata = offset_specs[-1]
            metadata = dict(metadata)
            metadata["logic_after"] = clause["logic_after"]
            if clause["logic_after"] == "BUT":
                metadata["semantic_relation"] = "contrast"
            offset_specs[-1] = (span, chunk_type, source, metadata)
        specs.extend(offset_specs)
    return specs


def _square_bracket_group_specs(text: str) -> List[tuple[list[int], str, str]]:
    parts = split_square_bracket_condition_group(text)
    if not parts:
        return []

    bracket_start, bracket_end = parts["span"]
    specs: List[tuple[list[int], str, str]] = []

    prefix_span = _trim_span(text, [0, bracket_start])
    if prefix_span[0] < prefix_span[1]:
        specs.append(
            (
                prefix_span,
                _classify_main_chunk(text[prefix_span[0] : prefix_span[1]], has_special_structure=True),
                "pre_bracket",
            )
        )

    bracket_span = _trim_span(text, [bracket_start + 1, bracket_end - 1])
    if bracket_span[0] < bracket_span[1]:
        specs.append((bracket_span, "bracketed_condition_group", "bracketed_condition_group"))

    suffix_span = _trim_span(text, [bracket_end, len(text)])
    if suffix_span[0] < suffix_span[1]:
        suffix_text = text[suffix_span[0] : suffix_span[1]]
        suffix_type = "duration_constraint" if DURATION_PATTERN.fullmatch(suffix_text) else _classify_main_chunk(
            suffix_text,
            has_special_structure=False,
        )
        suffix_source = "temporal_phrase" if suffix_type == "duration_constraint" else "post_bracket"
        specs.append((suffix_span, suffix_type, suffix_source))

    return [
        (span, chunk_type, source)
        for span, chunk_type, source in specs
        if not _is_trivial_punctuation_chunk(_clean_chunk_text(text[span[0] : span[1]]))
    ]


def _parenthesis_duration_chunk_specs(
    text: str,
    parenthesis_spans: Sequence[Sequence[int]],
) -> List[tuple[list[int], str, str]]:
    for parenthesis_span in parenthesis_spans:
        inner_start, inner_end = int(parenthesis_span[0]) + 1, int(parenthesis_span[1]) - 1
        duration_spans = [
            _duration_match_span(text, match)
            for match in DURATION_PATTERN.finditer(text)
            if inner_start <= match.start() and match.end() <= inner_end
        ]
        if not duration_spans:
            continue

        specs: List[tuple[list[int], str, str]] = []
        specs.extend(_main_clause_specs(text, [0, int(parenthesis_span[0])], int(parenthesis_span[0])))

        cursor = inner_start
        for duration_span in duration_spans:
            before_span = _trim_span(text, [cursor, duration_span[0]])
            if before_span[0] < before_span[1]:
                specs.append((before_span, _classify_parenthesis_chunk(text[before_span[0] : before_span[1]]), "parenthesis"))
            specs.append((duration_span, "duration_constraint", "temporal_phrase"))
            cursor = duration_span[1]

        after_span = _trim_span(text, [cursor, inner_end])
        if after_span[0] < after_span[1]:
            specs.append((after_span, _classify_parenthesis_chunk(text[after_span[0] : after_span[1]]), "parenthesis"))

        if int(parenthesis_span[1]) < len(text):
            specs.extend(_main_clause_specs(text, [int(parenthesis_span[1]), len(text)], int(parenthesis_span[0])))
        return _clean_specs(text, specs)
    return []


def _main_clause_specs(
    text: str,
    raw_span: list[int],
    first_parenthesis_start: int | None,
) -> List[tuple[list[int], str, str]]:
    span = _trim_span(text, raw_span)
    if span[0] >= span[1]:
        return []

    source = "pre_parenthesis" if first_parenthesis_start is not None and span[1] <= first_parenthesis_start else "main_clause"
    chunk_text = text[span[0] : span[1]]
    return [(span, _classify_main_chunk(chunk_text, has_special_structure=first_parenthesis_start is not None), source)]


def _build_chunk_from_spec(index: int, text: str, spec: tuple) -> JsonDict:
    span, chunk_type, source, metadata = _normalize_spec(spec)
    chunk = _build_chunk(index, text, span, chunk_type, source)
    chunk.update(metadata)
    return chunk


def _build_chunk(
    index: int,
    text: str,
    span: list[int],
    chunk_type: str,
    source: str,
) -> JsonDict:
    chunk_text = _clean_chunk_text(text[span[0] : span[1]])
    return {
        "chunk_id": f"CHUNK_{index}",
        "chunk_type": chunk_type,
        "text": chunk_text,
        "span": span,
        "entities": [],
        "source": source,
        "confidence": _confidence_for_chunk_type(chunk_type),
        "need_review": chunk_type == "natural_language_event",
    }


def _normalize_spec(spec: tuple) -> tuple[list[int], str, str, JsonDict]:
    if len(spec) == 4:
        span, chunk_type, source, metadata = spec
        return list(span), str(chunk_type), str(source), dict(metadata)
    span, chunk_type, source = spec
    return list(span), str(chunk_type), str(source), {}


def _duration_match_span(text: str, match: re.Match[str]) -> list[int]:
    span = _trim_span(text, [match.start(), match.end()])
    matched_text = text[span[0] : span[1]]
    and_match = re.match(r"and\s+", matched_text, flags=re.IGNORECASE)
    if and_match:
        span[0] += and_match.end()
        span = _trim_span(text, span)
    return span


def _parenthesis_spans(text: str) -> List[list[int]]:
    spans: List[list[int]] = []
    start: int | None = None
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            if depth == 0:
                start = index
            depth += 1
        elif char == ")" and depth:
            depth -= 1
            if depth == 0 and start is not None:
                spans.append([start, index + 1])
                start = None
    return spans


def _bracket_spans(text: str) -> List[list[int]]:
    span = find_balanced_square_bracket_span(text)
    return [span] if span else []


def _classify_parenthesis_chunk(chunk_text: str) -> str:
    if EXPLICIT_SIGNAL_PATTERN.search(chunk_text) or EXPLICIT_OPERATOR_PATTERN.search(chunk_text):
        return "explicit_signal_definition"
    return _classify_main_chunk(chunk_text, has_special_structure=True)


def _should_split_parenthesis(chunk_text: str) -> bool:
    return bool(EXPLICIT_OPERATOR_PATTERN.search(chunk_text))


def _classify_main_chunk(chunk_text: str, has_special_structure: bool) -> str:
    if has_special_structure and CONDITION_RELATION_PATTERN.search(chunk_text):
        return "natural_language_condition"
    if _looks_like_atomic_condition(chunk_text):
        return "atomic_condition"
    if CONDITION_RELATION_PATTERN.search(chunk_text):
        return "natural_language_condition"
    return "natural_language_event"


def _looks_like_atomic_condition(chunk_text: str) -> bool:
    return bool(
        EXPLICIT_SIGNAL_PATTERN.search(chunk_text)
        or EXPLICIT_OPERATOR_PATTERN.search(chunk_text)
    )


def _confidence_for_chunk_type(chunk_type: str) -> float:
    if chunk_type in {
        "explicit_signal_definition",
        "duration_constraint",
        "phase_timing_constraint",
        "temporal_context_constraint",
    }:
        return 0.9
    if chunk_type == "natural_language_event":
        return 0.6
    return 0.8


def _chunk_rules(chunks: Sequence[JsonDict]) -> List[JsonDict]:
    return [
        {
            "chunk_id": chunk.get("chunk_id"),
            "source": chunk.get("source"),
            "chunk_type": chunk.get("chunk_type"),
        }
        for chunk in chunks
    ]


def _is_trivial_punctuation_chunk(text: str) -> bool:
    return bool(re.fullmatch(r"[.,;:]+", text.strip()))


def _clean_chunk_text(text: str) -> str:
    cleaned = text.strip()
    if cleaned.endswith(".") and not re.search(r"\d+\.\d+\w*$", cleaned):
        cleaned = cleaned[:-1].rstrip()
    return cleaned


def _clean_condition_text(text: str) -> str:
    return _clean_chunk_text(text)


def _clean_specs(
    text: str,
    specs: Sequence[tuple],
) -> List[tuple]:
    cleaned_specs = []
    for spec in specs:
        span, chunk_type, source, metadata = _normalize_spec(spec)
        if span[0] >= span[1]:
            continue
        chunk_text = _clean_chunk_text(text[span[0] : span[1]])
        if not chunk_text or _is_trivial_punctuation_chunk(chunk_text):
            continue
        if metadata:
            cleaned_specs.append((span, chunk_type, source, metadata))
        else:
            cleaned_specs.append((span, chunk_type, source))
    return cleaned_specs


def _is_top_level_span(text: str, span: Sequence[int]) -> bool:
    target = int(span[0])
    paren_depth = 0
    bracket_depth = 0
    quote: str | None = None
    index = 0
    while index < target:
        char = text[index]
        if quote:
            if char == quote:
                quote = None
        elif char in {"'", '"'}:
            quote = char
        elif char == "(":
            paren_depth += 1
        elif char == ")" and paren_depth:
            paren_depth -= 1
        elif char == "[":
            bracket_depth += 1
        elif char == "]" and bracket_depth:
            bracket_depth -= 1
        index += 1
    return quote is None and paren_depth == 0 and bracket_depth == 0


def _phase_timing_constraint_from_match(match: re.Match[str]) -> JsonDict:
    marker = re.sub(r"\s+", " ", match.group("marker").lower())
    timing_relation = "before_phase" if marker in {"before", "prior to", "ahead of"} else "after_phase"
    return {
        "chunk_type": "phase_timing_constraint",
        "text": match.group(0),
        "span": [match.start(), match.end()],
        "source": "temporal_phrase",
        "timing_relation": timing_relation,
        "phase": _normalize_temporal_value(match.group("phase")),
    }


def _temporal_context_constraint_from_match(match: re.Match[str]) -> JsonDict:
    relative = match.group("relative")
    context = match.group("braced_context") or match.group("context")
    return {
        "chunk_type": "temporal_context_constraint",
        "text": match.group(0),
        "span": [match.start(), match.end()],
        "source": "temporal_phrase",
        "timing_relation": "during_context",
        "context": _normalize_temporal_value(context),
        "relative_time": _normalize_relative_time(relative),
    }


def _normalize_temporal_value(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip("{}")).lower()


def _normalize_relative_time(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.lower()
    if normalized in {"previous", "last", "prior"}:
        return "previous"
    if normalized in {"current", "present"}:
        return "current"
    return normalized


def _trim_span(text: str, span: Sequence[int]) -> list[int]:
    start, end = int(span[0]), int(span[1])
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return [start, end]


def _entity_matches_chunk(entity: JsonDict, chunk: JsonDict) -> bool:
    entity_span = _explicit_entity_span(entity)
    chunk_span = chunk.get("span", [0, 0])
    if entity_span:
        return _span_contains(chunk_span, entity_span)

    chunk_text = str(chunk.get("text", ""))
    mention = str(entity.get("mention") or "").strip()
    if mention and _contains_entity_text(chunk_text, mention):
        return True
    return False


def _explicit_entity_span(entity: JsonDict) -> tuple[int, int] | None:
    if entity.get("start") is None or entity.get("end") is None:
        return None
    try:
        return (int(entity["start"]), int(entity["end"]))
    except (TypeError, ValueError):
        return None


def _span_contains(container_span: Sequence[int], child_span: Sequence[int]) -> bool:
    container_start, container_end = int(container_span[0]), int(container_span[1])
    child_start, child_end = int(child_span[0]), int(child_span[1])
    return container_start <= child_start and child_end <= container_end


def _span_inside_any(span: Sequence[int], containers: Sequence[Sequence[int]]) -> bool:
    return any(_span_contains(container, span) for container in containers)


def _contains_entity_text(text: str, value: str) -> bool:
    return bool(re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=re.IGNORECASE))


def _entity_span(text: str, entity: JsonDict) -> tuple[int, int] | None:
    for flags in (0, re.IGNORECASE):
        for field_name in ("mention", "canonical_name"):
            value = str(entity.get(field_name, "")).strip()
            if not value:
                continue
            match = re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, flags=flags)
            if match:
                return (match.start(), match.end())
    return None
