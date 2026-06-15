import re
from typing import Sequence

from src.parser.condition_semantic_chunker import chunk_condition_sentence
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
    """Parse a simple duration constraint chunk."""

    normalized = text.strip()
    duration_of = re.fullmatch(r"for\s+a\s+duration\s+of\s+(?P<duration>\S+)", normalized, flags=re.IGNORECASE)
    if duration_of:
        return _duration_result(duration_of.group("duration"), None, "for_duration")

    at_least = re.fullmatch(
        r"for\s+at\s+least\s+(?P<duration>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if at_least:
        return _duration_result(number_value(at_least.group("duration")), at_least.group("unit"), ">=")

    within = re.fullmatch(
        r"within\s+(?P<duration>\d+(?:\.\d+)?)\s*(?P<unit>[A-Za-z]+)?",
        normalized,
        flags=re.IGNORECASE,
    )
    if within:
        return _duration_result(number_value(within.group("duration")), within.group("unit"), "<=")

    return {
        "condition_type": "duration_constraint",
        "raw_text": text,
        "need_review": True,
        "confidence": 0.3,
    }


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


def _duration_result(duration: object, unit: str | None, operator: str) -> JsonDict:
    return {
        "condition_type": "duration_constraint",
        "duration": duration,
        "unit": unit,
        "operator": operator,
        "confidence": 0.9,
    }
