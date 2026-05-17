from src.response import generate_final_response
from src.schemas import (
    AgentAction,
    FinalDecision,
    IntentExtraction,
    IntentType,
    ProposedTool,
    RequestContext,
    RequesterContext,
    RiskLevel,
    ToolCallRecord,
    TrustTier,
)


def _request() -> RequestContext:
    return RequestContext(
        request_id="REQ-test",
        conversation_id="CONV-test",
        trust_tier=TrustTier.BLUE,
        requester=RequesterContext(
            employee_id="EMP-2200",
            name="Priya Nair",
            department="Engineering",
            team="Platform",
            role="Director",
            verified=True,
        ),
        message="test",
    )


def _intent(intent: IntentType = IntentType.LOOKUP_EMPLOYEE) -> IntentExtraction:
    return IntentExtraction(intent=intent, risk_level=RiskLevel.MEDIUM)


def _tool_record(safe_result=None, fields_blocked_by_policy=None) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name="test",
        tool_args={},
        called=bool(safe_result),
        raw_tool_result={"salary": 123456, "personal_email": "raw@example.com"},
        safe_tool_result=safe_result,
        raw_fields_received=[],
        fields_released=list((safe_result or {}).keys()),
        fields_blocked_by_policy=fields_blocked_by_policy or [],
        error=None,
    )


def test_denied_salary_response_cites_policy_without_salary_value():
    decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=["salary"],
        policy_citations=["4.2"],
        reason="Individual compensation data is restricted.",
        should_call_tool=False,
    )

    response = generate_final_response(_request(), _intent(IntentType.QUERY_HR_INDIVIDUAL), decision, _tool_record())

    assert "salary" in response.lower() or "compensation" in response.lower()
    assert "4.2" in response
    assert "123456" not in response


def test_partial_allow_personal_email_uses_safe_result_only():
    decision = FinalDecision(
        final_action=AgentAction.PARTIAL_ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        allowed_fields_to_show=["name", "work_email"],
        blocked_fields=["personal_email"],
        policy_citations=["2.1", "2.2", "2.3"],
        reason="partial",
        should_call_tool=True,
    )
    safe = {"name": "Sarah Chen", "work_email": "sarah.chen@gaggia.example"}

    response = generate_final_response(_request(), _intent(), decision, _tool_record(safe, ["personal_email"]))

    assert "sarah.chen@gaggia.example" in response
    assert "personal email" in response.lower()
    assert "raw@example.com" not in response
    assert "2.2" in response


def test_password_reset_response_mentions_24_hour_expiration_and_portal():
    decision = FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.RESET_PASSWORD,
        policy_citations=["1.1", "1.3"],
        reason="reset allowed",
        should_call_tool=True,
    )
    safe = {"temp_password": "Temp-123", "expires_in": "24 hours"}

    response = generate_final_response(_request(), _intent(IntentType.RESET_PASSWORD), decision, _tool_record(safe))

    assert "Temp-123" in response
    assert "24 hours" in response
    assert "self-service portal" in response
    assert "1.1" in response and "1.3" in response


def test_legal_hold_escalation_response_includes_ticket():
    decision = FinalDecision(
        final_action=AgentAction.ESCALATE,
        final_tool=ProposedTool.ESCALATE_TO_HUMAN,
        policy_citations=["3.3"],
        reason="I can't grant access to legal-hold drives directly.",
        should_call_tool=True,
        escalation_reason="legal-hold",
    )
    safe = {"ticket_id": "HELP-12345", "estimated_response": "1 business day"}

    response = generate_final_response(_request(), _intent(IntentType.GRANT_FILE_ACCESS), decision, _tool_record(safe))

    assert "HELP-12345" in response
    assert "3.3" in response


def test_active_status_exception_response_only_includes_status():
    decision = FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.QUERY_HR_DATABASE,
        allowed_fields_to_show=["employment_status_active_only"],
        policy_citations=["4.4"],
        reason="active status allowed",
        should_call_tool=True,
    )
    safe = {"employee_id": "EMP-1060", "employment_status_active_only": "active"}

    response = generate_final_response(_request(), _intent(IntentType.QUERY_HR_INDIVIDUAL), decision, _tool_record(safe))

    assert "currently active" in response
    assert "salary" not in response.lower()
    assert "performance" not in response.lower()
    assert "disciplinary" not in response.lower()
    assert "4.4" in response
