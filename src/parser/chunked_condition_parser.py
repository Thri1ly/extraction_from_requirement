import re
from typing import Sequence

from src.parser.condition_semantic_chunker import DURATION_NOUN_PATTERN, TIME_VALUE_PATTERN, chunk_condition_sentence
from src.schemas import JsonDict, number_value


def parse_chunked_condition(
    text: str,
    normalized_entities: Sequence[JsonDict] | None = None,
    atomic_parser: str = "syntactic",
) -> JsonDict:
    """Chunk a condition sentence and parse each chunk into a condition group."""

    chunking = chunk_condition_sentence(text, normalized_entities or [])
    chunks = list(chunking.get("chunks", []))
    parsed_chunks = [_parse_chunk(chunk, atomic_parser) for chunk in chunks]
    debug_info = dict(chunking.get("debug_info", {}))
    debug_info.update(
        {
            "atomic_parser": atomic_parser,
            "chunk_count": len(chunks),
        }
    )
    return {
        "condition_type": "condition_group",
        "raw_text": text,
        "logic": "AND",
        "chunks": chunks,
        "parsed_chunks": parsed_chunks,
        "relations": _relations_for_chunks(chunks),
        "need_review": any(bool(parsed_chunk["parse_result"].get("need_review")) for parsed_chunk in parsed_chunks),
        "debug_info": debug_info,
    }


def parse_atomic_chunk(
    text: str,
    normalized_entities: Sequence[JsonDict] | None = None,
    atomic_parser: str = "syntactic",
) -> JsonDict:
    """Parse one chunk through the requested atomic parser implementation."""

    if atomic_parser == "syntactic":
        from src.parser.syntactic_atomic_condition_parser import parse_condition_line
    elif atomic_parser == "legacy":
        from src.parser.atomic_condition_parser import parse_condition_line
    else:
        raise ValueError(f"Unknown atomic parser '{atomic_parser}'. Expected 'syntactic' or 'legacy'.")
    return parse_condition_line(text, normalized_entities=list(normalized_entities or []))


def parse_duration_constraint(text: str) -> JsonDict:
    """Parse a duration or timing constraint chunk."""

    normalized = text.strip()
    value_info = extract_duration_value(normalized)
    if value_info.get("duration") is not None:
        operator = normalize_duration_operator(normalized)
        timing_relation = classify_timing_relation(normalized)
        duration_type = _duration_type(normalized)
        return _duration_result(
            text=normalized,
            duration=value_info["duration"],
            value=value_info.get("value"),
            unit=value_info.get("unit"),
            operator=operator,
            timing_relation=timing_relation,
            duration_type=duration_type,
        )

    return {
        "condition_type": "duration_constraint",
        "raw_text": text,
        "need_review": True,
        "confidence": 0.3,
    }


def normalize_duration_operator(text: str) -> str:
    normalized = _normalize_spaces(text).lower()
    if re.search(r"\b(?:equal to or greater than|greater than or equal to|at least|no less than|not less than)\b", normalized):
        return ">="
    if re.search(r"\b(?:equal to or less than|less than or equal to|at most|no more than|not more than)\b", normalized):
        return "<="
    if re.search(r"\b(?:greater than|more than|longer than|above|exceeding|exceeds)\b", normalized):
        return ">"
    if re.search(r"\b(?:less than|shorter than|below|under)\b", normalized):
        return "<"
    if re.search(r"\b(?:is equal to|equals|equal to)\b", normalized):
        return "="
    if re.search(rf"\b(?:the\s+|a\s+)?{DURATION_NOUN_PATTERN}\s+is\b", normalized):
        return "="
    if normalized.startswith(("within ", "in ")):
        return "<="
    if normalized.startswith("for "):
        return "for_duration"
    return "for_duration"


def classify_timing_relation(text: str) -> str:
    normalized = _normalize_spaces(text).lower()
    if normalized.startswith(("within ", "in ")):
        return "within_time"
    if normalized.startswith(("exceeding ", "exceeds ")):
        return "exceed_time"
    if normalized.startswith("for "):
        return "sustain_for"
    return "duration_compare"


def extract_duration_value(text: str) -> JsonDict:
    normalized = text.strip()
    matches = list(re.finditer(TIME_VALUE_PATTERN, normalized, flags=re.IGNORECASE))
    if not matches:
        return {"duration": None, "value": None, "unit": None}

    raw_value = matches[-1].group(0).strip()
    number_unit = re.fullmatch(
        r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>ms|s|sec|secs|second|seconds|msec|milliseconds)",
        raw_value,
        flags=re.IGNORECASE,
    )
    if number_unit:
        value = number_value(number_unit.group("value"))
        return {"duration": value, "value": value, "unit": number_unit.group("unit")}
    return {"duration": raw_value, "value": None, "unit": None}


def _parse_chunk(chunk: JsonDict, atomic_parser: str) -> JsonDict:
    if chunk.get("chunk_type") == "duration_constraint":
        parse_result = parse_duration_constraint(str(chunk.get("text", "")))
    else:
        try:
            parse_result = parse_atomic_chunk(
                str(chunk.get("text", "")),
                normalized_entities=list(chunk.get("entities", [])),
                atomic_parser=atomic_parser,
            )
        except Exception as exc:
            parse_result = _exception_fallback(chunk, exc)
        parse_result = _fallback_if_unparsed(chunk, parse_result)
    return {
        "chunk_id": chunk.get("chunk_id"),
        "chunk_type": chunk.get("chunk_type"),
        "text": chunk.get("text"),
        "parse_result": parse_result,
    }


def _fallback_if_unparsed(chunk: JsonDict, parse_result: JsonDict) -> JsonDict:
    if parse_result.get("type") != "unparsed_condition":
        return parse_result
    condition_type = "natural_language_event" if chunk.get("chunk_type") == "natural_language_event" else "unparsed_chunk"
    return {
        "condition_type": condition_type,
        "raw_text": str(chunk.get("text", "")),
        "need_review": True,
        "confidence": 0.3,
    }


def _exception_fallback(chunk: JsonDict, exc: Exception) -> JsonDict:
    return {
        "condition_type": "unparsed_chunk",
        "raw_text": str(chunk.get("text", "")),
        "need_review": True,
        "confidence": 0.3,
        "review_reason": f"atomic parser error: {type(exc).__name__}",
    }


def _relations_for_chunks(chunks: Sequence[JsonDict]) -> list[JsonDict]:
    relations: list[JsonDict] = []
    for index, chunk in enumerate(chunks[:-1]):
        next_chunk = chunks[index + 1]
        if (
            chunk.get("source") == "pre_parenthesis"
            and chunk.get("chunk_type") == "natural_language_condition"
            and next_chunk.get("source") == "parenthesis"
            and next_chunk.get("chunk_type") == "explicit_signal_definition"
        ):
            relations.append(
                {
                    "relation": "equivalent_to",
                    "source_chunk": str(chunk.get("chunk_id")),
                    "target_chunk": str(next_chunk.get("chunk_id")),
                    "reason": "parenthesized_explicit_definition",
                }
            )
    return relations


def _duration_result(
    text: str,
    duration: object,
    value: object | None,
    unit: str | None,
    operator: str,
    timing_relation: str,
    duration_type: str | None,
) -> JsonDict:
    result = {
        "condition_type": "duration_constraint",
        "text": text,
        "duration": duration,
        "value": value,
        "unit": unit,
        "operator": operator,
        "timing_relation": timing_relation,
        "confidence": 0.9,
        "need_review": False,
    }
    if duration_type:
        result["duration_type"] = duration_type
    return result


def _duration_type(text: str) -> str | None:
    normalized = _normalize_spaces(text).lower()
    for pattern, duration_type in (
        (r"\bdebounce\s+time\b", "debounce_time"),
        (r"\bdebounce\s+period\b", "debounce_period"),
        (r"\bdelay\s+time\b", "delay_time"),
        (r"\btime\s+window\b", "time_window"),
        (r"\btime\s+interval\b", "time_interval"),
        (r"\bduration\s+time\b", "duration_time"),
        (r"\bduration\b", "duration"),
        (r"\bperiod\b", "period"),
        (r"\btimer\b", "timer"),
        (r"\btimeout\b", "timeout"),
        (r"\btime\b", "time"),
    ):
        if re.search(pattern, normalized):
            return duration_type
    return None


def _normalize_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())
