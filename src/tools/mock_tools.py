from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict

from src.tools.mock_data import (
    find_employee,
    get_drive_by_id_or_name,
    get_employee_by_id,
)


def _model_to_dict(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def reset_password(employee_id: str) -> dict:
    employee = get_employee_by_id(employee_id) or find_employee(employee_id)
    if not employee:
        return {
            "status": "not_found",
            "employee_id": employee_id,
            "account_type": None,
            "temp_password": None,
            "expires_in": None,
        }

    return {
        "status": "success",
        "employee_id": employee.employee_id,
        "account_type": employee.account_type.value,
        "temp_password": f"Temp-{employee.employee_id}-Reset-2026",
        "expires_in": "30 minutes",
    }


def lookup_employee(query: str) -> dict:
    employee = find_employee(query)
    if not employee:
        return {
            "status": "not_found",
            "query": query,
            "employee": None,
        }

    return {
        "status": "success",
        "employee": _model_to_dict(employee),
    }


def grant_file_access(
    employee_id: str,
    drive_id: str,
    access_level: str,
    duration_days: int | None,
) -> dict:
    employee = get_employee_by_id(employee_id) or find_employee(employee_id)
    drive = get_drive_by_id_or_name(drive_id)
    expires = None
    if duration_days is not None:
        expires = (datetime.utcnow() + timedelta(days=duration_days)).date().isoformat()

    if not employee or not drive:
        return {
            "status": "not_found",
            "employee_id": employee_id,
            "drive_id": drive_id,
            "drive_type": drive.drive_type.value if drive else None,
            "owning_team": drive.owning_team if drive else None,
            "access_level": access_level,
            "access_granted": False,
            "expires": expires,
        }

    return {
        "status": "success",
        "employee_id": employee.employee_id,
        "drive_id": drive.drive_id,
        "drive_type": drive.drive_type.value,
        "owning_team": drive.owning_team,
        "access_level": access_level,
        "access_granted": True,
        "expires": expires,
    }


def query_hr_database(query_type: str, employee_id: str | None) -> dict:
    if query_type == "policy":
        return {
            "status": "success",
            "query_type": query_type,
            "policy_text": (
                "Employees receive 20 days of PTO annually, 12 paid company "
                "holidays, medical/dental/vision benefits, a 401(k) match up "
                "to 4%, and 16 weeks of paid parental leave for eligible staff."
            ),
        }

    if query_type != "individual":
        return {
            "status": "unsupported_query_type",
            "query_type": query_type,
            "employee_id": employee_id,
        }

    if employee_id is None:
        return {
            "status": "missing_employee_id",
            "query_type": query_type,
            "employee_id": None,
        }

    employee = get_employee_by_id(employee_id) or find_employee(employee_id)
    if not employee:
        return {
            "status": "not_found",
            "query_type": query_type,
            "employee_id": employee_id,
            "hr_record": None,
        }

    return {
        "status": "success",
        "query_type": query_type,
        "employee_id": employee.employee_id,
        "hr_record": {
            "salary": employee.salary,
            "bonus_target": _bonus_target_for(employee.salary),
            "last_review": "2026-01-15",
            "performance_rating": employee.performance_rating,
            "disciplinary_actions": _disciplinary_actions_for(employee.employee_id),
            "employment_status": employee.employment_status,
        },
    }


def escalate_to_human(reason: str, conversation_summary: str) -> dict:
    return {
        "status": "escalated",
        "ticket_id": f"HELP-{abs(hash((reason, conversation_summary))) % 100000:05d}",
        "estimated_response": "1 business day",
        "reason": reason,
        "conversation_summary": conversation_summary,
    }


def _bonus_target_for(salary: int | None) -> int | None:
    if salary is None:
        return None
    return round(salary * 0.12)


def _disciplinary_actions_for(employee_id: str) -> list[str]:
    if employee_id == "EMP-7781":
        return ["Written warning issued 2025-11-03 for expense policy violation."]
    return []
