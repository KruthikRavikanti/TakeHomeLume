from src.schemas import AgentAction, FinalDecision, ProposedTool
from src.tools.safe_tool_executor import execute_final_decision


def _decision(**overrides) -> FinalDecision:
    data = {
        "final_action": AgentAction.DENY,
        "final_tool": ProposedTool.NONE,
        "final_tool_args": {},
        "allowed_fields_to_show": [],
        "blocked_fields": [],
        "policy_citations": [],
        "reason": "test",
        "should_call_tool": False,
        "warnings": [],
    }
    data.update(overrides)
    return FinalDecision(**data)


def test_deny_decision_does_not_call_tool():
    record = execute_final_decision(_decision(final_tool=ProposedTool.LOOKUP_EMPLOYEE, final_tool_args={"query": "David Kim"}))

    assert record.called is False
    assert record.raw_tool_result is None
    assert record.safe_tool_result is None


def test_allow_lookup_employee_calls_tool_and_sanitizes():
    decision = _decision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        final_tool_args={"query": "David Kim"},
        allowed_fields_to_show=["work_email"],
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is True
    assert record.safe_tool_result == {"work_email": "david.kim@gaggia.example"}
    assert "personal_email" in record.fields_blocked_by_policy
    assert "salary" in record.fields_blocked_by_policy
    assert "name" in record.fields_not_requested
    assert "department" in record.fields_not_requested
    assert "title" in record.fields_not_requested
    assert "work_phone" in record.fields_not_requested
    assert "name" not in record.fields_blocked_by_policy


def test_salary_denial_does_not_call_hr_database():
    decision = _decision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=["salary"],
        should_call_tool=False,
    )

    record = execute_final_decision(decision)

    assert record.called is False
    assert record.safe_tool_result is None


def test_partial_allow_lookup_blocks_personal_email():
    decision = _decision(
        final_action=AgentAction.PARTIAL_ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        final_tool_args={"query": "Sarah Chen"},
        allowed_fields_to_show=["name", "work_email"],
        blocked_fields=["personal_email"],
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is True
    assert "personal_email" not in record.safe_tool_result
    assert "personal_email" in record.fields_blocked_by_policy


def test_password_reset_allowed_returns_temp_password_and_expiration():
    decision = _decision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.RESET_PASSWORD,
        final_tool_args={"employee_id": "EMP-2011"},
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is True
    assert record.safe_tool_result["temp_password"]
    assert record.safe_tool_result["expires_in"]


def test_legal_hold_escalation_calls_escalate_to_human():
    decision = _decision(
        final_action=AgentAction.ESCALATE,
        final_tool=ProposedTool.ESCALATE_TO_HUMAN,
        final_tool_args={"reason": "legal-hold", "conversation_summary": "legal-hold request"},
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is True
    assert record.safe_tool_result["ticket_id"].startswith("HELP-")


def test_active_status_exception_releases_only_narrow_field():
    decision = _decision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.QUERY_HR_DATABASE,
        final_tool_args={"query_type": "individual", "employee_id": "EMP-1060"},
        allowed_fields_to_show=["employment_status_active_only"],
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is True
    assert record.safe_tool_result == {
        "employee_id": "EMP-1060",
        "employment_status_active_only": "active",
    }
    assert "salary" in record.fields_blocked_by_policy
    assert "performance_rating" in record.fields_blocked_by_policy


def test_unknown_tool_returns_error_without_crashing():
    decision = FinalDecision.model_construct(
        final_action=AgentAction.ALLOW,
        final_tool="unknown_tool",
        final_tool_args={},
        allowed_fields_to_show=[],
        blocked_fields=[],
        policy_citations=[],
        reason="test",
        should_call_tool=True,
        escalation_reason=None,
        warnings=[],
    )

    record = execute_final_decision(decision)

    assert record.called is False
    assert "Unknown tool" in record.error


def test_missing_args_returns_error_without_crashing():
    decision = _decision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        final_tool_args={},
        should_call_tool=True,
    )

    record = execute_final_decision(decision)

    assert record.called is False
    assert "Missing required tool args" in record.error
