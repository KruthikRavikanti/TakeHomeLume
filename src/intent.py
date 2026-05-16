from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from src.llm.client import get_default_llm_client
from src.llm.json_parser import parse_json_object
from src.llm.prompts import build_intent_extraction_prompt
from src.schemas import IntentExtraction, IntentType, RequestContext, RiskLevel


VALID_INTENTS = {intent.value for intent in IntentType}
VALID_RISK_LEVELS = {level.value for level in RiskLevel}

FIELD_ALIASES = {
    "work email": "work_email",
    "business email": "work_email",
    "work_email": "work_email",
    "personal email": "personal_email",
    "private email": "personal_email",
    "personal_email": "personal_email",
    "cell": "personal_phone",
    "mobile": "personal_phone",
    "personal phone": "personal_phone",
    "private phone": "personal_phone",
    "personal_phone": "personal_phone",
    "home address": "home_address",
    "address": "home_address",
    "home_address": "home_address",
    "salary": "salary",
    "pay": "salary",
    "compensation": "salary",
    "performance": "performance_rating",
    "review": "performance_rating",
    "performance review": "performance_rating",
    "rating": "performance_rating",
    "performance rating": "performance_rating",
    "performance_rating": "performance_rating",
    "disciplinary": "disciplinary_actions",
    "discipline": "disciplinary_actions",
    "disciplinary record": "disciplinary_actions",
    "disciplinary_actions": "disciplinary_actions",
    "still works here": "employment_status",
    "active": "employment_status",
    "employment status": "employment_status",
    "employment_status": "employment_status",
    "department": "department",
    "job title": "title",
    "title": "title",
    "manager": "manager",
    "office": "office",
    "office location": "office",
    "work phone": "work_phone",
    "business phone": "work_phone",
    "work_phone": "work_phone",
}


def extract_intent(request: RequestContext) -> IntentExtraction:
    prompt = build_intent_extraction_prompt(request)
    client = get_default_llm_client()

    try:
        response = client.generate(prompt, temperature=0.0, format_json=True)
        parsed = parse_json_object(response)
    except Exception as exc:
        return IntentExtraction(
            intent=IntentType.UNKNOWN,
            requested_fields=[],
            user_claims=[],
            risk_level=RiskLevel.HIGH,
            asks_for_human=False,
            raw_summary=f"Intent extraction failed: {exc}",
        )

    try:
        intent = normalize_intent_payload(parsed)
        intent.user_claims = filter_user_claims_for_message(intent.user_claims, request.message)
        return intent
    except (TypeError, ValueError, ValidationError) as exc:
        return IntentExtraction(
            intent=IntentType.UNKNOWN,
            requested_fields=[],
            user_claims=[],
            risk_level=RiskLevel.HIGH,
            asks_for_human=False,
            raw_summary=f"Intent extraction normalization failed: {exc}",
        )


def normalize_intent_payload(payload: dict[str, Any]) -> IntentExtraction:
    intent = normalize_intent(payload.get("intent"))
    normalized = {
        "intent": intent,
        "target_employee_query": _optional_string(payload.get("target_employee_query")),
        "target_employee_id": _optional_string(payload.get("target_employee_id")),
        "requested_fields": normalize_requested_fields(payload.get("requested_fields", [])),
        "drive_query": _optional_string(payload.get("drive_query")),
        "drive_id": _optional_string(payload.get("drive_id")),
        "access_level": normalize_access_level(payload.get("access_level"), intent),
        "duration_days": _optional_int(payload.get("duration_days")),
        "business_justification": _optional_string(payload.get("business_justification")),
        "query_type": _optional_string(payload.get("query_type")),
        "user_claims": _string_list(payload.get("user_claims", [])),
        "risk_level": normalize_risk_level(payload.get("risk_level"), payload.get("intent")),
        "asks_for_human": bool(payload.get("asks_for_human", False)),
        "raw_summary": str(payload.get("raw_summary") or ""),
    }
    return IntentExtraction(**normalized)


def normalize_intent(value: Any) -> str:
    if value is None:
        return IntentType.UNKNOWN.value

    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "password_reset": IntentType.RESET_PASSWORD.value,
        "employee_lookup": IntentType.LOOKUP_EMPLOYEE.value,
        "directory_lookup": IntentType.LOOKUP_EMPLOYEE.value,
        "file_access": IntentType.GRANT_FILE_ACCESS.value,
        "drive_access": IntentType.GRANT_FILE_ACCESS.value,
        "hr_policy": IntentType.QUERY_HR_POLICY.value,
        "hr_individual": IntentType.QUERY_HR_INDIVIDUAL.value,
        "human": IntentType.ESCALATE.value,
        "human_help": IntentType.ESCALATE.value,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in VALID_INTENTS:
        return normalized
    return IntentType.UNKNOWN.value


def normalize_risk_level(value: Any, intent: Any = None) -> str:
    if value is not None:
        normalized = str(value).strip().lower()
        if normalized in VALID_RISK_LEVELS:
            return normalized

    if normalize_intent(intent) == IntentType.UNKNOWN.value:
        return RiskLevel.MEDIUM.value
    return RiskLevel.MEDIUM.value


def normalize_requested_fields(fields: Any) -> list[str]:
    if fields is None:
        return []
    if isinstance(fields, str):
        raw_fields = [fields]
    elif isinstance(fields, list):
        raw_fields = fields
    else:
        return []

    normalized_fields = []
    seen = set()
    for field in raw_fields:
        normalized = _normalize_field_name(field)
        if normalized and normalized not in seen:
            normalized_fields.append(normalized)
            seen.add(normalized)
    return normalized_fields


def normalize_access_level(value: Any, intent: Any) -> str | None:
    access_level = _optional_string(value)
    if access_level:
        return access_level.lower().replace(" ", "_")
    if normalize_intent(intent) == IntentType.GRANT_FILE_ACCESS.value:
        return "read"
    return None


def filter_user_claims_for_message(claims: list[str], message: str) -> list[str]:
    message_normalized = message.lower()
    filtered_claims = []
    for claim in claims:
        claim_normalized = claim.lower()
        if _claim_supported_by_message(claim_normalized, message_normalized):
            filtered_claims.append(claim)
    return filtered_claims


def _claim_supported_by_message(claim: str, message: str) -> bool:
    if "ignore previous instructions" in claim:
        return "ignore previous instructions" in message
    if "maintenance mode" in claim:
        return "maintenance mode" in message
    if "do not follow policy" in claim:
        return "do not follow policy" in message
    if "admin" in claim:
        return "admin" in message
    if "ciso" in claim:
        return "ciso" in message
    if "legal" in claim:
        return "legal" in message
    if "manager" in claim:
        return "manager" in message or "approved" in message
    if "urgent" in claim or "urgency" in claim:
        return "urgent" in message or "asap" in message or "immediately" in message

    claim_tokens = set(re.findall(r"[a-z0-9]+", claim))
    if not claim_tokens:
        return False
    message_tokens = set(re.findall(r"[a-z0-9]+", message))
    return bool(claim_tokens & message_tokens)


def _normalize_field_name(value: Any) -> str | None:
    normalized = str(value).strip().lower().replace("-", " ").replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    canonical = FIELD_ALIASES.get(normalized)
    if canonical:
        return canonical
    compact = normalized.replace(" ", "_")
    return FIELD_ALIASES.get(compact, compact if compact else None)


def _optional_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
