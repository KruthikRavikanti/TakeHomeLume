from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TrustTier(str, Enum):
    BLUE = "blue"
    RED = "red"
    GREY = "grey"


class AccountType(str, Enum):
    STANDARD = "standard"
    ADMIN = "admin"
    EXECUTIVE = "executive"
    SERVICE = "service"


class DriveType(str, Enum):
    TEAM = "team"
    CROSS_TEAM = "cross_team"
    PERSONAL = "personal"
    RESTRICTED = "restricted"
    LEGAL_HOLD = "legal_hold"


class AgentAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    PARTIAL_ALLOW = "partial_allow"
    CLARIFY = "clarify"
    ESCALATE = "escalate"


class RequesterContext(BaseModel):
    employee_id: str
    name: str
    department: str
    team: str
    role: str
    is_manager: bool = False
    verified: bool = False
    reports: List[str] = Field(default_factory=list)


class RequestContext(BaseModel):
    request_id: str
    conversation_id: str
    trust_tier: TrustTier
    requester: RequesterContext
    message: str


class IntentExtraction(BaseModel):
    intent: str
    requested_action: Optional[str] = None
    target_employee_id: Optional[str] = None
    target_employee_name: Optional[str] = None
    target_drive_id: Optional[str] = None
    target_drive_name: Optional[str] = None
    requested_fields: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    rationale: Optional[str] = None


class PolicyDecisionProposal(BaseModel):
    action: AgentAction
    rationale: str
    allowed_fields: List[str] = Field(default_factory=list)
    denied_fields: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    escalation_reason: Optional[str] = None
    clarification_question: Optional[str] = None


class ToolCallRecord(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = Field(default_factory=dict)
    success: bool
    result_summary: Optional[str] = None
    error: Optional[str] = None


class FinalDecision(BaseModel):
    action: AgentAction
    response: str
    rationale: str
    allowed_data: Dict[str, Any] = Field(default_factory=dict)
    denied_fields: List[str] = Field(default_factory=list)
    policy_references: List[str] = Field(default_factory=list)
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)


class DecisionLogRecord(BaseModel):
    request_id: str
    conversation_id: str
    trust_tier: TrustTier
    requester_employee_id: str
    intent: IntentExtraction
    proposal: PolicyDecisionProposal
    final_decision: FinalDecision
    tool_calls: List[ToolCallRecord] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class EmployeeRecord(BaseModel):
    employee_id: str
    name: str
    department: str
    team: str
    title: str
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    office: str
    work_email: str
    work_phone: str
    personal_email: Optional[str] = None
    personal_phone: Optional[str] = None
    home_address: Optional[str] = None
    salary: Optional[int] = None
    performance_rating: Optional[str] = None
    employment_status: str
    account_type: AccountType


class DriveRecord(BaseModel):
    drive_id: str
    name: str
    drive_type: DriveType
    owning_team: str
    owner_employee_id: Optional[str] = None


class Scenario(BaseModel):
    scenario_id: str
    description: str
    request: RequestContext
    expected_action: Optional[AgentAction] = None
    expected_allowed_fields: List[str] = Field(default_factory=list)
    expected_denied_fields: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
