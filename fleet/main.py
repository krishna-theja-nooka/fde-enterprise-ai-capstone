import json
import sqlite3
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.security import APIKeyHeader

from fleet import __version__
from fleet.actions import ActionError, Actions
from fleet.config import Settings
from fleet.db import Store
from fleet.models import AskRequest, AskResponse, DecisionRequest, FeedbackRequest, ProposalRequest
from fleet.observability import RateLimiter, save_trace, summary
from fleet.orchestrator import Copilot
from fleet.retrieval import Retriever
from fleet.tools import Tools, ToolUnavailable

key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
FAULTS = {"transient_tool", "tool_failure", "tool_timeout", "retrieval_failure"}


def create_app(settings=None):
    settings = settings or Settings.from_env()
    settings.validate()
    store = Store(settings.db_path)
    tools = Tools(store, settings)
    retriever = Retriever(store)
    copilot = Copilot(tools, retriever)
    actions = Actions(store, tools, retriever, settings)
    limiter = RateLimiter(settings.requests_per_minute)

    @asynccontextmanager
    async def lifespan(app):
        store.initialize(settings.seed_date)
        yield

    app = FastAPI(
        title="Fleet Intelligence Copilot",
        version=__version__,
        lifespan=lifespan,
        description="Synthetic fleet operations with cited policies, bounded tools, "
        "human approvals, and auditable actions. No paid services required.",
    )
    app.state.store = store
    app.state.settings = settings
    app.state.copilot = copilot
    app.state.actions = actions

    def principal(request: Request, key=Depends(key_header)):
        actor = settings.keys.get(key)
        if actor is None:
            raise HTTPException(
                401, "Valid X-API-Key required", headers={"WWW-Authenticate": "APIKey"}
            )
        request.state.context["actor_id"] = actor["id"]
        if not limiter.allow(actor["id"]):
            raise HTTPException(429, "Request quota exceeded", headers={"Retry-After": "60"})
        fault = request.headers.get("X-Demo-Fault")
        if fault:
            if not settings.demo_mode:
                raise HTTPException(403, "Fault injection is disabled")
            if fault not in FAULTS:
                raise HTTPException(422, "Unknown demo fault")
            request.state.context["fault"] = fault
        return actor

    def operator(actor=Depends(principal)):
        if actor["role"] != "operator":
            raise HTTPException(403, "Operator role required")
        return actor

    def approver(actor=Depends(principal)):
        if actor["role"] != "approver":
            raise HTTPException(403, "Approver role required")
        return actor

    @app.middleware("http")
    async def trace(request: Request, call_next):
        started = time.perf_counter()
        request.state.context = {"trace_id": str(uuid4()), "events": [], "retry_count": 0}
        context = request.state.context
        try:
            response = await call_next(request)
        except Exception:
            context["outcome"] = "error"
            response = JSONResponse(
                status_code=503,
                content={
                    "detail": "Service unavailable; no unverified recommendation is returned",
                    "trace_id": context["trace_id"],
                },
            )
        if request.url.path.startswith("/v1/"):
            if response.status_code >= 400:
                context["outcome"] = "error"
            try:
                # Templates prevent unknown paths or IDs becoming arbitrary log content.
                route = request.scope.get("route")
                path = getattr(route, "path", "/v1/unmatched")
                save_trace(
                    store,
                    context,
                    path,
                    request.method,
                    response.status_code,
                    (time.perf_counter() - started) * 1000,
                )
            except sqlite3.Error:
                response = JSONResponse(
                    status_code=503,
                    content={
                        "detail": "Audit storage unavailable. "
                        "Inspect approval state before retrying.",
                        "trace_id": context["trace_id"],
                        "trace_persisted": False,
                    },
                )
        response.headers["X-Trace-ID"] = context["trace_id"]
        return response

    @app.exception_handler(ActionError)
    async def action_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={"detail": error.message, "trace_id": request.state.context["trace_id"]},
        )

    @app.exception_handler(ToolUnavailable)
    async def tool_error(request, error):
        request.state.context["outcome"] = "degraded"
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Required evidence unavailable; no action was performed",
                "trace_id": request.state.context["trace_id"],
            },
        )

    @app.get("/health", tags=["Operations"])
    def health():
        return {"status": "ok", "version": __version__, "demo_mode": settings.demo_mode}

    @app.get("/ready", tags=["Operations"])
    def ready():
        try:
            policy_ids = {
                row["policy_id"] for row in store.rows("SELECT policy_id FROM fleet_policies")
            }
            if not {"P-SAFETY", "P-REPLACE", "P-MAINT", "P-CONTRACT"}.issubset(policy_ids):
                raise HTTPException(503, "Required policy corpus is incomplete")
            with store.connect(write=True) as con:
                con.execute("INSERT OR REPLACE INTO metadata VALUES ('readiness_probe','ok')")
        except sqlite3.Error as exc:
            raise HTTPException(503, "Database unavailable") from exc
        return {
            "status": "ready",
            "provider": "deterministic_local",
            "data_as_of": store.seed_date().isoformat(),
            "policies": len(policy_ids),
        }

    @app.get("/", response_class=HTMLResponse, include_in_schema=False)
    def dashboard():
        return (Path(__file__).parent / "static/dashboard.html").read_text()

    @app.post("/v1/copilot/ask", response_model=AskResponse, tags=["Copilot"])
    def ask(body: AskRequest, request: Request, actor=Depends(principal)):
        return copilot.ask(body.question, request.state.context)

    @app.post("/v1/actions/propose", tags=["Approval workflow"])
    def propose(body: ProposalRequest, request: Request, actor=Depends(operator)):
        return actions.propose(body, actor, request.state.context)

    @app.get("/v1/approvals/{approval_id}", tags=["Approval workflow"])
    def approval(approval_id: str, actor=Depends(principal)):
        return actions.get(approval_id, actor)

    @app.post("/v1/approvals/{approval_id}/decision", tags=["Approval workflow"])
    def decide(approval_id: str, body: DecisionRequest, request: Request, actor=Depends(approver)):
        return actions.decide(approval_id, body.decision, actor, request.state.context)

    @app.post("/v1/approvals/{approval_id}/execute", tags=["Approval workflow"])
    def execute(approval_id: str, request: Request, actor=Depends(operator)):
        if request.state.context.get("fault"):
            raise ToolUnavailable("Demo execution failure")
        return actions.execute(approval_id, actor, request.state.context)

    @app.get("/v1/cases", tags=["Evidence"])
    def cases(actor=Depends(principal)):
        if actor["role"] == "approver":
            return {"cases": store.rows("SELECT * FROM cases ORDER BY created_at DESC LIMIT 100")}
        return {
            "cases": store.rows(
                "SELECT * FROM cases WHERE created_by=? ORDER BY created_at DESC LIMIT 100",
                (actor["id"],),
            )
        }

    @app.get("/v1/policies/{policy_id}", tags=["Evidence"])
    def policy(policy_id: str, actor=Depends(principal)):
        rows = store.rows("SELECT * FROM fleet_policies WHERE policy_id=?", (policy_id,))
        if not rows:
            raise HTTPException(404, "Policy not found")
        return rows[0]

    @app.get("/v1/traces/{trace_id}", tags=["Operations"])
    def get_trace(trace_id: str, actor=Depends(principal)):
        rows = store.rows("SELECT * FROM audit_traces WHERE trace_id=?", (trace_id,))
        if not rows:
            raise HTTPException(404, "Trace not found")
        result = rows[0]
        if actor["role"] != "approver" and result["actor_id"] != actor["id"]:
            raise HTTPException(403, "Trace belongs to another user")
        result["events"] = json.loads(result.pop("events_json"))
        return result

    @app.get("/v1/audit/actions/{approval_id}", tags=["Operations"])
    def action_audit(approval_id: str, actor=Depends(principal)):
        actions.get(approval_id, actor)
        return {
            "events": store.rows(
                "SELECT * FROM action_audit WHERE approval_id=? ORDER BY created_at", (approval_id,)
            )
        }

    @app.get("/v1/metrics/summary", tags=["Operations"])
    def metrics(actor=Depends(approver)):
        return summary(store)

    @app.post("/v1/feedback", tags=["Evidence"])
    def feedback(body: FeedbackRequest, actor=Depends(principal)):
        trace = get_trace(body.trace_id, actor)
        if trace["actor_id"] != actor["id"]:
            raise HTTPException(403, "Only the request owner can submit feedback")
        with store.connect(write=True) as con:
            con.execute(
                "INSERT INTO feedback VALUES (?,?,?) ON CONFLICT(trace_id,actor_id) "
                "DO UPDATE SET score=excluded.score",
                (body.trace_id, actor["id"], body.score),
            )
        return {"status": "recorded", "trace_id": body.trace_id, "score": body.score}

    return app


app = create_app()
