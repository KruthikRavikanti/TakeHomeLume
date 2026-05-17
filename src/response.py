from __future__ import annotations

from src.schemas import (
    AgentAction,
    FinalDecision,
    IntentExtraction,
    ProposedTool,
    RequestContext,
    ToolCallRecord,
)


def generate_final_response(
    request: RequestContext,
    intent: IntentExtraction,
    final_decision: FinalDecision,
    tool_call_record: ToolCallRecord,
) -> str:
    safe_result = tool_call_record.safe_tool_result or {}

    if final_decision.final_action == AgentAction.ALLOW:
        return _allow_response(final_decision, safe_result)
    if final_decision.final_action == AgentAction.PARTIAL_ALLOW:
        return _partial_allow_response(final_decision, safe_result)
    if final_decision.final_action == AgentAction.DENY:
        return _deny_response(final_decision, intent)
    if final_decision.final_action == AgentAction.ESCALATE:
        return _escalate_response(final_decision, safe_result)
    if final_decision.final_action == AgentAction.CLARIFY:
        return _clarify_response(final_decision)

    return f"I couldn't determine how to handle this request.\n\n{format_policy_citations(final_decision.policy_citations)}"


def format_policy_citations(citations: list[str]) -> str:
    deduped = []
    seen = set()
    for citation in citations:
        if citation and citation not in seen:
            deduped.append(citation)
            seen.add(citation)

    if not deduped:
        return ""
    if len(deduped) == 1:
        return f"Policy basis: Section {deduped[0]}."
    if len(deduped) == 2:
        return f"Policy basis: Sections {deduped[0]} and {deduped[1]}."
    return f"Policy basis: Sections {', '.join(deduped[:-1])}, and {deduped[-1]}."


def format_safe_lookup_result(safe_result: dict) -> str:
    if not safe_result:
        return "No releasable employee fields were returned."

    name = safe_result.get("name")
    title = safe_result.get("title")
    department = safe_result.get("department")
    parts = []

    if name and title and department:
        parts.append(f"{name} is a {title} in {department}.")
    elif name:
        parts.append(str(name))

    field_labels = [
        ("office", "Office"),
        ("manager", "Manager"),
        ("manager_name", "Manager"),
        ("work_email", "Work email"),
        ("work_phone", "Work phone"),
        ("team", "Team"),
        ("employee_id", "Employee ID"),
    ]
    for field, label in field_labels:
        if safe_result.get(field):
            parts.append(f"{label}: {safe_result[field]}.")

    for field in ["department", "title"]:
        if field in safe_result and not (name and title and department):
            label = "Department" if field == "department" else "Title"
            parts.append(f"{label}: {safe_result[field]}.")

    return " ".join(parts)


def _allow_response(final_decision: FinalDecision, safe_result: dict) -> str:
    if final_decision.final_tool == ProposedTool.LOOKUP_EMPLOYEE:
        body = format_safe_lookup_result(safe_result)
        return _with_citations(body, final_decision.policy_citations)

    if final_decision.final_tool == ProposedTool.RESET_PASSWORD:
        temp_password = safe_result.get("temp_password", "[temporary password unavailable]")
        expires_in = safe_result.get("expires_in", "24 hours")
        body = (
            f"Your password has been reset. Temporary password: {temp_password}\n\n"
            f"Your temporary password expires in {expires_in}. Please use the self-service portal to set a permanent password."
        )
        if expires_in != "24 hours":
            body += "\n\nPolicy note: temporary passwords must expire in 24 hours."
        return _with_citations(body, final_decision.policy_citations)

    if final_decision.final_tool == ProposedTool.GRANT_FILE_ACCESS:
        expires = safe_result.get("expires")
        duration = f" Access expires on {expires}." if expires else ""
        body = f"Access has been granted for drive {safe_result.get('drive_id')}.{duration}"
        return _with_citations(body, final_decision.policy_citations)

    if final_decision.final_tool == ProposedTool.QUERY_HR_DATABASE:
        if "employment_status_active_only" in final_decision.allowed_fields_to_show:
            status = safe_result.get("employment_status_active_only", "unknown")
            body = f"The employee is currently {status}."
            return _with_citations(body, final_decision.policy_citations)
        body = str(safe_result.get("result", "No HR policy result was returned."))
        return _with_citations(body, final_decision.policy_citations)

    return _with_citations(final_decision.reason, final_decision.policy_citations)


def _partial_allow_response(final_decision: FinalDecision, safe_result: dict) -> str:
    safe_text = format_safe_lookup_result(safe_result)
    blocked = _format_fields(final_decision.blocked_fields)
    body = f"I can share the safe directory/work information, but I can't share {blocked}.\n\n{safe_text}"
    return _with_citations(body, final_decision.policy_citations)


def _deny_response(final_decision: FinalDecision, intent: IntentExtraction) -> str:
    body = final_decision.reason
    if any(field in final_decision.blocked_fields for field in ["salary", "performance_rating", "disciplinary_actions"]):
        body += " If this is needed for an official HR process, contact HR or submit a human escalation request."
    elif "personal_drive" in " ".join(final_decision.policy_citations):
        body += " I can escalate this to a human operator if files are needed for a business continuity reason."
    elif "7.2" in final_decision.policy_citations:
        body += " Please contact IT directly or request verification."
    elif "1.2" in final_decision.policy_citations:
        body += " This must be handled by IT Security."
    return _with_citations(body, final_decision.policy_citations)


def _escalate_response(final_decision: FinalDecision, safe_result: dict) -> str:
    body = final_decision.reason
    if safe_result.get("ticket_id"):
        body += f"\n\nTicket: {safe_result['ticket_id']}"
    if safe_result.get("estimated_response"):
        body += f"\nEstimated response: {safe_result['estimated_response']}"
    return _with_citations(body, final_decision.policy_citations)


def _clarify_response(final_decision: FinalDecision) -> str:
    return _with_citations(final_decision.reason, final_decision.policy_citations)


def _with_citations(body: str, citations: list[str]) -> str:
    citation_text = format_policy_citations(citations)
    return f"{body}\n\n{citation_text}" if citation_text else body


def _format_fields(fields: list[str]) -> str:
    if not fields:
        return "the restricted fields"
    labels = [field.replace("_", " ") for field in fields]
    if len(labels) == 1:
        return labels[0]
    if len(labels) == 2:
        return f"{labels[0]} or {labels[1]}"
    return f"{', '.join(labels[:-1])}, or {labels[-1]}"
