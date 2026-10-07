from concurrent.futures import ThreadPoolExecutor

import pytest

from tests.conftest import decide, execute, headers, propose


@pytest.mark.parametrize("action", ["support_case", "escalation", "replacement_recommendation"])
def test_all_actions_require_separate_approval(client, action):
    aid = propose(client, action)
    assert execute(client, aid).status_code == 409
    assert client.get("/v1/cases", headers=headers()).json()["cases"] == []
    assert (
        client.post(
            f"/v1/approvals/{aid}/decision", headers=headers(), json={"decision": "approve"}
        ).status_code
        == 403
    )
    assert decide(client, aid).status_code == 200
    first = execute(client, aid)
    assert first.status_code == 200
    assert first.json()["kind"] == action
    assert execute(client, aid).json()["case_id"] == first.json()["case_id"]
    assert len(client.get("/v1/cases", headers=headers()).json()["cases"]) == 1
    events = client.get(f"/v1/audit/actions/{aid}", headers=headers()).json()["events"]
    assert [e["event"] for e in events] == ["proposed", "approved", "executed"]
    assert events[0]["actor_id"] != events[1]["actor_id"]


def test_rejection_prevents_execution(client):
    aid = propose(client)
    assert decide(client, aid, "reject").json()["status"] == "rejected"
    assert execute(client, aid).status_code == 409
    assert decide(client, aid).status_code == 409


@pytest.mark.parametrize("phase", ["decision", "execution"])
@pytest.mark.parametrize("mutation", ["vehicle", "policy", "maintenance", "contract"])
def test_stale_evidence_blocks_action(client, phase, mutation):
    aid = propose(client, "replacement_recommendation")
    if phase == "execution":
        assert decide(client, aid).status_code == 200
    store = client.app.state.store
    with store.connect(write=True) as con:
        sql = {
            "vehicle": "UPDATE vehicles SET version=version+1 WHERE vehicle_id='V-102'",
            "policy": "UPDATE fleet_policies SET content=content||' Changed.' "
            "WHERE policy_id='P-REPLACE'",
            "maintenance": "UPDATE maintenance_events SET description='Updated inspection' "
            "WHERE event_id='M-301'",
            "contract": "UPDATE contracts SET monthly_rate_usd=1234 WHERE vehicle_id='V-102'",
        }[mutation]
        con.execute(sql)
    r = decide(client, aid) if phase == "decision" else execute(client, aid)
    assert r.status_code == 409
    assert "Evidence changed" in r.json()["detail"]
    assert store.rows("SELECT * FROM cases") == []


def test_expiry(client):
    aid = propose(client)
    assert decide(client, aid).status_code == 200
    with client.app.state.store.connect(write=True) as con:
        con.execute("UPDATE approvals SET expires_at='2000-01-01T00:00:00+00:00'")
    assert execute(client, aid).status_code == 409


def test_idempotency_and_conflict(client):
    aid = propose(client)
    assert propose(client) == aid
    r = client.post(
        "/v1/actions/propose",
        headers=headers(),
        json={
            "action": "support_case",
            "vehicle_id": "V-102",
            "idempotency_key": "test-action-001",
        },
    )
    assert r.status_code == 409


def test_concurrent_execution_creates_one_case(client):
    aid = propose(client)
    assert decide(client, aid).status_code == 200
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: execute(client, aid), range(4)))
    assert {r.status_code for r in results} == {200}
    assert len({r.json()["case_id"] for r in results}) == 1
    assert len(client.app.state.store.rows("SELECT * FROM cases")) == 1


@pytest.mark.parametrize("action", ["escalation", "replacement_recommendation"])
def test_ineligible_vehicle_blocked(client, action):
    r = client.post(
        "/v1/actions/propose",
        headers=headers(),
        json={"action": action, "vehicle_id": "V-103", "idempotency_key": "ineligible-1"},
    )
    assert r.status_code == 409


def test_self_approval_even_with_approver_role(client):
    aid = propose(client)
    client.app.state.settings.keys["demo-approver"] = {"id": "operator-1", "role": "approver"}
    assert decide(client, aid).status_code == 403


def test_other_operator_cannot_view_or_execute(client):
    aid = propose(client)
    client.app.state.settings.keys["other-operator"] = {"id": "operator-2", "role": "operator"}
    other = {"X-API-Key": "other-operator"}
    assert client.get(f"/v1/approvals/{aid}", headers=other).status_code == 403
    assert client.post(f"/v1/approvals/{aid}/execute", headers=other).status_code == 403


def test_atomic_rollback_if_action_audit_fails(client, monkeypatch):
    aid = propose(client)
    assert decide(client, aid).status_code == 200

    def fail(*args):
        raise RuntimeError("Simulated audit failure")

    monkeypatch.setattr(client.app.state.actions, "audit", fail)
    assert execute(client, aid).status_code == 503
    assert client.app.state.store.rows("SELECT * FROM cases") == []
    assert client.get(f"/v1/approvals/{aid}", headers=headers()).json()["status"] == "approved"


def test_not_found_and_missing_policy(client):
    assert client.get("/v1/approvals/missing", headers=headers()).status_code == 404
    assert decide(client, "missing").status_code == 404
    assert execute(client, "missing").status_code == 404
    for vehicle in ["V-999", "V-102"]:
        if vehicle == "V-102":
            with client.app.state.store.connect(write=True) as con:
                con.execute("DELETE FROM fleet_policies WHERE policy_id='P-MAINT'")
        r = client.post(
            "/v1/actions/propose",
            headers=headers(),
            json={
                "action": "escalation",
                "vehicle_id": vehicle,
                "idempotency_key": "missing-policy-1",
            },
        )
        assert r.status_code == (404 if vehicle == "V-999" else 503)


def test_execution_fault_is_safe(client):
    aid = propose(client)
    assert decide(client, aid).status_code == 200
    r = client.post(
        f"/v1/approvals/{aid}/execute", headers={**headers(), "X-Demo-Fault": "tool_failure"}
    )
    assert r.status_code == 503
    assert client.app.state.store.rows("SELECT * FROM cases") == []
