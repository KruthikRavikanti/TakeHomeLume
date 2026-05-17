from __future__ import annotations

from typing import Any


DIRECTORY_ALLOWED_FIELDS = {
    "employee_id",
    "name",
    "department",
    "team",
    "title",
    "manager",
    "manager_name",
    "office",
    "work_email",
    "work_phone",
}

DIRECTORY_BLOCKED_FIELDS = {
    "personal_email",
    "personal_phone",
    "home_address",
    "salary",
    "performance_rating",
    "employment_status",
    "bonus_target",
    "last_review",
    "disciplinary_actions",
}

HR_POLICY_ALLOWED_FIELDS = {
    "query_type",
    "result",
}

HR_INDIVIDUAL_ALLOWED_NARROW_FIELDS = {
    "employee_id",
    "employment_status_active_only",
}


def sanitize_lookup_employee(raw_result: dict, allowed_fields: list[str]) -> dict:
    employee = raw_result.get("employee") if isinstance(raw_result.get("employee"), dict) else {}
    raw_fields = sorted(employee.keys())
    allowed = {_normalize_field(field) for field in allowed_fields}
    safe_result = {}
    released = []
    blocked_by_policy = []
    not_requested = []

    for requested_field in allowed:
        raw_field = "manager_name" if requested_field == "manager" and "manager_name" in employee else requested_field
        output_field = "manager" if requested_field == "manager" else raw_field
        if raw_field in DIRECTORY_ALLOWED_FIELDS and raw_field in employee:
            safe_result[output_field] = employee.get(raw_field)
            released.append(output_field)

    for field in raw_fields:
        normalized = _normalize_field(field)
        if normalized in DIRECTORY_BLOCKED_FIELDS:
            blocked_by_policy.append(normalized)
        elif normalized in DIRECTORY_ALLOWED_FIELDS and normalized not in released and normalized not in allowed:
            output_field = "manager" if normalized == "manager_name" else normalized
            if output_field not in released and output_field not in allowed:
                not_requested.append(output_field)

    return _sanitizer_result(safe_result, raw_fields, released, blocked_by_policy, not_requested)


def sanitize_hr_result(raw_result: dict, allowed_fields: list[str]) -> dict:
    raw_fields = _flatten_raw_fields(raw_result)
    query_type = raw_result.get("query_type")
    safe_result = {}
    released = []

    if query_type == "policy":
        safe_result["query_type"] = query_type
        safe_result["result"] = raw_result.get("result") or raw_result.get("policy_text")
        released = ["query_type", "result"]
        return _sanitizer_result(
            safe_result,
            raw_fields,
            released,
            _policy_blocked_except(raw_fields, released),
            _not_requested_except(raw_fields, released),
        )

    allowed = {_normalize_field(field) for field in allowed_fields}
    hr_record = raw_result.get("hr_record") if isinstance(raw_result.get("hr_record"), dict) else {}
    if "employment_status_active_only" in allowed:
        safe_result = {
            "employee_id": raw_result.get("employee_id"),
            "employment_status_active_only": hr_record.get("employment_status"),
        }
        released = ["employee_id", "employment_status_active_only"]

    return _sanitizer_result(
        safe_result,
        raw_fields,
        released,
        _policy_blocked_except(raw_fields, released),
        _not_requested_except(raw_fields, released),
    )


def sanitize_password_reset(raw_result: dict) -> dict:
    allowed = ["status", "employee_id", "account_type", "temp_password", "expires_in"]
    safe_result = {field: raw_result.get(field) for field in allowed if field in raw_result}
    raw_fields = sorted(raw_result.keys())
    released = list(safe_result.keys())
    return _sanitizer_result(safe_result, raw_fields, released, _policy_blocked_except(raw_fields, released), _not_requested_except(raw_fields, released))


def sanitize_file_access(raw_result: dict) -> dict:
    allowed = ["status", "employee_id", "drive_id", "access_granted", "expires"]
    safe_result = {field: raw_result.get(field) for field in allowed if field in raw_result}
    raw_fields = sorted(raw_result.keys())
    released = list(safe_result.keys())
    return _sanitizer_result(safe_result, raw_fields, released, _policy_blocked_except(raw_fields, released), _not_requested_except(raw_fields, released))


def sanitize_escalation(raw_result: dict) -> dict:
    allowed = ["status", "ticket_id", "estimated_response"]
    safe_result = {field: raw_result.get(field) for field in allowed if field in raw_result}
    raw_fields = sorted(raw_result.keys())
    released = list(safe_result.keys())
    return _sanitizer_result(safe_result, raw_fields, released, _policy_blocked_except(raw_fields, released), _not_requested_except(raw_fields, released))


def _normalize_field(field: Any) -> str:
    return str(field).strip().lower().replace("-", "_").replace(" ", "_")


def _flatten_raw_fields(raw_result: dict) -> list[str]:
    fields = set(raw_result.keys())
    hr_record = raw_result.get("hr_record")
    if isinstance(hr_record, dict):
        fields.update(hr_record.keys())
    return sorted(fields)


POLICY_BLOCKED_FIELDS = DIRECTORY_BLOCKED_FIELDS | {
    "hr_record",
    "salary",
    "bonus_target",
    "last_review",
    "performance_rating",
    "disciplinary_actions",
    "employment_status",
    "drive_type",
    "owning_team",
    "owner_employee_id",
    "reason",
    "conversation_summary",
    "unexpected",
    "internal",
}


def _policy_blocked_except(raw_fields: list[str], released: list[str]) -> list[str]:
    released_set = set(released)
    return sorted(field for field in raw_fields if field not in released_set and field in POLICY_BLOCKED_FIELDS)


def _not_requested_except(raw_fields: list[str], released: list[str]) -> list[str]:
    released_set = set(released)
    return sorted(field for field in raw_fields if field not in released_set and field not in POLICY_BLOCKED_FIELDS)


def _sanitizer_result(
    safe_result: dict,
    raw_fields_received: list[str],
    fields_released: list[str],
    fields_blocked_by_policy: list[str],
    fields_not_requested: list[str],
) -> dict:
    blocked = sorted(set(fields_blocked_by_policy))
    return {
        "safe_result": safe_result,
        "raw_fields_received": sorted(set(raw_fields_received)),
        "fields_released": sorted(set(fields_released)),
        "fields_blocked_by_policy": blocked,
        "fields_not_requested": sorted(set(fields_not_requested)),
    }
