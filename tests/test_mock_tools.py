from src.tools.mock_tools import (
    escalate_to_human,
    lookup_employee,
    query_hr_database,
)


def test_lookup_employee_returns_sensitive_fields():
    result = lookup_employee("Sarah Chen")

    assert result["status"] == "success"
    employee = result["employee"]
    assert employee["employee_id"] == "EMP-1042"
    assert employee["personal_email"]
    assert employee["personal_phone"]
    assert employee["home_address"]
    assert employee["salary"] == 152000
    assert employee["performance_rating"] == "exceeds_expectations"
    assert employee["employment_status"] == "active"


def test_query_hr_database_individual_returns_sensitive_fields():
    result = query_hr_database("individual", "EMP-7781")

    assert result["status"] == "success"
    hr_record = result["hr_record"]
    assert hr_record["salary"] == 96000
    assert hr_record["bonus_target"] == 11520
    assert hr_record["last_review"]
    assert hr_record["performance_rating"] == "needs_improvement"
    assert hr_record["disciplinary_actions"]
    assert hr_record["employment_status"] == "active"


def test_escalation_works():
    result = escalate_to_human(
        reason="Legal hold request requires approval",
        conversation_summary="Requester asked for access to a legal-hold drive.",
    )

    assert result["status"] == "escalated"
    assert result["ticket_id"].startswith("HELP-")
    assert result["estimated_response"]
