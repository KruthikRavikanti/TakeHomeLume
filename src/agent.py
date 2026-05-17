from __future__ import annotations

from datetime import datetime, timezone
from time import perf_counter

from src.intent import extract_intent
from src.logging.decision_logger import DecisionLogger
from src.policy.policy_guard import enforce_policy
from src.policy.retriever import PolicyRetriever, load_policy_cards
from src.policy_reasoner import propose_policy_decision
from src.response import generate_final_response
from src.schemas import DecisionLogRecord, RequestContext, ToolCallRecord
from src.tools.safe_tool_executor import execute_final_decision


class PolicyAgent:
    def __init__(
        self,
        retriever: PolicyRetriever | None = None,
        decision_logger: DecisionLogger | None = None,
        enable_logging: bool = True,
    ):
        self.retriever = retriever or PolicyRetriever()
        self.decision_logger = decision_logger or DecisionLogger()
        self.enable_logging = enable_logging

    def handle_request(self, request: RequestContext) -> dict:
        started = perf_counter()
        warnings = []

        intent = extract_intent(request)
        retrieved_policy_sections = self.retriever.retrieve(request.message)
        policy_proposal = propose_policy_decision(request, intent, retrieved_policy_sections)
        final_decision = enforce_policy(
            request,
            intent,
            policy_proposal,
            policy_cards=load_policy_cards(),
        )
        tool_call_record = execute_final_decision(final_decision)
        response_text = generate_final_response(
            request,
            intent,
            final_decision,
            tool_call_record,
        )
        latency_ms = round((perf_counter() - started) * 1000, 2)
        decision_log_record = build_decision_log_record(
            request=request,
            intent=intent,
            retrieved_policy_sections=retrieved_policy_sections,
            policy_proposal=policy_proposal,
            final_decision=final_decision,
            tool_call_record=tool_call_record,
            response_text=response_text,
            latency_ms=latency_ms,
            warnings=warnings,
        )
        log_written = False
        logging_warning = None
        if self.enable_logging:
            try:
                self.decision_logger.log(decision_log_record)
                log_written = True
            except Exception as exc:  # pragma: no cover - defensive path
                logging_warning = f"Decision logging failed: {exc}"
                warnings.append(logging_warning)
                decision_log_record.warnings = warnings

        return {
            "response_text": response_text,
            "intent": intent,
            "retrieved_policy_sections": retrieved_policy_sections,
            "policy_proposal": policy_proposal,
            "final_decision": final_decision,
            "tool_call_record": tool_call_record,
            "decision_log_record": decision_log_record,
            "decision_log_written": log_written,
            "decision_log_path": str(self.decision_logger.log_path),
            "logging_warning": logging_warning,
        }


def build_decision_log_record(
    request: RequestContext,
    intent,
    retrieved_policy_sections: list[dict],
    policy_proposal,
    final_decision,
    tool_call_record: ToolCallRecord,
    response_text: str,
    latency_ms: float | None,
    warnings: list[str] | None = None,
) -> DecisionLogRecord:
    return DecisionLogRecord(
        request_id=request.request_id,
        conversation_id=request.conversation_id,
        timestamp=datetime.now(timezone.utc).isoformat(),
        trust_tier=request.trust_tier.value,
        requester_id=request.requester.employee_id,
        requester_name=request.requester.name,
        requester_department=request.requester.department,
        requester_team=request.requester.team,
        requester_role=request.requester.role,
        requester_verified=request.requester.verified,
        user_message=request.message,
        extracted_intent=intent.model_dump(mode="json"),
        retrieved_policy_sections=[
            _policy_section_log_item(section) for section in retrieved_policy_sections
        ],
        policy_proposal=policy_proposal.model_dump(mode="json"),
        final_decision=final_decision.model_dump(mode="json"),
        tool_call=_tool_call_log_item(tool_call_record),
        final_response=response_text,
        latency_ms=latency_ms,
        warnings=warnings or [],
    )


def _policy_section_log_item(section: dict) -> dict:
    return {
        "section_id": section.get("section_id"),
        "title": section.get("title"),
        "score": section.get("score"),
        "retrieval_source": section.get("retrieval_source"),
        "relationship": section.get("relationship"),
        "matched_from": section.get("matched_from"),
    }


def _tool_call_log_item(tool_call_record: ToolCallRecord) -> dict:
    return {
        "tool_name": tool_call_record.tool_name,
        "tool_args": tool_call_record.tool_args,
        "called": tool_call_record.called,
        "raw_fields_received": tool_call_record.raw_fields_received,
        "fields_released": tool_call_record.fields_released,
        "fields_blocked_by_policy": tool_call_record.fields_blocked_by_policy,
        "fields_not_requested": tool_call_record.fields_not_requested,
        "error": tool_call_record.error,
    }
