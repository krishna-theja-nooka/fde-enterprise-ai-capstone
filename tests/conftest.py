from datetime import date

import pytest
from fastapi.testclient import TestClient

from fleet.config import Settings
from fleet.main import create_app


@pytest.fixture
def client(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "fleet.db"), seed_date=date(2026, 10, 7), requests_per_minute=10000
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def headers(role="operator"):
    return {"X-API-Key": "demo-" + role}


def propose(client, action="escalation", vehicle="V-102", key="test-action-001"):
    response = client.post(
        "/v1/actions/propose",
        headers=headers(),
        json={
            "action": action,
            "vehicle_id": vehicle,
            "idempotency_key": key,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()["approval_id"]


def decide(client, aid, decision="approve"):
    return client.post(
        f"/v1/approvals/{aid}/decision", headers=headers("approver"), json={"decision": decision}
    )


def execute(client, aid):
    return client.post(f"/v1/approvals/{aid}/execute", headers=headers())
