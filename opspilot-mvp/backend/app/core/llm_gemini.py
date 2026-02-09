from __future__ import annotations

import json
from typing import Any

from .config import settings


SYSTEM_INSTRUCTIONS = """You are OpsPilot, an agentic infrastructure automation assistant.
Return STRICT JSON only, matching the provided schema.
Never include markdown fences or commentary.
Only choose skill from allowed list.
"""


ALLOWED_SKILLS = [
    'patching_exclusion',
    'storage_ops',
    'manageengine_downtime',
    'vuln_triage',
    'solarwinds_event',
]


def _stub_plan(user_message: str, skill_hint: str | None = None) -> dict[str, Any]:
    """Offline fallback when GEMINI_API_KEY isn't set."""
    skill = skill_hint or 'patching_exclusion'
    if skill not in ALLOWED_SKILLS:
        skill = 'patching_exclusion'

    return {
        'intent': {
            'skill': skill,
            'summary': f'Dry-run plan for: {user_message[:80]}',
            'risk': 'medium' if skill in ('storage_ops',) else 'low',
            'needs_approval': skill in ('storage_ops',),
        },
        'steps': [
            {
                'id': 'S1',
                'title': 'Validate request & policy',
                'action': 'Validate inputs (targets, window, change id) and apply policy gates.',
                'tool': skill,
                'args': {},
                'safe': True,
            },
            {
                'id': 'S2',
                'title': 'Execute (dry-run)',
                'action': 'Call the tool adapter in dry-run mode and capture evidence.',
                'tool': skill,
                'args': {'note': 'This is a stub response. Set GEMINI_API_KEY for real planning.'},
                'safe': True,
            },
        ],
        'assumptions': [
            'This is an MVP dry-run. Replace adapters with real integrations.',
        ],
    }


def generate_plan(user_message: str, skill_hint: str | None, context: dict[str, Any]) -> dict[str, Any]:
    """Returns a dict that matches ExecutionPlan schema."""

    if not settings.gemini_api_key:
        return _stub_plan(user_message, skill_hint)

    try:
        import google.generativeai as genai

        genai.configure(api_key=settings.gemini_api_key)
        model = genai.GenerativeModel(
            model_name=settings.gemini_model,
            system_instruction=SYSTEM_INSTRUCTIONS,
        )

        schema = {
            'type': 'object',
            'properties': {
                'intent': {
                    'type': 'object',
                    'properties': {
                        'skill': {'type': 'string', 'enum': ALLOWED_SKILLS},
                        'summary': {'type': 'string'},
                        'risk': {'type': 'string', 'enum': ['low', 'medium', 'high']},
                        'needs_approval': {'type': 'boolean'},
                    },
                    'required': ['skill', 'summary', 'risk', 'needs_approval'],
                },
                'steps': {
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'id': {'type': 'string'},
                            'title': {'type': 'string'},
                            'action': {'type': 'string'},
                            'tool': {'type': 'string', 'enum': ALLOWED_SKILLS},
                            'args': {'type': 'object'},
                            'safe': {'type': 'boolean'},
                        },
                        'required': ['id', 'title', 'action', 'tool', 'args', 'safe'],
                    },
                },
                'assumptions': {'type': 'array', 'items': {'type': 'string'}},
            },
            'required': ['intent', 'steps', 'assumptions'],
        }

        prompt = {
            'task': 'Create an execution plan for infrastructure automation (MVP).',
            'user_message': user_message,
            'skill_hint': skill_hint,
            'context': context,
            'output_schema': schema,
            'rules': [
                'Return STRICT JSON only. No extra keys.',
                'Prefer safe, reversible steps. Mark unsafe steps safe=false.',
                'If request is risky or ambiguous, set needs_approval=true.',
                'Keep args minimal and practical for adapters.',
            ],
        }

        resp = model.generate_content(json.dumps(prompt), generation_config={'temperature': 0})
        text = resp.text.strip()
        # Some SDKs may return leading/trailing code fences; strip defensively
        text = text.replace('```json', '').replace('```', '').strip()
        return json.loads(text)

    except Exception:
        # if anything goes wrong, degrade gracefully
        return _stub_plan(user_message, skill_hint)
