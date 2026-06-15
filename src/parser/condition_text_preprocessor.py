from src.schemas import JsonDict


BRACKET_PAIRS = [
    ("(", ")", "parenthesis"),
    ("[", "]", "square_bracket"),
    ("{", "}", "curly_brace"),
]


def clean_condition_text(text: str) -> JsonDict:
    """Remove only unmatched outer bracket noise before semantic chunking."""

    original_text = text
    cleaned_text = text.strip()
    cleaning_actions: list[JsonDict] = []

    changed = True
    while changed:
        changed = False
        for opening, closing, name in BRACKET_PAIRS:
            if cleaned_text.startswith(opening) and closing not in cleaned_text:
                cleaning_actions.append(
                    {
                        "action": f"remove_unmatched_opening_{name}",
                        "char": opening,
                        "position": 0,
                    }
                )
                cleaned_text = cleaned_text[1:].strip()
                changed = True
                break
            if cleaned_text.endswith(closing) and opening not in cleaned_text:
                position = len(cleaned_text) - 1
                cleaning_actions.append(
                    {
                        "action": f"remove_unmatched_closing_{name}",
                        "char": closing,
                        "position": position,
                    }
                )
                cleaned_text = cleaned_text[:-1].strip()
                changed = True
                break

    changed_result = bool(cleaning_actions)
    return {
        "original_text": original_text,
        "cleaned_text": cleaned_text,
        "changed": changed_result,
        "cleaning_actions": cleaning_actions,
        "need_review": changed_result,
    }
