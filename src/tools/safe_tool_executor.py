from __future__ import annotations

from typing import Any

from src.schemas import FinalDecision, ProposedTool, ToolCallRecord
from src.tools import mock_tools
from src.tools.sanitizers import (
    sanitize_escalation,
    sanitize_file_access,
    sanitize_hr_result,
    sanitize_lookup_employee,
    sanitize_password_reset,
)


def execute_final_decision(final_decision: FinalDecision) -> ToolCallRecord:
    tool_name = _tool_value(final_decision.final_tool)
    tool_args = final_decision.final_tool_args

    if not final_decision.should_call_tool:
        return ToolCallRecord(
            tool_name=tool_name,
            tool_args=tool_args,
            called=False,
            raw_tool_result=None,
            safe_tool_result=None,
            raw_fields_received=[],
            fields_released=[],
            fields_blocked_by_policy=[],
            fields_not_requested=[],
            error=None,
        )

    if tool_name == ProposedTool.NONE.value:
        return _not_called(tool_name, tool_args, "Final decision requested tool execution but final_tool is none.")

    tool_spec = TOOL_SPECS.get(tool_name)
    if tool_spec is None:
        return _not_called(tool_name, tool_args, f"Unknown tool: {tool_name}")

    missing_args = [arg for arg in tool_spec["required_args"] if arg not in tool_args]
    if missing_args:
        return _not_called(tool_name, tool_args, f"Missing required tool args: {', '.join(missing_args)}")

    try:
        raw_result = tool_spec["callable"](**{arg: tool_args.get(arg) for arg in tool_spec["call_args"]})
    except Exception as exc:
        return ToolCallRecord(
            tool_name=tool_name,
            tool_args=tool_args,
            called=True,
            raw_tool_result=None,
            safe_tool_result=None,
            raw_fields_received=[],
            fields_released=[],
            fields_blocked_by_policy=[],
            fields_not_requested=[],
            error=f"Tool execution failed: {exc}",
        )

    sanitized = tool_spec["sanitizer"](raw_result, final_decision)
    return ToolCallRecord(
        tool_name=tool_name,
        tool_args=tool_args,
        called=True,
        raw_tool_result=raw_result,
        safe_tool_result=sanitized["safe_result"],
        raw_fields_received=sanitized["raw_fields_received"],
        fields_released=sanitized["fields_released"],
        fields_blocked_by_policy=sanitized["fields_blocked_by_policy"],
        fields_not_requested=sanitized["fields_not_requested"],
        error=None,
    )


def _sanitize_lookup(raw_result: dict, final_decision: FinalDecision) -> dict:
    return sanitize_lookup_employee(raw_result, final_decision.allowed_fields_to_show)


def _sanitize_hr(raw_result: dict, final_decision: FinalDecision) -> dict:
    return sanitize_hr_result(raw_result, final_decision.allowed_fields_to_show)


def _sanitize_password(raw_result: dict, final_decision: FinalDecision) -> dict:
    return sanitize_password_reset(raw_result)


def _sanitize_file(raw_result: dict, final_decision: FinalDecision) -> dict:
    return sanitize_file_access(raw_result)


def _sanitize_escalate(raw_result: dict, final_decision: FinalDecision) -> dict:
    return sanitize_escalation(raw_result)


TOOL_SPECS: dict[str, dict[str, Any]] = {
    ProposedTool.RESET_PASSWORD.value: {
        "callable": mock_tools.reset_password,
        "call_args": ["employee_id"],
        "required_args": ["employee_id"],
        "sanitizer": _sanitize_password,
    },
    ProposedTool.LOOKUP_EMPLOYEE.value: {
        "callable": mock_tools.lookup_employee,
        "call_args": ["query"],
        "required_args": ["query"],
        "sanitizer": _sanitize_lookup,
    },
    ProposedTool.GRANT_FILE_ACCESS.value: {
        "callable": mock_tools.grant_file_access,
        "call_args": ["employee_id", "drive_id", "access_level", "duration_days"],
        "required_args": ["employee_id", "drive_id", "access_level"],
        "sanitizer": _sanitize_file,
    },
    ProposedTool.QUERY_HR_DATABASE.value: {
        "callable": mock_tools.query_hr_database,
        "call_args": ["query_type", "employee_id"],
        "required_args": ["query_type"],
        "sanitizer": _sanitize_hr,
    },
    ProposedTool.ESCALATE_TO_HUMAN.value: {
        "callable": mock_tools.escalate_to_human,
        "call_args": ["reason", "conversation_summary"],
        "required_args": ["reason", "conversation_summary"],
        "sanitizer": _sanitize_escalate,
    },
}


def _tool_value(tool: ProposedTool | str) -> str:
    return tool.value if isinstance(tool, ProposedTool) else str(tool)


def _not_called(tool_name: str, tool_args: dict, error: str) -> ToolCallRecord:
    return ToolCallRecord(
        tool_name=tool_name,
        tool_args=tool_args,
        called=False,
        raw_tool_result=None,
        safe_tool_result=None,
        raw_fields_received=[],
        fields_released=[],
        fields_blocked_by_policy=[],
        fields_not_requested=[],
        error=error,
    )
