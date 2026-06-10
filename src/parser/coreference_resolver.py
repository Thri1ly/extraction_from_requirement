from typing import List, Tuple

from src.schemas import JsonDict


PRONOUN_TARGETS = {"it", "this signal", "the signal", "the fault", "the indicator"}
TORQUE_SIGNALS = {"S_TORQUE_DEMAND", "S_ASSIST_TORQUE", "S_DRIVER_TORQUE", "S_COLUMN_TORQUE"}


def _candidate_label(candidate: JsonDict) -> str:
    return str(candidate.get("target_mention") or candidate.get("mention") or candidate.get("canonical_name"))


def _candidate_canonical(candidate: JsonDict) -> str:
    return str(candidate.get("target") or candidate.get("canonical_name"))


def collect_candidates(actions: List[JsonDict], normalized_entities: List[JsonDict]) -> List[JsonDict]:
    """Collect possible antecedents from parsed actions and normalized entities."""

    candidates: List[JsonDict] = []
    for action in actions:
        canonical = action.get("target")
        if canonical and action.get("type") in {"calculate_signal", "adjust_signal", "set_fault", "set_indicator"}:
            candidates.append(
                {
                    "mention": action.get("target_mention") or canonical,
                    "canonical_name": canonical,
                    "source": f"action:{action.get('type')}",
                }
            )
    for entity in normalized_entities:
        if entity.get("type") in {"signal", "fault", "indicator"}:
            candidates.append(entity)
    return candidates


def _select_candidate(
    action_index: int,
    action: JsonDict,
    actions: List[JsonDict],
    normalized_entities: List[JsonDict],
) -> Tuple[JsonDict | None, List[JsonDict], bool]:
    """Select an antecedent for one pronoun-bearing action."""

    previous_targets = [
        {
            "mention": prior.get("target_mention") or prior.get("target"),
            "canonical_name": prior.get("target"),
            "source": f"previous_action:{prior.get('type')}",
        }
        for prior in actions[:action_index]
        if prior.get("target")
    ]
    if previous_targets:
        unit = action.get("unit")
        narrowed = [candidate for candidate in reversed(previous_targets) if _matches_unit(candidate, unit)]
        if narrowed:
            return narrowed[0], previous_targets, False
        return previous_targets[-1], previous_targets, False

    all_candidates = collect_candidates(actions[:action_index], normalized_entities)
    unit_candidates = [candidate for candidate in all_candidates if _matches_unit(candidate, action.get("unit"))]
    candidates = unit_candidates or all_candidates
    unique = _unique_candidates(candidates)
    if len(unique) == 1:
        return unique[0], unique, False
    return None, unique, True


def _matches_unit(candidate: JsonDict, unit: str | None) -> bool:
    canonical = str(candidate.get("canonical_name") or candidate.get("target") or "")
    if unit == "Nm":
        return canonical in TORQUE_SIGNALS or "TORQUE" in canonical
    if unit == "kph":
        return "VEHICLE_SPEED" in canonical
    return True


def _unique_candidates(candidates: List[JsonDict]) -> List[JsonDict]:
    seen = set()
    unique = []
    for candidate in candidates:
        canonical = candidate.get("canonical_name") or candidate.get("target")
        if canonical in seen:
            continue
        seen.add(canonical)
        unique.append(candidate)
    return unique


def resolve_coreferences(
    text: str,
    parsed_actions: List[JsonDict],
    normalized_entities: List[JsonDict] | None = None,
) -> JsonDict:
    """Resolve Layer6 pronoun references and update parsed actions in-place."""

    del text
    normalized_entities = normalized_entities or []
    resolutions: List[JsonDict] = []
    needs_review = False
    for index, action in enumerate(parsed_actions):
        mention = str(action.get("target_mention") or "").lower()
        if not action.get("needs_coreference") and mention not in PRONOUN_TARGETS:
            continue

        selected, candidates, review = _select_candidate(index, action, parsed_actions, normalized_entities)
        if selected:
            action["target"] = _candidate_canonical(selected)
            action["resolved_target_mention"] = _candidate_label(selected)
            action["needs_coreference"] = False
        else:
            action["need_review"] = True
        needs_review = needs_review or review
        resolutions.append(
            {
                "pronoun": action.get("target_mention"),
                "action_type": action.get("type"),
                "resolved_to": _candidate_label(selected) if selected else None,
                "canonical_target": _candidate_canonical(selected) if selected else None,
                "need_review": review,
                "candidates": [
                    {
                        "mention": candidate.get("mention"),
                        "canonical_name": candidate.get("canonical_name"),
                        "source": candidate.get("source"),
                    }
                    for candidate in candidates
                ],
            }
        )

    return {"need_review": needs_review, "resolutions": resolutions}
