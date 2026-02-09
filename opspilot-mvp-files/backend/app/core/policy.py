from __future__ import annotations

import re
from .config import settings
from .models import Intent, ExecutionPlan


def _has_change_id(change_id: str | None) -> bool:
    if not change_id:
        return False
    # basic: CHG123456 or INC12345 etc.
    return bool(re.match(r'^[A-Z]{2,5}\d{4,}$', change_id.strip()))


def apply_policy(plan: ExecutionPlan, environment: str, change_id: str | None) -> ExecutionPlan:
    """Adds/overrides approval flags based on simple rules."""
    needs_approval = plan.intent.needs_approval
    risk = plan.intent.risk

    # Production always requires change id for risky actions
    if environment == 'prod' and settings.require_change_id_for_prod and not _has_change_id(change_id):
        needs_approval = True
        risk = 'high'

    # Storage unmount/perm changes are always high risk in prod
    if plan.intent.skill == 'storage_ops' and environment == 'prod':
        needs_approval = True
        risk = 'high'

    # Bulk ops threshold triggers approval
    for s in plan.steps:
        # heuristic: if args include a list of targets
        targets = s.args.get('targets') or s.args.get('servers') or s.args.get('hosts')
        if isinstance(targets, list) and len(targets) >= settings.bulk_threshold:
            needs_approval = True
            risk = 'high'

    intent = plan.intent.model_copy(update={'needs_approval': needs_approval, 'risk': risk})
    return plan.model_copy(update={'intent': intent})
