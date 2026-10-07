import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from fleet.db import digest, now
from fleet.retrieval import POLICY_FOR_ACTION


class ActionError(Exception):
    def __init__(self, status, message):
        self.status = status
        self.message = message


class Actions:
    def __init__(self, store, tools, retriever, settings):
        self.store, self.tools, self.retriever, self.settings = store, tools, retriever, settings

    def evidence(self, action, vehicle_id, con=None):
        vehicle = self.tools.vehicle(vehicle_id, con)
        if vehicle is None:
            raise ActionError(404, "Unknown vehicle")
        required = POLICY_FOR_ACTION[action]
        policies = self.tools._rows(
            "SELECT * FROM fleet_policies WHERE policy_id=?", (required,), con
        )
        if not policies:
            raise ActionError(503, "Required policy is missing; action is blocked")
        today = self.store.seed_date()
        recent = [
            e
            for e in vehicle["maintenance"]
            if (today - timedelta(days=30)).isoformat() <= e["event_date"] <= today.isoformat()
        ]
        if action == "escalation" and len(recent) < 3:
            raise ActionError(
                409, "Escalation requires at least three maintenance events in 30 days"
            )
        if action == "replacement_recommendation" and not (
            vehicle["vehicle"]["status"] in {"maintenance", "unavailable"}
            and vehicle["active_contracts"]
            and any(
                e["state"] == "open" and e["severity"] == "high" for e in vehicle["maintenance"]
            )
        ):
            raise ActionError(409, "Replacement eligibility is not met; review policy P-REPLACE")
        return {"action": action, "vehicle": vehicle, "policy": policies[0]}

    @staticmethod
    def audit(con, approval_id, actor_id, event, trace_id):
        con.execute(
            "INSERT INTO action_audit VALUES (?,?,?,?,?,?)",
            (
                str(uuid4()),
                approval_id,
                actor_id,
                event,
                trace_id,
                now(),
            ),
        )

    def propose(self, request, principal, context):
        evidence = self.tools.call(
            "action_evidence", lambda: self.evidence(request.action, request.vehicle_id), context
        )
        self.retriever.retrieve(request.action, context, POLICY_FOR_ACTION[request.action])
        payload = {
            "action": request.action,
            "vehicle_id": request.vehicle_id,
            "description": f"Approved {request.action} review for {request.vehicle_id}. "
            "Simulated internal case; no external notification or assignment.",
            "citations": [self.retriever.citation(evidence["policy"])],
        }
        aid = str(uuid4())
        with self.store.connect(write=True) as con:
            previous = con.execute(
                "SELECT * FROM approvals WHERE requested_by=? AND idempotency_key=?",
                (principal["id"], request.idempotency_key),
            ).fetchone()
            if previous:
                if (
                    previous["action"] != request.action
                    or previous["vehicle_id"] != request.vehicle_id
                ):
                    raise ActionError(409, "Idempotency key already used for a different action")
                return self.serialize(dict(previous))
            # Re-read under the write lock: proposal binds a coherent current snapshot.
            evidence = self.evidence(request.action, request.vehicle_id, con)
            payload["citations"] = [self.retriever.citation(evidence["policy"])]
            con.execute(
                "INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    aid,
                    principal["id"],
                    request.idempotency_key,
                    request.action,
                    request.vehicle_id,
                    json.dumps(payload),
                    digest(evidence),
                    "pending",
                    None,
                    now(),
                    (
                        datetime.now(UTC) + timedelta(seconds=self.settings.approval_ttl_seconds)
                    ).isoformat(),
                ),
            )
            self.audit(con, aid, principal["id"], "proposed", context["trace_id"])
            row = dict(
                con.execute("SELECT * FROM approvals WHERE approval_id=?", (aid,)).fetchone()
            )
        context["outcome"] = "pending_approval"
        return self.serialize(row)

    @staticmethod
    def serialize(row):
        row["payload"] = json.loads(row.pop("payload_json"))
        row.pop("evidence_digest", None)
        row.pop("idempotency_key", None)
        return row

    def get(self, approval_id, principal):
        rows = self.store.rows("SELECT * FROM approvals WHERE approval_id=?", (approval_id,))
        if not rows:
            raise ActionError(404, "Approval not found")
        if principal["role"] != "approver" and rows[0]["requested_by"] != principal["id"]:
            raise ActionError(403, "Approval belongs to another operator")
        return self.serialize(rows[0])

    def decide(self, approval_id, decision, principal, context):
        with self.store.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if not row:
                raise ActionError(404, "Approval not found")
            if row["requested_by"] == principal["id"]:
                raise ActionError(403, "Self-approval is prohibited")
            self.ensure_live(row)
            if row["status"] != "pending":
                raise ActionError(409, "Only pending proposals can be decided")
            self.ensure_current(row, con)
            status = "approved" if decision == "approve" else "rejected"
            con.execute(
                "UPDATE approvals SET status=?,decided_by=? WHERE approval_id=?",
                (status, principal["id"], approval_id),
            )
            self.audit(con, approval_id, principal["id"], status, context["trace_id"])
        context["outcome"] = status
        return self.get(approval_id, principal)

    @staticmethod
    def ensure_live(row):
        if datetime.fromisoformat(row["expires_at"]) <= datetime.now(UTC):
            raise ActionError(409, "Approval expired; create a new proposal")

    def ensure_current(self, row, con):
        evidence = self.evidence(row["action"], row["vehicle_id"], con)
        if digest(evidence) != row["evidence_digest"]:
            raise ActionError(409, "Evidence changed; create and approve a new proposal")

    def execute(self, approval_id, principal, context):
        with self.store.connect(write=True) as con:
            row = con.execute(
                "SELECT * FROM approvals WHERE approval_id=?", (approval_id,)
            ).fetchone()
            if not row:
                raise ActionError(404, "Approval not found")
            if row["requested_by"] != principal["id"]:
                raise ActionError(403, "Only the proposing operator can execute this action")
            if row["status"] == "executed":
                return dict(
                    con.execute(
                        "SELECT * FROM cases WHERE approval_id=?", (approval_id,)
                    ).fetchone()
                )
            self.ensure_live(row)
            if row["status"] != "approved" or row["decided_by"] == principal["id"]:
                raise ActionError(409, "A different approver must approve before execution")
            self.ensure_current(row, con)
            payload = json.loads(row["payload_json"])
            cid = "CASE-" + str(uuid4())[:8].upper()
            con.execute(
                "INSERT INTO cases VALUES (?,?,?,?,?,?,?)",
                (
                    cid,
                    approval_id,
                    row["vehicle_id"],
                    row["action"],
                    payload["description"],
                    principal["id"],
                    now(),
                ),
            )
            con.execute(
                "UPDATE approvals SET status='executed' WHERE approval_id=?", (approval_id,)
            )
            self.audit(con, approval_id, principal["id"], "executed", context["trace_id"])
            result = dict(con.execute("SELECT * FROM cases WHERE case_id=?", (cid,)).fetchone())
        context["outcome"] = "executed"
        return result
