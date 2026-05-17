from src.agent import PolicyAgent
from src.logging.decision_logger import DecisionLogger
from src.schemas import (
    AgentAction,
    FinalDecision,
    IntentExtraction,
    IntentType,
    PolicyDecisionProposal,
    ProposedTool,
    RequestContext,
    RequesterContext,
    RiskLevel,
    ToolCallRecord,
    TrustTier,
)


class FakeRetriever:
    def retrieve(self, query: str):
        return [{"section_id": "2.2", "title": "Personal Contact", "text": "No personal email."}]


def _request(message: str = "Can I get Sarah Chen's personal email?") -> RequestContext:
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
        message=message,
    )


def _patch_pipeline(monkeypatch, final_decision: FinalDecision, tool_record: ToolCallRecord):
    monkeypatch.setattr(
        "src.agent.extract_intent",
        lambda request: IntentExtraction(
            intent=IntentType.LOOKUP_EMPLOYEE,
            target_employee_query="Sarah Chen",
            requested_fields=["personal_email"],
            risk_level=RiskLevel.MEDIUM,
        ),
    )
    monkeypatch.setattr(
        "src.agent.propose_policy_decision",
        lambda request, intent, sections: PolicyDecisionProposal(
            proposed_action=AgentAction.DENY,
            proposed_tool=ProposedTool.NONE,
            blocked_fields=["personal_email"],
            policy_citations=["2.2"],
        ),
    )
    monkeypatch.setattr("src.agent.load_policy_cards", lambda: [])
    monkeypatch.setattr("src.agent.enforce_policy", lambda request, intent, proposal, policy_cards: final_decision)
    monkeypatch.setattr("src.agent.execute_final_decision", lambda decision: tool_record)


def test_handle_request_returns_response_text_and_artifacts(monkeypatch):
    final_decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=["personal_email"],
        policy_citations=["2.2"],
        reason="Personal email cannot be shared.",
        should_call_tool=False,
    )
    tool_record = ToolCallRecord(tool_name="none", called=False)
    _patch_pipeline(monkeypatch, final_decision, tool_record)

    result = PolicyAgent(retriever=FakeRetriever(), enable_logging=False).handle_request(_request())

    assert result["response_text"]
    assert result["intent"]
    assert result["retrieved_policy_sections"]
    assert result["policy_proposal"]
    assert result["final_decision"]
    assert result["tool_call_record"]
    assert result["decision_log_record"]


def test_denied_request_does_not_call_tool(monkeypatch):
    final_decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        policy_citations=["4.2"],
        reason="Salary is restricted.",
        should_call_tool=False,
    )
    tool_record = ToolCallRecord(tool_name="none", called=False)
    _patch_pipeline(monkeypatch, final_decision, tool_record)

    result = PolicyAgent(retriever=FakeRetriever(), enable_logging=False).handle_request(_request("What's Sarah Chen's salary?"))

    assert result["tool_call_record"].called is False


def test_partial_allow_uses_safe_tool_result_only(monkeypatch):
    final_decision = FinalDecision(
        final_action=AgentAction.PARTIAL_ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        allowed_fields_to_show=["work_email"],
        blocked_fields=["personal_email"],
        policy_citations=["2.2", "2.3"],
        reason="partial",
        should_call_tool=True,
    )
    tool_record = ToolCallRecord(
        tool_name="lookup_employee",
        called=True,
        raw_tool_result={"employee": {"personal_email": "sarah.personal@example.com", "salary": 152000}},
        safe_tool_result={"work_email": "sarah.chen@gaggia.example"},
        fields_released=["work_email"],
        fields_blocked_by_policy=["personal_email", "salary"],
    )
    _patch_pipeline(monkeypatch, final_decision, tool_record)

    result = PolicyAgent(retriever=FakeRetriever(), enable_logging=False).handle_request(_request())

    assert "sarah.chen@gaggia.example" in result["response_text"]
    assert "sarah.personal@example.com" not in result["response_text"]
    assert "152000" not in result["response_text"]


def test_handle_request_writes_log_when_enabled(monkeypatch, tmp_path):
    final_decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=["salary"],
        policy_citations=["4.2"],
        reason="Salary is restricted.",
        should_call_tool=False,
    )
    tool_record = ToolCallRecord(tool_name="none", called=False)
    _patch_pipeline(monkeypatch, final_decision, tool_record)
    logger = DecisionLogger(str(tmp_path / "decisions.jsonl"))

    result = PolicyAgent(
        retriever=FakeRetriever(),
        decision_logger=logger,
        enable_logging=True,
    ).handle_request(_request("What's Sarah Chen's salary?"))

    records = logger.read_last(1)
    assert result["decision_log_record"]
    assert result["decision_log_written"] is True
    assert len(records) == 1
    assert records[0]["request_id"] == "REQ-test"


def test_handle_request_does_not_write_log_when_disabled(monkeypatch, tmp_path):
    final_decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        policy_citations=["4.2"],
        reason="Salary is restricted.",
        should_call_tool=False,
    )
    tool_record = ToolCallRecord(tool_name="none", called=False)
    _patch_pipeline(monkeypatch, final_decision, tool_record)
    logger = DecisionLogger(str(tmp_path / "decisions.jsonl"))

    result = PolicyAgent(
        retriever=FakeRetriever(),
        decision_logger=logger,
        enable_logging=False,
    ).handle_request(_request("What's Sarah Chen's salary?"))

    assert result["decision_log_written"] is False
    assert logger.read_last(1) == []


def test_denied_request_log_has_called_false(monkeypatch, tmp_path):
    final_decision = FinalDecision(
        final_action=AgentAction.DENY,
        final_tool=ProposedTool.NONE,
        blocked_fields=["salary"],
        policy_citations=["4.2"],
        reason="Salary is restricted.",
        should_call_tool=False,
    )
    tool_record = ToolCallRecord(tool_name="none", called=False)
    _patch_pipeline(monkeypatch, final_decision, tool_record)
    logger = DecisionLogger(str(tmp_path / "decisions.jsonl"))

    PolicyAgent(retriever=FakeRetriever(), decision_logger=logger).handle_request(
        _request("What's Sarah Chen's salary?")
    )

    assert logger.read_last(1)[0]["tool_call"]["called"] is False


def test_partial_allow_log_includes_released_and_policy_blocked_fields(monkeypatch, tmp_path):
    final_decision = FinalDecision(
        final_action=AgentAction.PARTIAL_ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        allowed_fields_to_show=["work_email"],
        blocked_fields=["personal_email"],
        policy_citations=["2.2", "2.3"],
        reason="partial",
        should_call_tool=True,
    )
    tool_record = ToolCallRecord(
        tool_name="lookup_employee",
        called=True,
        raw_tool_result={
            "employee": {
                "work_email": "sarah.chen@gaggia.example",
                "personal_email": "sarah.personal@example.com",
                "salary": 152000,
                "home_address": "123 Private Lane",
                "performance_rating": "Exceeds",
            }
        },
        safe_tool_result={"work_email": "sarah.chen@gaggia.example"},
        raw_fields_received=["work_email", "personal_email", "salary", "home_address", "performance_rating"],
        fields_released=["work_email"],
        fields_blocked_by_policy=["personal_email", "salary", "home_address", "performance_rating"],
    )
    _patch_pipeline(monkeypatch, final_decision, tool_record)
    logger = DecisionLogger(str(tmp_path / "decisions.jsonl"))

    PolicyAgent(retriever=FakeRetriever(), decision_logger=logger).handle_request(_request())

    tool_call = logger.read_last(1)[0]["tool_call"]
    assert tool_call["fields_released"] == ["work_email"]
    assert "personal_email" in tool_call["fields_blocked_by_policy"]


def test_persistent_log_excludes_raw_sensitive_values(monkeypatch, tmp_path):
    final_decision = FinalDecision(
        final_action=AgentAction.PARTIAL_ALLOW,
        final_tool=ProposedTool.LOOKUP_EMPLOYEE,
        allowed_fields_to_show=["work_email"],
        blocked_fields=["personal_email", "salary"],
        policy_citations=["2.2", "2.3"],
        reason="partial",
        should_call_tool=True,
    )
    tool_record = ToolCallRecord(
        tool_name="lookup_employee",
        called=True,
        raw_tool_result={
            "employee": {
                "work_email": "sarah.chen@gaggia.example",
                "personal_email": "sarah.personal@example.com",
                "salary": 152000,
                "home_address": "123 Private Lane",
                "performance_rating": "Exceeds",
            }
        },
        safe_tool_result={"work_email": "sarah.chen@gaggia.example"},
        raw_fields_received=["work_email", "personal_email", "salary", "home_address", "performance_rating"],
        fields_released=["work_email"],
        fields_blocked_by_policy=["personal_email", "salary", "home_address", "performance_rating"],
    )
    _patch_pipeline(monkeypatch, final_decision, tool_record)
    log_path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(str(log_path))

    PolicyAgent(retriever=FakeRetriever(), decision_logger=logger).handle_request(_request())

    persisted = log_path.read_text(encoding="utf-8")
    assert "sarah.personal@example.com" not in persisted
    assert "152000" not in persisted
    assert "123 Private Lane" not in persisted
    assert "Exceeds" not in persisted
    assert "raw_tool_result" not in persisted
