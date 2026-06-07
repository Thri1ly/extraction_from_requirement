import re
from typing import List

from src.normalizer import canonical_for_mention
from src.schemas import JsonDict


DEPENDENCY_RELATIONS = {
    "depend on": "depend_on",
    "depends on": "depend_on",
    "rely on": "rely_on",
    "relies on": "rely_on",
    "based on": "based_on",
    "according to": "according_to",
}

SIGNAL_PATTERN = r"Driver Torque|Column Torque|assist torque|torque demand|vehicle speed|S_[A-Z0-9_]+"


def parse_dependencies(text: str, normalized_entities: List[JsonDict] | None = None) -> List[JsonDict]:
    """Parse dependency and trend relationships."""

    del normalized_entities
    dependencies: List[JsonDict] = []
    dependencies.extend(parse_trend_dependencies(text))
    dependencies.extend(parse_dependency_relations(text))
    return dependencies


def parse_trend_dependencies(text: str) -> List[JsonDict]:
    """Parse trend dependencies such as with increasing Driver Torque."""

    dependencies: List[JsonDict] = []
    for match in re.finditer(
        rf"\bwith\s+(?P<trend>increasing|decreasing)\s+(?P<signal>{SIGNAL_PATTERN})\b",
        text,
        flags=re.IGNORECASE,
    ):
        source_trend = "increase" if match.group("trend").lower() == "increasing" else "decrease"
        lowered = text.lower()
        correlation = "unknown"
        if "reduce" in lowered or "decrease" in lowered:
            correlation = "negative" if source_trend == "increase" else "positive"
        elif "increase" in lowered:
            correlation = "positive" if source_trend == "increase" else "negative"
        dependencies.append(
            {
                "type": "trend_dependency",
                "mention": match.group(0),
                "source_signal": canonical_for_mention(match.group("signal")),
                "source_trend": source_trend,
                "correlation": correlation,
                "need_review": correlation == "unknown",
            }
        )
    return dependencies


def parse_dependency_relations(text: str) -> List[JsonDict]:
    """Parse direct signal dependency phrases such as assist torque depends on vehicle speed."""

    relations: List[JsonDict] = []
    relation_pattern = "|".join(re.escape(relation) for relation in sorted(DEPENDENCY_RELATIONS, key=len, reverse=True))
    pattern = re.compile(
        rf"(?P<target>{SIGNAL_PATTERN})\s+(?P<relation>{relation_pattern})\s+(?P<source>{SIGNAL_PATTERN})",
        flags=re.IGNORECASE,
    )
    for match in pattern.finditer(text):
        relations.append(
            {
                "type": "dependency_relation",
                "mention": match.group(0),
                "target_signal": canonical_for_mention(match.group("target")),
                "relation": DEPENDENCY_RELATIONS[match.group("relation").lower()],
                "source_signal": canonical_for_mention(match.group("source")),
                "need_review": False,
            }
        )
    return relations
