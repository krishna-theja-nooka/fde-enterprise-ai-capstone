import sqlite3
import time
from datetime import date

import pytest
from fastapi.testclient import TestClient

from fleet.config import Settings
from fleet.main import create_app
from fleet.observability import RateLimiter, summary
from tests.conftest import headers


@pytest.mark.parametrize(
    "settings",
    [
        Settings(keys={}),
        Settings(requests_per_minute=0),
        Settings(keys={"invalid": {"id": "user", "role": "root"}}),
    ],
)
def test_invalid_config_fails_at_startup(settings):
    with pytest.raises(ValueError):
        settings.validate()


def test_tool_deadline_withholds_late_result(client, monkeypatch):
    tools = client.app.state.copilot.tools
    original = tools.counts
    tools.settings.tool_deadline_ms = 1

    def slow():
        time.sleep(0.01)
        return original()

    monkeypatch.setattr(tools, "counts", slow)
    response = client.post("/v1/copilot/ask", headers=headers(), json={"question": "fleet summary"})
    assert response.json()["status"] == "degraded"
    assert response.json()["data"] == {}


def test_audit_storage_failure_is_explicit(client, monkeypatch):
    import fleet.main

    def fail(*args):
        raise sqlite3.OperationalError("audit unavailable")

    monkeypatch.setattr(fleet.main, "save_trace", fail)
    response = client.post("/v1/copilot/ask", headers=headers(), json={"question": "fleet summary"})
    assert response.status_code == 503
    assert response.json()["trace_persisted"] is False


def test_readiness_database_failure(client, monkeypatch):
    def fail(*args):
        raise sqlite3.OperationalError("db unavailable")

    monkeypatch.setattr(client.app.state.store, "rows", fail)
    assert client.get("/ready").status_code == 503


def test_quota_recovers_after_window(monkeypatch):
    import fleet.observability

    clock = [100.0]
    monkeypatch.setattr(fleet.observability.time, "monotonic", lambda: clock[0])
    limiter = RateLimiter(1)
    assert limiter.allow("user")
    assert not limiter.allow("user")
    clock[0] += 61
    assert limiter.allow("user")


def test_empty_metrics_and_low_relevance_policy(tmp_path):
    settings = Settings(db_path=str(tmp_path / "empty.db"), seed_date=date(2026, 10, 7))
    with TestClient(create_app(settings)) as client:
        assert summary(client.app.state.store)["requests"] == 0
        assert (
            client.post(
                "/v1/copilot/ask", headers=headers(), json={"question": "policy qzxw"}
            ).json()["status"]
            == "degraded"
        )
        assert client.get("/v1/cases", headers=headers("approver")).json() == {"cases": []}
