from __future__ import annotations

from typing import Any

from src.intent import normalize_requested_fields
from src.schemas import (
    AccountType,
    AgentAction,
    DriveType,
    FinalDecision,
    IntentExtraction,
    IntentType,
    PolicyDecisionProposal,
    ProposedTool,
    RequestContext,
    RiskLevel,
    TrustTier,
)
from src.tools.mock_data import (
    find_employee,
    get_drive_by_id_or_name,
    get_employee_by_id,
)


SAFE_DIRECTORY_FIELDS = ["name", "department", "title", "manager", "office", "work_email", "work_phone"]
ALLOWED_DIRECTORY_FIELDS = set(SAFE_DIRECTORY_FIELDS + ["team", "manager_name"])
PERSONAL_CONTACT_FIELDS = {"personal_email", "personal_phone", "home_address"}
SENSITIVE_HR_FIELDS = {
    "salary",
    "compensation",
    "bonus_target",
    "performance_rating",
    "performance_review",
    "disciplinary_actions",
    "employment_status",
    "employment_status_change",
    "termination_reason",
}
ACTIVE_STATUS_FIELDS = {"employment_status", "active_status", "employment_status_active_only"}
CONTEXT_ONLY_FIELDS = {"manager"}


def enforce_policy(
    request: RequestContext,
    intent: IntentExtraction,
    proposal: PolicyDecisionProposal,
    policy_cards: list[dict] | None = None,
) -> FinalDecision:
    """Apply deterministic policy precedence before any tool execution.

    Precedence:
    1. Trust-tier restrictions.
    2. Explicit prohibitions.
    3. Narrow verified exceptions.
    4. General permissions.
    5. Clarify or escalate when uncertainty remains.
    """

    if request.trust_tier == TrustTier.RED:
        return _handle_red_request(request, intent)

    if request.trust_tier == TrustTier.GREY:
        grey_decision = _handle_grey_request(request, intent)
        if grey_decision is not None:
            return grey_decision

    if intent.user_claims:
        claim_warning = "User claims were treated as unverified and did not authorize the action."
    else:
        claim_warning = None

    if intent.intent == IntentType.RESET_PASSWORD:
        decision = _handle_password_reset(request, intent)
    elif intent.intent == IntentType.LOOKUP_EMPLOYEE:
        decision = _handle_directory_lookup(request, intent)
    elif intent.intent == IntentType.QUERY_HR_POLICY:
        decision = _allow_hr_policy()
    elif intent.intent == IntentType.QUERY_HR_INDIVIDUAL:
        decision = _handle_individual_hr(request, intent)
    elif intent.intent == IntentType.GRANT_FILE_ACCESS:
        decision = _handle_drive_access(request, intent)
    elif intent.intent == IntentType.ESCALATE or intent.asks_for_human:
        decision = _escalate("User requested human assistance.", ["5.2"])
    else:
        decision = _clarify("The request is ambiguous and needs clarification.", ["6.2"])

    if claim_warning:
        decision.warnings.append(claim_warning)
        decision.policy_citations = _dedupe([*decision.policy_citations, "6.3"])
    return decision


def _handle_red_request(request: RequestContext, intent: IntentExtraction) -> FinalDecision:
    if intent.intent == IntentType.ESCALATE or intent.asks_for_human:
        return _escalate("Team Red user may be escalated to a human operator.", ["7.2", "5.2"])
    return _deny("Team Red users cannot receive tool-based actions except escalation.", ["7.2"])


def _handle_grey_request(request: RequestContext, intent: IntentExtraction) -> FinalDecision | None:
    if intent.intent == IntentType.QUERY_HR_POLICY:
        return _allow_hr_policy()
    if intent.intent == IntentType.GRANT_FILE_ACCESS:
        drive = _resolve_drive(intent)
        if drive is None and _drive_query_mentions(intent, ["legal-hold", "legal_hold", "legal hold", "restricted"]):
            return _escalate(
                "Restricted or legal-hold drive access must be handled by a human operator.",
                ["3.3"],
            )
        if drive is None and _drive_query_mentions(intent, ["personal drive"]):
            return _deny("The agent must not grant access to another employee's personal drive.", ["3.4", "7.3"])
        if drive and drive.drive_type in {DriveType.RESTRICTED, DriveType.LEGAL_HOLD}:
            return _escalate_drive(drive, "Restricted or legal-hold drive access must be handled by a human operator.")
        if drive and drive.drive_type == DriveType.PERSONAL:
            return _deny("The agent must not grant access to another employee's personal drive.", ["3.4", "7.3"])
        return _clarify("Team Grey drive access requests require verification before access can be granted.", ["7.3"])
    if intent.intent in {
        IntentType.RESET_PASSWORD,
        IntentType.LOOKUP_EMPLOYEE,
        IntentType.QUERY_HR_INDIVIDUAL,
    }:
        return _escalate("Team Grey requests for sensitive actions require verification or human review.", ["7.3"])
    return None


def _handle_password_reset(request: RequestContext, intent: IntentExtraction) -> FinalDecision:
    if not request.requester.verified:
        return _deny("Password resets require a verified requester.", ["1.1"])

    target = _resolve_target_employee(intent) or get_employee_by_id(request.requester.employee_id)
    requester_employee = get_employee_by_id(request.requester.employee_id)
    if requester_employee is None:
        return _deny("Requester account could not be verified for password reset.", ["1.1"])

    if target is None:
        return _clarify("The target account could not be identified.", ["6.2"])

    if target.account_type in {AccountType.EXECUTIVE, AccountType.ADMIN, AccountType.SERVICE}:
        return _deny(
            "Executive, admin, and service account password resets must be handled by IT Security.",
            ["1.2"],
        )

    if target.employee_id != request.requester.employee_id:
        return _deny("The agent may reset only the requester's own standard employee account.", ["1.1"])

    return FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.RESET_PASSWORD,
        final_tool_args={"employee_id": request.requester.employee_id},
        policy_citations=["1.1", "1.3"],
        reason="Standard account reset is allowed for the verified account holder. The user must be told the temporary password expires in 24 hours and to use the self-service portal.",
        should_call_tool=True,
    )


def _handle_directory_lookup(request: RequestContext, intent: IntentExtraction) -> FinalDecision:
    target_query = intent.target_employee_query or intent.target_employee_id
    if not target_query:
        return _clarify("The employee to look up is unclear.", ["6.2"])

    requested_fields = normalize_requested_fields(intent.requested_fields)
    if not requested_fields:
        requested_fields = SAFE_DIRECTORY_FIELDS.copy()

    allowed = [field for field in requested_fields if field in ALLOWED_DIRECTORY_FIELDS]
    blocked = [field for field in requested_fields if field in PERSONAL_CONTACT_FIELDS or field in SENSITIVE_HR_FIELDS]
    unknown = [field for field in requested_fields if field not in allowed and field not in blocked]
    if blocked and _message_requests_general_employee_info(request.message):
        allowed = SAFE_DIRECTORY_FIELDS.copy()

    if not allowed and not blocked and unknown:
        return _clarify("The requested employee fields are unclear.", ["6.2"])

    if allowed and blocked:
        return FinalDecision(
            final_action=AgentAction.PARTIAL_ALLOW,
            final_tool=ProposedTool.LOOKUP_EMPLOYEE,
            final_tool_args={"query": target_query},
            allowed_fields_to_show=_dedupe([field for field in SAFE_DIRECTORY_FIELDS if field in ALLOWED_DIRECTORY_FIELDS]),
            blocked_fields=_dedupe(blocked),
            policy_citations=_directory_citations(blocked),
            reason="Safe directory and work contact fields may be shared, but restricted personal or HR fields must be blocked.",
            should_call_tool=True,
        )

    if blocked and not allowed:
        citations = ["4.2"] if any(field in SENSITIVE_HR_FIELDS for field in blocked) else ["2.2"]
        return FinalDecision(
            final_action=AgentAction.DENY,
            final_tool=ProposedTool.NONE,
            blocked_fields=_dedupe(blocked),
            policy_citations=citations,
            reason="The requested fields are restricted and cannot be shared through employee lookup.",
            should_call_tool=False,
        )

    return FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        final_tool_args={"query": target_query},
        allowed_fields_to_show=_dedupe(allowed),
        blocked_fields=[],
        policy_citations=_directory_citations([]),
        reason="Requested directory and work contact fields may be shared.",
        should_call_tool=True,
    )


def _message_requests_general_employee_info(message: str) -> bool:
    lowered = message.lower()
    return any(term in lowered for term in ["info", "details", "profile", "look up", "lookup"])


def _allow_hr_policy() -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.QUERY_HR_DATABASE,
        final_tool_args={"query_type": "policy", "employee_id": None},
        policy_citations=["4.1"],
        reason="General HR policy questions may be answered using the HR knowledge base.",
        should_call_tool=True,
    )


def _handle_individual_hr(request: RequestContext, intent: IntentExtraction) -> FinalDecision:
    requested_fields = normalize_requested_fields(intent.requested_fields)
    target = _resolve_target_employee(intent)

    if _active_status_exception_applies(request, target, requested_fields):
        return FinalDecision(
            final_action=AgentAction.ALLOW,
            final_tool=ProposedTool.QUERY_HR_DATABASE,
            final_tool_args={"query_type": "individual", "employee_id": target.employee_id},
            allowed_fields_to_show=["employment_status_active_only"],
            blocked_fields=[],
            policy_citations=["4.2", "4.4"],
            reason="A verified manager in the reporting chain may confirm only current active/inactive status.",
            should_call_tool=True,
        )

    blocked = requested_fields or ["individual_hr_data"]
    if any(field in PERSONAL_CONTACT_FIELDS for field in blocked):
        citations = ["2.2", "4.2"] if any(field in SENSITIVE_HR_FIELDS for field in blocked) else ["2.2"]
        return FinalDecision(
            final_action=AgentAction.DENY,
            final_tool=ProposedTool.NONE,
            blocked_fields=_dedupe(blocked),
            policy_citations=citations,
            reason="Personal contact information such as personal email, personal phone, and home address cannot be shared.",
            should_call_tool=False,
        )

    return FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=_dedupe(blocked),
        policy_citations=["4.2"],
        reason="Individual compensation, performance, disciplinary, and employment-status-change information is restricted.",
        should_call_tool=False,
    )


def _handle_drive_access(request: RequestContext, intent: IntentExtraction) -> FinalDecision:
    drive = _resolve_drive(intent)
    if drive is None:
        if _drive_query_mentions(intent, ["legal-hold", "legal_hold", "legal hold", "restricted"]):
            return _escalate(
                "Restricted or legal-hold drive access must be handled by a human operator.",
                ["3.3"],
            )
        if _drive_query_mentions(intent, ["personal drive"]):
            return _deny("The agent must not grant access to another employee's personal drive.", ["3.4"])
        return _clarify("The requested drive could not be identified.", ["6.2"])

    if drive.drive_type == DriveType.PERSONAL:
        return _deny("The agent must not grant access to another employee's personal drive.", ["3.4"])

    if drive.drive_type in {DriveType.RESTRICTED, DriveType.LEGAL_HOLD}:
        return _escalate_drive(drive, "Restricted or legal-hold drive access must be handled by a human operator.")

    if not request.requester.verified:
        return _clarify("Drive access requires verified requester context.", ["6.2"])

    if drive.drive_type == DriveType.TEAM:
        if request.requester.team != drive.owning_team:
            return _deny("Same-team drive access requires requester membership in the owning team.", ["3.1"])
        return _allow_drive_access(request, intent, drive, ["3.1"])

    if drive.drive_type == DriveType.CROSS_TEAM:
        if not intent.business_justification:
            return _clarify("Cross-team drive access requires a business justification.", ["3.2"])
        if intent.duration_days is None:
            return _clarify("Cross-team drive access requires a temporary duration up to 7 days.", ["3.2"])
        if intent.duration_days > 7:
            return _clarify("Cross-team drive access is limited to temporary access of up to 7 days.", ["3.2"])
        return _allow_drive_access(request, intent, drive, ["3.2"])

    return _clarify("The drive access request could not be evaluated.", ["6.2"])


def _allow_drive_access(request: RequestContext, intent: IntentExtraction, drive, citations: list[str]) -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.ALLOW,
        final_tool=ProposedTool.GRANT_FILE_ACCESS,
        final_tool_args={
            "employee_id": request.requester.employee_id,
            "drive_id": drive.drive_id,
            "access_level": intent.access_level or "read",
            "duration_days": intent.duration_days,
        },
        policy_citations=citations,
        reason="Drive access conditions are satisfied.",
        should_call_tool=True,
    )


def _active_status_exception_applies(request: RequestContext, target, requested_fields: list[str]) -> bool:
    if target is None:
        return False
    if request.trust_tier != TrustTier.BLUE:
        return False
    if not request.requester.verified or not request.requester.is_manager:
        return False
    if set(requested_fields) - ACTIVE_STATUS_FIELDS - CONTEXT_ONLY_FIELDS:
        return False
    if not any(field in ACTIVE_STATUS_FIELDS for field in requested_fields):
        return False
    return target.manager_id == request.requester.employee_id


def _resolve_target_employee(intent: IntentExtraction):
    if intent.target_employee_id:
        return get_employee_by_id(intent.target_employee_id) or find_employee(intent.target_employee_id)
    if intent.target_employee_query:
        return find_employee(intent.target_employee_query)
    return None


def _resolve_drive(intent: IntentExtraction):
    if intent.drive_id:
        return get_drive_by_id_or_name(intent.drive_id)
    if intent.drive_query:
        return get_drive_by_id_or_name(intent.drive_query)
    return None


def _drive_query_mentions(intent: IntentExtraction, terms: list[str]) -> bool:
    text = " ".join(part for part in [intent.drive_id, intent.drive_query] if part).lower()
    return any(term in text for term in terms)


def _directory_citations(blocked: list[str]) -> list[str]:
    citations = ["2.1", "2.3"]
    if any(field in PERSONAL_CONTACT_FIELDS for field in blocked):
        citations.append("2.2")
    if any(field in SENSITIVE_HR_FIELDS for field in blocked):
        citations.append("4.2")
    return _dedupe(citations)


def _deny(reason: str, citations: list[str]) -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        final_tool_args={},
        policy_citations=_dedupe(citations),
        reason=reason,
        should_call_tool=False,
    )


def _clarify(reason: str, citations: list[str]) -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.CLARIFY,
        final_tool=ProposedTool.NONE,
        final_tool_args={},
        policy_citations=_dedupe(citations),
        reason=reason,
        should_call_tool=False,
    )


def _escalate(reason: str, citations: list[str]) -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.ESCALATE,
        final_tool=ProposedTool.ESCALATE_TO_HUMAN,
        final_tool_args={"reason": reason, "conversation_summary": reason},
        policy_citations=_dedupe(citations),
        reason=reason,
        should_call_tool=True,
        escalation_reason=reason,
    )


def _escalate_drive(drive, reason: str) -> FinalDecision:
    return FinalDecision(
        final_action=AgentAction.ESCALATE,
        final_tool=ProposedTool.ESCALATE_TO_HUMAN,
        final_tool_args={
            "reason": reason,
            "conversation_summary": f"Requester asked for access to {drive.name}.",
        },
        policy_citations=["3.3"],
        reason=reason,
        should_call_tool=True,
        escalation_reason=reason,
    )


def _dedupe(values: list[Any]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        text = str(value)
        if text and text not in seen:
            deduped.append(text)
            seen.add(text)
    return deduped
