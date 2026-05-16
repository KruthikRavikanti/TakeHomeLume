from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError

from src.intent import normalize_requested_fields
from src.llm.client import get_default_llm_client
from src.llm.json_parser import parse_json_object
from src.llm.prompts import build_policy_reasoning_prompt
from src.schemas import (
    AgentAction,
    IntentExtraction,
    PolicyDecisionProposal,
    ProposedTool,
    RequestContext,
    RiskLevel,
)


VALID_ACTIONS = {action.value for action in AgentAction}
VALID_TOOLS = {tool.value for tool in ProposedTool}
VALID_RISK_LEVELS = {level.value for level in RiskLevel}
SAFE_DIRECTORY_FIELDS = ["name", "department", "title", "manager", "office", "work_email", "work_phone"]
BLOCKED_LOOKUP_FIELDS = {
    "personal_email",
    "personal_phone",
    "home_address",
    "salary",
    "performance_rating",
    "disciplinary_actions",
    "employment_status",
}


def propose_policy_decision(
    request: RequestContext,
    intent: IntentExtraction,
    retrieved_sections: list[dict],
) -> PolicyDecisionProposal:
    prompt = build_policy_reasoning_prompt(request, intent, retrieved_sections)
    client = get_default_llm_client()

    try:
        response = client.generate(prompt, temperature=0.0, format_json=True)
        parsed = parse_json_object(response)
    except Exception as exc:
        return _fallback_proposal(retrieved_sections, f"Policy reasoning parse failure: {exc}")

    try:
        proposal = normalize_policy_proposal(parsed, retrieved_sections)
        return apply_reasoning_cleanup(proposal, request, intent, retrieved_sections)
    except (TypeError, ValueError, ValidationError) as exc:
        return _fallback_proposal(retrieved_sections, f"Policy reasoning normalization failure: {exc}")


def normalize_policy_proposal(
    payload: dict[str, Any],
    retrieved_sections: list[dict],
) -> PolicyDecisionProposal:
    proposed_action = normalize_action(payload.get("proposed_action"))
    citations = normalize_citations(
        payload.get("policy_citations", []),
        retrieved_sections,
        proposed_action,
    )
    normalized = {
        "proposed_action": proposed_action,
        "proposed_tool": normalize_tool(payload.get("proposed_tool")),
        "tool_args": payload.get("tool_args") if isinstance(payload.get("tool_args"), dict) else {},
        "allowed_fields_to_show": normalize_requested_fields(payload.get("allowed_fields_to_show", [])),
        "blocked_fields": normalize_requested_fields(payload.get("blocked_fields", [])),
        "policy_citations": citations,
        "reasoning_summary": str(payload.get("reasoning_summary") or ""),
        "risk_level": normalize_risk_level(payload.get("risk_level")),
        "requires_escalation": bool(payload.get("requires_escalation", False)),
        "user_facing_explanation": str(payload.get("user_facing_explanation") or ""),
    }
    return PolicyDecisionProposal(**normalized)


def apply_reasoning_cleanup(
    proposal: PolicyDecisionProposal,
    request: RequestContext,
    intent: IntentExtraction,
    retrieved_sections: list[dict],
) -> PolicyDecisionProposal:
    if _is_mixed_employee_lookup(request, intent, proposal):
        blocked_fields = _dedupe([*proposal.blocked_fields, *_blocked_requested_fields(intent.requested_fields)])
        proposal.proposed_action = AgentAction.PARTIAL_ALLOW
        proposal.proposed_tool = ProposedTool.LOOKUP_EMPLOYEE
        proposal.tool_args = {"query": intent.target_employee_query or intent.target_employee_id or ""}
        proposal.allowed_fields_to_show = SAFE_DIRECTORY_FIELDS.copy()
        proposal.blocked_fields = blocked_fields
        proposal.policy_citations = _preferred_valid_citations(retrieved_sections, ["2.1", "2.2", "2.3"])
        proposal.reasoning_summary = (
            "Safe directory and work contact fields may be shared, but restricted personal or HR fields must be blocked."
        )
        proposal.risk_level = RiskLevel.MEDIUM
        proposal.requires_escalation = False
        proposal.user_facing_explanation = (
            "I can share safe directory and work contact information, but I can't share personal email or other restricted fields."
        )
    return proposal


def normalize_action(value: Any) -> str:
    normalized = _normalize_token(value)
    aliases = {
        "partially_allow": AgentAction.PARTIAL_ALLOW.value,
        "partial": AgentAction.PARTIAL_ALLOW.value,
        "human": AgentAction.ESCALATE.value,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in VALID_ACTIONS:
        return normalized
    return AgentAction.CLARIFY.value


def normalize_tool(value: Any) -> str:
    normalized = _normalize_token(value)
    aliases = {
        "no_tool": ProposedTool.NONE.value,
        "none_tool": ProposedTool.NONE.value,
        "hr_database": ProposedTool.QUERY_HR_DATABASE.value,
        "query_hr_policy": ProposedTool.QUERY_HR_DATABASE.value,
        "query_hr_individual": ProposedTool.QUERY_HR_DATABASE.value,
        "human": ProposedTool.ESCALATE_TO_HUMAN.value,
        "escalate": ProposedTool.ESCALATE_TO_HUMAN.value,
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in VALID_TOOLS:
        return normalized
    return ProposedTool.NONE.value


def normalize_risk_level(value: Any) -> str:
    normalized = _normalize_token(value)
    if normalized in VALID_RISK_LEVELS:
        return normalized
    return RiskLevel.MEDIUM.value


def normalize_citations(
    citations: Any,
    retrieved_sections: list[dict],
    proposed_action: str,
) -> list[str]:
    valid_section_ids = [str(section.get("section_id")) for section in retrieved_sections if section.get("section_id")]
    valid_section_id_set = set(valid_section_ids)

    if isinstance(citations, str):
        raw_citations = [citations]
    elif isinstance(citations, list):
        raw_citations = citations
    else:
        raw_citations = []

    normalized_citations = []
    seen = set()
    for citation in raw_citations:
        normalized = normalize_citation(citation)
        if normalized in valid_section_id_set and normalized not in seen:
            normalized_citations.append(normalized)
            seen.add(normalized)

    if proposed_action in {AgentAction.DENY.value, AgentAction.ESCALATE.value} and not normalized_citations:
        if valid_section_ids:
            normalized_citations.append(valid_section_ids[0])

    return normalized_citations


def normalize_citation(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"(?i)^sections?\s+", "", text)
    text = text.strip()
    match = re.search(r"\d+(?:\.\d+)*", text)
    return match.group(0) if match else text


def _is_mixed_employee_lookup(
    request: RequestContext,
    intent: IntentExtraction,
    proposal: PolicyDecisionProposal,
) -> bool:
    if intent.intent.value != "lookup_employee":
        return False

    requested_blocked_fields = _blocked_requested_fields(intent.requested_fields)
    blocked_fields = _blocked_requested_fields(proposal.blocked_fields)
    if not requested_blocked_fields and not blocked_fields:
        return False

    message = request.message.lower()
    asks_for_general_info = any(term in message for term in ["info", "details", "profile", "look up", "lookup"])
    has_allowed_fields = bool(set(intent.requested_fields) & set(SAFE_DIRECTORY_FIELDS))
    return asks_for_general_info or has_allowed_fields


def _blocked_requested_fields(fields: list[str]) -> list[str]:
    return [field for field in normalize_requested_fields(fields) if field in BLOCKED_LOOKUP_FIELDS]


def _preferred_valid_citations(retrieved_sections: list[dict], preferred: list[str]) -> list[str]:
    valid = {str(section.get("section_id")) for section in retrieved_sections if section.get("section_id")}
    citations = [section_id for section_id in preferred if section_id in valid]
    if citations:
        return citations
    return [str(retrieved_sections[0]["section_id"])] if retrieved_sections and retrieved_sections[0].get("section_id") else []


def _dedupe(values: list[str]) -> list[str]:
    deduped = []
    seen = set()
    for value in values:
        if value not in seen:
            deduped.append(value)
            seen.add(value)
    return deduped


def _fallback_proposal(retrieved_sections: list[dict], reason: str) -> PolicyDecisionProposal:
    citation = []
    if retrieved_sections and retrieved_sections[0].get("section_id"):
        citation = [str(retrieved_sections[0]["section_id"])]
    return PolicyDecisionProposal(
        proposed_action=AgentAction.ESCALATE,
        proposed_tool=ProposedTool.ESCALATE_TO_HUMAN,
        tool_args={
            "reason": "Policy reasoning failed and needs human review.",
            "conversation_summary": reason,
        },
        allowed_fields_to_show=[],
        blocked_fields=[],
        policy_citations=citation,
        reasoning_summary=reason,
        risk_level=RiskLevel.HIGH,
        requires_escalation=True,
        user_facing_explanation="I need to escalate this request for human review.",
    )


def _normalize_token(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower().replace("-", "_").replace(" ", "_")
