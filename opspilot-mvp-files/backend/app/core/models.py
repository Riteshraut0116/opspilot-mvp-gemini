from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal, Any


Skill = Literal[
    'patching_exclusion',
    'storage_ops',
    'manageengine_downtime',
    'vuln_triage',
    'solarwinds_event',
]


class UserContext(BaseModel):
    username: str = 'operator'
    role: Literal['admin', 'operator', 'viewer'] = 'operator'


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    skill_hint: Skill | None = None
    environment: Literal['dev', 'test', 'prod'] = 'dev'
    change_id: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Intent(BaseModel):
    skill: Skill
    summary: str
    risk: Literal['low', 'medium', 'high'] = 'low'
    needs_approval: bool = False


class PlanStep(BaseModel):
    id: str
    title: str
    action: str
    tool: Skill
    args: dict[str, Any] = Field(default_factory=dict)
    safe: bool = True


class ExecutionPlan(BaseModel):
    intent: Intent
    steps: list[PlanStep]
    assumptions: list[str] = Field(default_factory=list)


class RunRecord(BaseModel):
    run_id: str
    created_at: str
    requested_by: str
    role: str
    environment: str
    message: str
    plan: ExecutionPlan
    status: Literal['pending_approval', 'running', 'succeeded', 'failed', 'rejected', 'dry_run']
    approval_required: bool = False
    approval_decision: Literal['approved', 'rejected', 'none'] = 'none'
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    error: str | None = None


class ApproveRequest(BaseModel):
    decision: Literal['approved', 'rejected']
    comment: str | None = None


class ChatResponse(BaseModel):
    run: RunRecord
    assistant_message: str
