from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


JsonDict = Dict[str, Any]


@dataclass
class NormalizedEntity:
    """Normalized entity mention with canonical signal or group metadata."""

    mention: str
    type: str
    canonical_name: str
    members: List[str] = field(default_factory=list)
    source: str = "rule"

    def to_dict(self) -> JsonDict:
        return asdict(self)


@dataclass
class ParseIssue:
    """Non-fatal parse issue used to mark requirements that need review."""

    layer: str
    message: str

    def to_dict(self) -> JsonDict:
        return asdict(self)


def number_value(value: str) -> int | float:
    """Convert a numeric regex capture into int when possible."""

    parsed = float(value)
    return int(parsed) if parsed.is_integer() else parsed


def unique_dicts(items: List[JsonDict], keys: Optional[List[str]] = None) -> List[JsonDict]:
    """Deduplicate dictionaries while preserving order."""

    seen = set()
    result = []
    for item in items:
        if keys:
            identity = tuple(item.get(key) for key in keys)
        else:
            identity = tuple(sorted((key, repr(value)) for key, value in item.items()))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(item)
    return result
