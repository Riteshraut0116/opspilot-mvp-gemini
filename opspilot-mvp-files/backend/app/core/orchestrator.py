from __future__ import annotations

from typing import Any

from .models import ExecutionPlan
from .llm_gemini import generate_plan
from .policy import apply_policy
from .tools import TOOL_REGISTRY


def plan_from_llm(message: str, skill_hint: str | None, context: dict[str, Any]) -> ExecutionPlan:
    data = generate_plan(message, skill_hint, context)
    return ExecutionPlan.model_validate(data)


def execute_plan(plan: ExecutionPlan) -> list[dict[str, Any]]:
    """Runs tool adapters and returns evidence entries (dict)."""
    evidence: list[dict[str, Any]] = []
    for step in plan.steps:
        tool_name = step.tool
        tool_fn = TOOL_REGISTRY.get(tool_name)
        if not tool_fn:
            evidence.append({'step': step.id, 'error': f'No adapter registered for {tool_name}'})
            continue
        result = tool_fn(step.args)
        evidence.append({'step': step.id, 'title': step.title, 'tool': tool_name, 'result': result})
    return evidence


def governed_run(message: str, skill_hint: str | None, environment: str, change_id: str | None, user: dict[str, Any]) -> tuple[ExecutionPlan, bool]:
    context = {
        'environment': environment,
        'change_id_present': bool(change_id),
        'user': user,
    }
    plan = plan_from_llm(message, skill_hint, context)
    plan = apply_policy(plan, environment=environment, change_id=change_id)
    approval_required = plan.intent.needs_approval
    return plan, approval_required
