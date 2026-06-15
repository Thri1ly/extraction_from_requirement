import re
from typing import List, Sequence

from src.schemas import JsonDict


DURATION_PATTERN = re.compile(
    r"\b(?:"
    r"for\s+a\s+duration\s+of\s+\S+|"
    r"for\s+at\s+least\s+\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|second|seconds|msec|milliseconds)?|"
    r"within\s+\d+(?:\.\d+)?\s*(?:ms|s|sec|secs|second|seconds|msec|milliseconds)?"
    r")\b",
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


def chunk_condition_sentence(
    text: str,
    normalized_entities: Sequence[JsonDict] | None = None,
) -> JsonDict:
    """Split a condition sentence into conservative semantic chunks."""

    entities = list(normalized_entities or [])
    chunk_specs = _collect_chunk_specs(text)
    chunks = [
        _build_chunk(index, text, span, chunk_type, source)
        for index, (span, chunk_type, source) in enumerate(chunk_specs, start=1)
    ]
    chunks = assign_entities_to_chunks(chunks, entities)
    return {
        "raw_text": text,
        "chunks": chunks,
        "debug_info": {
            "chunk_count": len(chunks),
            "chunk_rules": _chunk_rules(chunks),
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


def _collect_chunk_specs(text: str) -> List[tuple[list[int], str, str]]:
    all_parenthesis_spans = _parenthesis_spans(text)
    parenthesis_spans = [
        span
        for span in all_parenthesis_spans
        if _should_split_parenthesis(text[span[0] + 1 : span[1] - 1])
    ]
    duration_spans = [_trim_span(text, [match.start(), match.end()]) for match in DURATION_PATTERN.finditer(text)]
    occupied_spans = sorted(parenthesis_spans + duration_spans, key=lambda span: span[0])

    if all_parenthesis_spans and not occupied_spans:
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
    if chunk_type in {"explicit_signal_definition", "duration_constraint"}:
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
