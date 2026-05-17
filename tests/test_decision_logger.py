import json

from src.logging.decision_logger import DecisionLogger


def _record(request_id: str = "REQ-1") -> dict:
    return {
        "request_id": request_id,
        "conversation_id": "CONV-1",
        "timestamp": "2026-05-17T12:00:00+00:00",
        "trust_tier": "blue",
        "requester_id": "EMP-2200",
        "requester_name": "Priya Nair",
        "requester_department": "Engineering",
        "requester_team": "Platform",
        "requester_role": "Director",
        "requester_verified": True,
        "user_message": "Can I get David Kim's work email?",
        "extracted_intent": {"intent": "lookup_employee"},
        "retrieved_policy_sections": [{"section_id": "2.3", "title": "Work Contact Information"}],
        "policy_proposal": {"proposed_action": "allow"},
        "final_decision": {"final_action": "allow", "policy_citations": ["2.3"]},
        "tool_call": {
            "tool_name": "lookup_employee",
            "tool_args": {"query": "David Kim"},
            "called": True,
            "raw_fields_received": ["work_email", "personal_email"],
            "fields_released": ["work_email"],
            "fields_blocked_by_policy": ["personal_email"],
            "fields_not_requested": [],
            "error": None,
        },
        "final_response": "Work email: david.kim@gaggia.example.",
        "latency_ms": 12.3,
        "warnings": [],
    }


def test_decision_logger_creates_logs_directory(tmp_path):
    log_path = tmp_path / "nested" / "decisions.jsonl"

    DecisionLogger(str(log_path))

    assert log_path.parent.exists()


def test_log_writes_one_jsonl_line(tmp_path):
    log_path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(str(log_path))

    logger.log(_record())

    lines = log_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert json.loads(lines[0])["request_id"] == "REQ-1"


def test_read_last_returns_latest_record(tmp_path):
    log_path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(str(log_path))
    logger.log(_record("REQ-1"))
    logger.log(_record("REQ-2"))

    assert logger.read_last(1)[0]["request_id"] == "REQ-2"


def test_read_last_returns_subset_in_chronological_order(tmp_path):
    log_path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(str(log_path))
    logger.log(_record("REQ-1"))
    logger.log(_record("REQ-2"))
    logger.log(_record("REQ-3"))

    records = logger.read_last(2)

    assert [record["request_id"] for record in records] == ["REQ-2", "REQ-3"]


def test_read_last_returns_empty_list_when_log_missing(tmp_path):
    logger = DecisionLogger(str(tmp_path / "missing" / "decisions.jsonl"))

    assert logger.read_last(5) == []


def test_logged_record_does_not_include_raw_tool_result(tmp_path):
    log_path = tmp_path / "decisions.jsonl"
    logger = DecisionLogger(str(log_path))
    record = _record()
    record["tool_call"]["raw_tool_result"] = {"employee": {"salary": 152000}}

    logger.log(record)

    logged = logger.read_last(1)[0]
    assert "raw_tool_result" not in logged["tool_call"]
