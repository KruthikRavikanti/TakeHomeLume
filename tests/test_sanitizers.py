from src.tools.sanitizers import (
    sanitize_escalation,
    sanitize_file_access,
    sanitize_hr_result,
    sanitize_lookup_employee,
    sanitize_password_reset,
)


def test_lookup_employee_sanitizer_blocks_sensitive_fields():
    raw = {
        "status": "success",
        "employee": {
            "name": "David Kim",
            "work_email": "david.kim@gaggia.example",
            "personal_email": "david.personal@example.com",
            "personal_phone": "555",
            "home_address": "home",
            "salary": 188000,
            "performance_rating": "meets_expectations",
            "employment_status": "active",
        },
    }

    sanitized = sanitize_lookup_employee(raw, ["name", "work_email", "personal_email", "salary"])

    assert sanitized["safe_result"] == {
        "name": "David Kim",
        "work_email": "david.kim@gaggia.example",
    }
    assert "personal_email" in sanitized["fields_blocked_by_policy"]
    assert "salary" in sanitized["fields_blocked_by_policy"]


def test_lookup_employee_sanitizer_releases_safe_directory_fields():
    raw = {
        "status": "success",
        "employee": {
            "name": "Sarah Chen",
            "department": "Product",
            "title": "Senior Product Designer",
            "manager_name": "Jordan Rivera",
            "office": "San Francisco",
            "work_phone": "+1-415-555-0142",
            "personal_email": "blocked@example.com",
        },
    }

    sanitized = sanitize_lookup_employee(raw, ["name", "department", "title", "manager", "office", "work_phone"])

    assert sanitized["safe_result"] == {
        "name": "Sarah Chen",
        "department": "Product",
        "title": "Senior Product Designer",
        "manager": "Jordan Rivera",
        "office": "San Francisco",
        "work_phone": "+1-415-555-0142",
    }
    assert "personal_email" in sanitized["fields_blocked_by_policy"]
    assert "department" not in sanitized["fields_blocked_by_policy"]


def test_hr_policy_sanitizer_releases_policy_result():
    raw = {"status": "success", "query_type": "policy", "policy_text": "PTO policy text", "internal": "blocked"}

    sanitized = sanitize_hr_result(raw, [])

    assert sanitized["safe_result"] == {"query_type": "policy", "result": "PTO policy text"}
    assert "internal" in sanitized["fields_blocked_by_policy"]


def test_hr_individual_active_status_narrow_sanitizer():
    raw = {
        "status": "success",
        "query_type": "individual",
        "employee_id": "EMP-1060",
        "hr_record": {
            "salary": 221000,
            "performance_rating": "exceeds_expectations",
            "disciplinary_actions": [],
            "employment_status": "active",
        },
    }

    sanitized = sanitize_hr_result(raw, ["employment_status_active_only"])

    assert sanitized["safe_result"] == {
        "employee_id": "EMP-1060",
        "employment_status_active_only": "active",
    }
    assert "salary" in sanitized["fields_blocked_by_policy"]
    assert "performance_rating" in sanitized["fields_blocked_by_policy"]
    assert "disciplinary_actions" in sanitized["fields_blocked_by_policy"]


def test_hr_individual_without_narrow_field_releases_nothing_sensitive():
    raw = {
        "status": "success",
        "query_type": "individual",
        "employee_id": "EMP-1060",
        "hr_record": {"salary": 221000, "employment_status": "active"},
    }

    sanitized = sanitize_hr_result(raw, [])

    assert sanitized["safe_result"] == {}
    assert "salary" in sanitized["fields_blocked_by_policy"]
    assert "employment_status" in sanitized["fields_blocked_by_policy"]


def test_password_reset_sanitizer_releases_reset_fields():
    raw = {
        "status": "success",
        "employee_id": "EMP-2011",
        "account_type": "standard",
        "temp_password": "Temp",
        "expires_in": "24 hours",
        "unexpected": "blocked",
    }

    sanitized = sanitize_password_reset(raw)

    assert sanitized["safe_result"]["temp_password"] == "Temp"
    assert sanitized["safe_result"]["expires_in"] == "24 hours"
    assert "unexpected" in sanitized["fields_blocked_by_policy"]


def test_file_access_sanitizer_blocks_drive_metadata():
    raw = {
        "status": "success",
        "employee_id": "EMP-2200",
        "drive_id": "DRV-DESIGN",
        "drive_type": "cross_team",
        "owning_team": "Design",
        "access_granted": True,
        "expires": "2026-05-24",
    }

    sanitized = sanitize_file_access(raw)

    assert sanitized["safe_result"]["access_granted"] is True
    assert "drive_type" in sanitized["fields_blocked_by_policy"]
    assert "owning_team" in sanitized["fields_blocked_by_policy"]


def test_escalation_sanitizer_releases_ticket_fields():
    raw = {
        "status": "escalated",
        "ticket_id": "HELP-123",
        "estimated_response": "1 business day",
        "reason": "blocked",
    }

    sanitized = sanitize_escalation(raw)

    assert sanitized["safe_result"] == {
        "status": "escalated",
        "ticket_id": "HELP-123",
        "estimated_response": "1 business day",
    }
    assert "reason" in sanitized["fields_blocked_by_policy"]


def test_lookup_employee_separates_policy_blocked_from_not_requested():
    raw = {
        "status": "success",
        "employee": {
            "name": "David Kim",
            "department": "Engineering",
            "title": "Engineering Manager",
            "office": "New York",
            "work_email": "david.kim@gaggia.example",
            "work_phone": "+1-212-555-0143",
            "personal_email": "blocked@example.com",
            "salary": 188000,
        },
    }

    sanitized = sanitize_lookup_employee(raw, ["work_email"])

    assert sanitized["safe_result"] == {"work_email": "david.kim@gaggia.example"}
    assert "personal_email" in sanitized["fields_blocked_by_policy"]
    assert "salary" in sanitized["fields_blocked_by_policy"]
    assert "name" in sanitized["fields_not_requested"]
    assert "department" in sanitized["fields_not_requested"]
    assert "title" in sanitized["fields_not_requested"]
    assert "office" in sanitized["fields_not_requested"]
    assert "work_phone" in sanitized["fields_not_requested"]
    assert "name" not in sanitized["fields_blocked_by_policy"]


def test_lookup_employee_manager_alias_is_not_not_requested_when_released():
    raw = {
        "status": "success",
        "employee": {
            "name": "Sarah Chen",
            "manager_name": "Jordan Rivera",
            "personal_email": "blocked@example.com",
        },
    }

    sanitized = sanitize_lookup_employee(raw, ["name", "manager"])

    assert sanitized["safe_result"]["manager"] == "Jordan Rivera"
    assert "manager" in sanitized["fields_released"]
    assert "manager" not in sanitized["fields_not_requested"]
