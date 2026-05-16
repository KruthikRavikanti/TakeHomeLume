from __future__ import annotations

import json
import re


FENCED_BLOCK_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


def parse_json_object(text: str) -> dict:
    return _parse_json_top_level(
        text=text,
        expected_type=dict,
        opener="{",
        closer="}",
        type_name="object",
    )


def parse_json_array(text: str) -> list:
    return _parse_json_top_level(
        text=text,
        expected_type=list,
        opener="[",
        closer="]",
        type_name="array",
    )


def _parse_json_top_level(
    text: str,
    expected_type: type,
    opener: str,
    closer: str,
    type_name: str,
):
    candidates = _json_candidates(text, opener, closer)
    last_error: Exception | None = None

    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError as exc:
            last_error = exc
            continue

        if not isinstance(parsed, expected_type):
            raise ValueError(f"Parsed JSON value is not a {type_name}.")
        return parsed

    if last_error is not None:
        raise ValueError(f"Could not parse JSON {type_name} from LLM response: {last_error}") from last_error
    raise ValueError(f"Could not find a JSON {type_name} in LLM response.")


def _json_candidates(text: str, opener: str, closer: str) -> list[str]:
    stripped = text.strip()
    candidates = []

    if stripped:
        candidates.append(stripped)

    candidates.extend(match.group(1).strip() for match in FENCED_BLOCK_RE.finditer(text))

    extracted = _extract_first_balanced_value(text, opener, closer)
    if extracted is not None:
        candidates.append(extracted)

    deduped = []
    seen = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            deduped.append(candidate)
            seen.add(candidate)
    return deduped


def _extract_first_balanced_value(text: str, opener: str, closer: str) -> str | None:
    start = text.find(opener)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False

    for index in range(start, len(text)):
        char = text[index]

        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == opener:
            depth += 1
        elif char == closer:
            depth -= 1
            if depth == 0:
                return text[start : index + 1]

    return None
