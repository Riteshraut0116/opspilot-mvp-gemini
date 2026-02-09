from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .core.config import settings
from .core.models import ChatRequest, ChatResponse, ApproveRequest, RunRecord, UserContext
from .core.orchestrator import governed_run, execute_plan
from .core.store import store, new_run_id, now_iso

app = FastAPI(title=settings.app_name)

# CORS (MVP-friendly)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Resolve paths regardless of where uvicorn is executed from
# backend/app/main.py -> parents[2] = opspilot-mvp
ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"
ASSETS_DIR = FRONTEND_DIR / "assets"

# Serve UI assets
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


def get_user_from_headers(req: Request) -> UserContext:
    """
    Demo auth via headers:
      X-User: username
      X-Role: viewer|operator|admin
    """
    username = req.headers.get("x-user", "operator")
    role = req.headers.get("x-role", "operator")

    # Validate against demo users (optional)
    try:
        users = json.loads(settings.demo_users_json)
        if username in users:
            role = users[username].get("role", role)
    except Exception:
        pass

    try:
        return UserContext(username=username, role=role)  # type: ignore
    except Exception:
        return UserContext(username="operator", role="operator")


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=500, detail=f"Frontend not found at {index_path}")
    return index_path.read_text(encoding="utf-8")


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "app": settings.app_name,
        "gemini_configured": bool(settings.gemini_api_key),
        "model": settings.gemini_model,
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: Request, payload: ChatRequest):
    user = get_user_from_headers(req)

    plan, approval_required = governed_run(
        message=payload.message,
        skill_hint=payload.skill_hint,
        environment=payload.environment,
        change_id=payload.change_id,
        user=user.model_dump(),
    )

    run_id = new_run_id()
    status = "pending_approval" if approval_required else "running"

    run = RunRecord(
        run_id=run_id,
        created_at=now_iso(),
        requested_by=user.username,
        role=user.role,
        environment=payload.environment,
        message=payload.message,
        plan=plan,
        status=status,  # type: ignore
        approval_required=approval_required,
        evidence=[],
    )
    store.create_run(run)

    assistant_message = (
        f"I prepared a {'HIGH' if plan.intent.risk == 'high' else plan.intent.risk.upper()} "
        f"risk plan for “{plan.intent.skill}”. "
        + ("Approval is required before execution." if approval_required else "Executing now in dry-run mode.")
    )

    # ✅ FIXED: no multi-line string literals
    if not approval_required:
        try:
            evidence = execute_plan(plan)
            run = store.update_run(run_id, status="dry_run", evidence=evidence)
            assistant_message += "\n\n✅ Dry-run completed. Review evidence in the Run Details panel."
        except Exception as e:
            run = store.update_run(run_id, status="failed", error=str(e))
            assistant_message += f"\n\n❌ Execution failed: {e}"

    return ChatResponse(run=run, assistant_message=assistant_message)


@app.get("/api/runs")
def list_runs():
    return [r.model_dump() for r in store.list_runs()]


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    run = store.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run.model_dump()


@app.post("/api/runs/{run_id}/approve")
def approve_run(req: Request, run_id: str, payload: ApproveRequest):
    user = get_user_from_headers(req)
    run = store.get_run(run_id)

    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    if run.status != "pending_approval":
        raise HTTPException(status_code=400, detail="Run is not pending approval")

    # MVP governance: only admin can approve high risk
    if run.plan.intent.risk == "high" and user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin approval required for high-risk runs")

    if payload.decision == "rejected":
        run = store.update_run(
            run_id,
            status="rejected",
            approval_decision="rejected",
            evidence=run.evidence
            + [
                {
                    "type": "approval",
                    "by": user.username,
                    "decision": "rejected",
                    "comment": payload.comment,
                }
            ],
        )
        return run.model_dump()

    # approved
    run = store.update_run(
        run_id,
        status="running",
        approval_decision="approved",
        evidence=run.evidence
        + [
            {
                "type": "approval",
                "by": user.username,
                "decision": "approved",
                "comment": payload.comment,
            }
        ],
    )

    # execute
    try:
        evidence = run.evidence + execute_plan(run.plan)
        run = store.update_run(run_id, status="dry_run", evidence=evidence)
    except Exception as e:
        run = store.update_run(run_id, status="failed", error=str(e))

    return run.model_dump()


@app.post("/api/solarwinds/webhook")
def solarwinds_webhook(payload: dict):
    # payload example: {site, device, state, circuit}
    message = f"SolarWinds IP SLA event: {payload.get('state')} at {payload.get('site')} ({payload.get('device')})"

    plan, approval_required = governed_run(
        message=message,
        skill_hint="solarwinds_event",
        environment="prod",
        change_id=payload.get("change_id"),
        user={"username": "solarwinds", "role": "operator"},
    )

    run_id = new_run_id()
    run = RunRecord(
        run_id=run_id,
        created_at=now_iso(),
        requested_by="solarwinds",
        role="operator",
        environment="prod",
        message=message,
        plan=plan,
        status="pending_approval" if approval_required else "running",  # type: ignore
        approval_required=approval_required,
        evidence=[{"type": "webhook", "payload": payload}],
    )
    store.create_run(run)

    if not approval_required:
        evidence = run.evidence + execute_plan(plan)
        store.update_run(run_id, status="dry_run", evidence=evidence)

    return {"run_id": run_id, "approval_required": approval_required}


@app.post("/api/vuln/upload")
def upload_vuln(file: UploadFile = File(...)):
    # MVP: accept CSV and count rows
    content = file.file.read().decode("utf-8", errors="ignore")
    lines = [ln for ln in content.splitlines() if ln.strip()]
    rows = max(0, len(lines) - 1)  # assume header

    message = (
        f"Vulnerability triage for uploaded file {file.filename} with approx {rows} rows. "
        "Segment by team (Wintel/Linux/App) and prioritize."
    )

    plan, approval_required = governed_run(
        message=message,
        skill_hint="vuln_triage",
        environment="dev",
        change_id=None,
        user={"username": "operator", "role": "operator"},
    )

    # Inject row count into first step args for evidence
    if plan.steps:
        plan.steps[0].args = {**plan.steps[0].args, "input_rows": rows}

    run_id = new_run_id()
    run = RunRecord(
        run_id=run_id,
        created_at=now_iso(),
        requested_by="operator",
        role="operator",
        environment="dev",
        message=message,
        plan=plan,
        status="pending_approval" if approval_required else "running",  # type: ignore
        approval_required=approval_required,
        evidence=[{"type": "upload", "filename": file.filename, "rows": rows}],
    )
    store.create_run(run)

    if not approval_required:
        evidence = run.evidence + execute_plan(plan)
        store.update_run(run_id, status="dry_run", evidence=evidence)

    return {"run_id": run_id, "rows": rows, "approval_required": approval_required}