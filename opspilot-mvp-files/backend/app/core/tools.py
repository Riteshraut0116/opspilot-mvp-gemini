from __future__ import annotations

import time
from typing import Any


class ToolResult(dict):
    pass


def tool_patching_exclusion(args: dict[str, Any]) -> ToolResult:
    # Simulated adapter (MVP)
    servers = args.get('servers', [])
    window = args.get('patch_window', 'unknown')
    time.sleep(0.2)
    return ToolResult({
        'adapter': 'patching_exclusion',
        'action': 'update_exclusions',
        'servers_count': len(servers),
        'patch_window': window,
        'result': 'dry-run: exclusions would be updated in patching tool',
    })


def tool_storage_ops(args: dict[str, Any]) -> ToolResult:
    time.sleep(0.2)
    return ToolResult({
        'adapter': 'storage_ops',
        'action': args.get('action', 'mount'),
        'targets': args.get('targets', []),
        'result': 'dry-run: would execute pre-checks, action, and post-checks',
    })


def tool_manageengine_downtime(args: dict[str, Any]) -> ToolResult:
    time.sleep(0.2)
    return ToolResult({
        'adapter': 'manageengine_downtime',
        'monitors': args.get('monitors') or args.get('servers') or [],
        'window': {'start': args.get('start'), 'end': args.get('end'), 'timezone': args.get('timezone', 'UTC')},
        'result': 'dry-run: downtime schedule would be created/updated via ManageEngine API',
    })


def tool_vuln_triage(args: dict[str, Any]) -> ToolResult:
    time.sleep(0.2)
    return ToolResult({
        'adapter': 'vuln_triage',
        'input_rows': args.get('input_rows', 0),
        'result': 'dry-run: findings would be segmented and tickets proposed',
    })


def tool_solarwinds_event(args: dict[str, Any]) -> ToolResult:
    time.sleep(0.2)
    return ToolResult({
        'adapter': 'solarwinds_event',
        'site': args.get('site'),
        'device': args.get('device'),
        'state': args.get('state'),
        'result': 'dry-run: would trigger AWX template + notify DL',
    })


TOOL_REGISTRY = {
    'patching_exclusion': tool_patching_exclusion,
    'storage_ops': tool_storage_ops,
    'manageengine_downtime': tool_manageengine_downtime,
    'vuln_triage': tool_vuln_triage,
    'solarwinds_event': tool_solarwinds_event,
}
