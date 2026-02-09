from __future__ import annotations

import uuid
import datetime as dt
from typing import Any
from .models import RunRecord


class InMemoryStore:
    """MVP store. Swap with Postgres/SQLite later."""

    def __init__(self):
        self.runs: dict[str, RunRecord] = {}

    def create_run(self, run: RunRecord) -> RunRecord:
        self.runs[run.run_id] = run
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        return self.runs.get(run_id)

    def list_runs(self) -> list[RunRecord]:
        # newest first
        return sorted(self.runs.values(), key=lambda r: r.created_at, reverse=True)

    def update_run(self, run_id: str, **kwargs: Any) -> RunRecord:
        run = self.runs[run_id]
        updated = run.model_copy(update=kwargs)
        self.runs[run_id] = updated
        return updated


store = InMemoryStore()

def new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def now_iso() -> str:
    return dt.datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'
