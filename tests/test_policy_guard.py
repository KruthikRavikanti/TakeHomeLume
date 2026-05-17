from __future__ import annotations

from src.policy.policy_guard import enforce_policy
from src.schemas import (
    AgentAction,
    IntentExtraction,
    IntentType,
    PolicyDecisionProposal,
    ProposedTool,
    RequestContext,
    RequesterContext,
    RiskLevel,
    TrustTier,
)
from src.tools.mock_data import get_employee_by_id, is_manager


def _request(employee_id: str = "EMP-2200", trust_tier: TrustTier = TrustTier.BLUE) -> RequestContext:
    employee = get_employee_by_id(employee_id)
    if employee is None:
        requester = RequesterContext(
            employee_id=employee_id,
            name="Unknown Requester",
            department="Unknown",
            team="Unknown",
            role="Unknown",
            is_manager=False,
            verified=False,
            reports=[],
        )
    else:
        requester = RequesterContext(
            employee_id=employee.employee_id,
            name=employee.name,
            department=employee.department,
            team=employee.team,
            role=employee.title,
            is_manager=is_manager(employee.employee_id),
            verified=True,
            reports=[],
        )
    return RequestContext(
        request_id="REQ-test",
        conversation_id="CONV-test",
        trust_tier=trust_tier,
        requester=requester,
        message="test request",
    )


def _intent(intent: IntentType, **overrides) -> IntentExtraction:
    data = {
        "intent": intent,
        "requested_fields": [],
        "user_claims": [],
        "risk_level": RiskLevel.MEDIUM,
        "raw_summary": "test intent",
    }
    data.update(overrides)
    return IntentExtraction(**data)


def _proposal(**overrides) -> PolicyDecisionProposal:
    data = {
        "proposed_action": AgentAction.ALLOW,
        "proposed_tool": ProposedTool.NONE,
        "tool_args": {},
        "allowed_fields_to_show": [],
        "blocked_fields": [],
        "policy_citations": [],
        "reasoning_summary": "test proposal",
        "risk_level": RiskLevel.MEDIUM,
        "requires_escalation": False,
        "user_facing_explanation": "test",
    }
    data.update(overrides)
    return PolicyDecisionProposal(**data)


def test_blue_work_email_allowed():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(IntentType.LOOKUP_EMPLOYEE, target_employee_query="David Kim", requested_fields=["work_email"]),
        _proposal(),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.LOOKUP_EMPLOYEE
    assert decision.should_call_tool is True
    assert "work_email" in decision.allowed_fields_to_show


def test_blue_salary_denied():
    decision = enforce_policy(
        _request("EMP-3300"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Sarah Chen",
            requested_fields=["salary"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.final_tool == ProposedTool.NONE
    assert decision.should_call_tool is False
    assert "salary" in decision.blocked_fields
    assert "4.2" in decision.policy_citations


def test_home_address_denied_with_personal_contact_citation():
    decision = enforce_policy(
        _request(),
        IntentExtraction(
            intent=IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Sarah Chen",
            requested_fields=["home_address"],
        ),
        _proposal(),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.final_tool == ProposedTool.NONE
    assert decision.should_call_tool is False
    assert "home_address" in decision.blocked_fields
    assert "2.2" in decision.policy_citations


def test_blue_mixed_info_and_personal_email_partial_allow():
    request = _request("EMP-2200")
    request.message = "Look up Sarah Chen's info and include her personal email"

    decision = enforce_policy(
        request,
        _intent(IntentType.LOOKUP_EMPLOYEE, target_employee_query="Sarah Chen", requested_fields=["personal_email"]),
        _proposal(proposed_action=AgentAction.DENY, blocked_fields=["personal_email"]),
    )

    assert decision.final_action == AgentAction.PARTIAL_ALLOW
    assert decision.final_tool == ProposedTool.LOOKUP_EMPLOYEE
    assert decision.should_call_tool is True
    assert "work_email" in decision.allowed_fields_to_show
    assert "personal_email" in decision.blocked_fields
    assert "2.2" in decision.policy_citations


def test_red_reset_password_denied():
    decision = enforce_policy(
        _request("EMP-9999", TrustTier.RED),
        _intent(IntentType.RESET_PASSWORD, target_employee_query="all Engineering passwords"),
        _proposal(proposed_tool=ProposedTool.RESET_PASSWORD),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.final_tool == ProposedTool.NONE
    assert decision.should_call_tool is False


def test_red_lookup_employee_denied():
    decision = enforce_policy(
        _request("EMP-9999", TrustTier.RED),
        _intent(IntentType.LOOKUP_EMPLOYEE, target_employee_query="Sarah Chen", requested_fields=["work_email"]),
        _proposal(proposed_tool=ProposedTool.LOOKUP_EMPLOYEE),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.should_call_tool is False


def test_service_account_password_reset_denied():
    decision = enforce_policy(
        _request("EMP-4010"),
        _intent(IntentType.RESET_PASSWORD, target_employee_query="svc-deploy"),
        _proposal(proposed_tool=ProposedTool.RESET_PASSWORD),
    )

    assert decision.final_action == AgentAction.DENY
    assert "1.2" in decision.policy_citations


def test_standard_own_password_reset_allowed():
    decision = enforce_policy(
        _request("EMP-3300"),
        _intent(IntentType.RESET_PASSWORD, target_employee_id="EMP-3300"),
        _proposal(proposed_tool=ProposedTool.RESET_PASSWORD),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.RESET_PASSWORD
    assert decision.final_tool_args == {"employee_id": "EMP-3300"}
    assert decision.should_call_tool is True
    assert {"1.1", "1.3"} <= set(decision.policy_citations)


def test_emp_2011_standard_own_password_reset_allowed():
    decision = enforce_policy(
        _request("EMP-2011"),
        _intent(IntentType.RESET_PASSWORD),
        _proposal(proposed_tool=ProposedTool.RESET_PASSWORD),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.RESET_PASSWORD
    assert decision.final_tool_args == {"employee_id": "EMP-2011"}
    assert decision.should_call_tool is True
    assert {"1.1", "1.3"} <= set(decision.policy_citations)


def test_personal_drive_access_denied():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(IntentType.GRANT_FILE_ACCESS, drive_query="Jessica Park Personal Drive"),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.should_call_tool is False
    assert "3.4" in decision.policy_citations


def test_legal_hold_drive_access_escalated():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(IntentType.GRANT_FILE_ACCESS, drive_query="Legal-hold Investigation Drive"),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.ESCALATE
    assert decision.final_tool == ProposedTool.ESCALATE_TO_HUMAN
    assert decision.should_call_tool is True
    assert "3.3" in decision.policy_citations


def test_legal_hold_drive_phrase_escalates_even_when_not_exact_drive_name():
    decision = enforce_policy(
        _request("EMP-0000", TrustTier.GREY),
        _intent(
            IntentType.GRANT_FILE_ACCESS,
            drive_query="legal-hold drive",
            business_justification="investigation",
            user_claims=["from Legal"],
        ),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.ESCALATE
    assert decision.final_tool == ProposedTool.ESCALATE_TO_HUMAN
    assert decision.should_call_tool is True
    assert "3.3" in decision.policy_citations


def test_cross_team_drive_with_justification_and_short_duration_allowed():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(
            IntentType.GRANT_FILE_ACCESS,
            drive_query="Design Shared Drive",
            access_level="read",
            duration_days=5,
            business_justification="launch project",
        ),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.GRANT_FILE_ACCESS
    assert decision.final_tool_args["duration_days"] <= 7
    assert "3.2" in decision.policy_citations


def test_cross_team_drive_missing_justification_clarifies():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(IntentType.GRANT_FILE_ACCESS, drive_query="Design Shared Drive", duration_days=5),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.CLARIFY
    assert decision.should_call_tool is False


def test_cross_team_drive_duration_over_seven_does_not_call_tool():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(
            IntentType.GRANT_FILE_ACCESS,
            drive_query="Design Shared Drive",
            duration_days=14,
            business_justification="launch project",
        ),
        _proposal(proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action in {AgentAction.CLARIFY, AgentAction.DENY}
    assert decision.should_call_tool is False


def test_verified_manager_active_status_exception_allowed():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="David Kim",
            requested_fields=["employment_status"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.QUERY_HR_DATABASE
    assert "employment_status_active_only" in decision.allowed_fields_to_show
    assert decision.should_call_tool is True


def test_david_kim_active_status_exception_for_jordan_allowed():
    decision = enforce_policy(
        _request("EMP-1043"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Jordan Rivera",
            requested_fields=["employment_status"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.QUERY_HR_DATABASE
    assert decision.allowed_fields_to_show == ["employment_status_active_only"]
    assert decision.should_call_tool is True


def test_david_kim_active_status_ignores_manager_role_claim_field():
    decision = enforce_policy(
        _request("EMP-1043"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Jordan Rivera",
            requested_fields=["employment_status", "manager"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.ALLOW
    assert decision.final_tool == ProposedTool.QUERY_HR_DATABASE
    assert decision.allowed_fields_to_show == ["employment_status_active_only"]
    assert "4.4" in decision.policy_citations


def test_emp_2200_active_status_for_jordan_denied():
    decision = enforce_policy(
        _request("EMP-2200"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Jordan Rivera",
            requested_fields=["employment_status"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.should_call_tool is False


def test_non_manager_active_status_request_denied():
    decision = enforce_policy(
        _request("EMP-3300"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Sarah Chen",
            requested_fields=["employment_status"],
        ),
        _proposal(proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.should_call_tool is False


def test_claimed_authority_does_not_authorize_restricted_action():
    decision = enforce_policy(
        _request("EMP-3300"),
        _intent(
            IntentType.GRANT_FILE_ACCESS,
            drive_query="Finance Restricted Drive",
            user_claims=["my manager approved this"],
        ),
        _proposal(proposed_action=AgentAction.ALLOW, proposed_tool=ProposedTool.GRANT_FILE_ACCESS),
    )

    assert decision.final_action == AgentAction.ESCALATE
    assert decision.should_call_tool is True
    assert {"3.3", "6.3"} <= set(decision.policy_citations)


def test_unsafe_proposal_allowing_salary_is_overridden():
    decision = enforce_policy(
        _request("EMP-3300"),
        _intent(
            IntentType.QUERY_HR_INDIVIDUAL,
            target_employee_query="Sarah Chen",
            requested_fields=["salary"],
        ),
        _proposal(proposed_action=AgentAction.ALLOW, proposed_tool=ProposedTool.QUERY_HR_DATABASE),
    )

    assert decision.final_action == AgentAction.DENY
    assert decision.final_tool == ProposedTool.NONE
    assert decision.should_call_tool is False
    assert "salary" in decision.blocked_fields
