"""Offline regression evaluator using independent, manually authored expectations."""

import argparse
import json
import math
import platform
import tempfile
import time
from datetime import date
from pathlib import Path

from fastapi.testclient import TestClient

from fleet.config import Settings
from fleet.main import create_app


def run(suite_path):
    suite = [json.loads(line) for line in Path(suite_path).read_text().splitlines() if line.strip()]
    results = []
    citation_checks = []
    approval_checks = []
    traces = []
    latencies = []
    with tempfile.TemporaryDirectory() as directory:
        settings = Settings(
            db_path=str(Path(directory) / "evaluation.db"),
            seed_date=date(2026, 10, 7),
            requests_per_minute=10000,
        )
        with TestClient(create_app(settings)) as client:
            for case in suite:
                started = time.perf_counter()
                checks = {}
                headers = {"X-API-Key": "demo-operator"}
                if case.get("fault"):
                    headers["X-Demo-Fault"] = case["fault"]
                if case.get("mode") == "workflow":
                    response = client.post(
                        "/v1/actions/propose",
                        headers=headers,
                        json={
                            "action": case["action"],
                            "vehicle_id": case["vehicle_id"],
                            "idempotency_key": case["id"],
                        },
                    )
                    checks["proposal_created"] = response.status_code == 200
                    if response.status_code == 200:
                        aid = response.json()["approval_id"]
                        path = f"/v1/approvals/{aid}"
                        before = client.post(path + "/execute", headers=headers)
                        self_decision = client.post(
                            path + "/decision", headers=headers, json={"decision": "approve"}
                        )
                        checks["approval_gate"] = (
                            before.status_code == 409
                            and self_decision.status_code == 403
                            and not client.app.state.store.rows(
                                "SELECT * FROM cases WHERE approval_id=?", (aid,)
                            )
                        )
                        approval_checks.append(checks["approval_gate"])
                        decision = client.post(
                            path + "/decision",
                            headers={"X-API-Key": "demo-approver"},
                            json={"decision": "approve"},
                        )
                        executed = client.post(path + "/execute", headers=headers)
                        replayed = client.post(path + "/execute", headers=headers)
                        checks["approved_execution"] = (
                            decision.status_code
                            == executed.status_code
                            == replayed.status_code
                            == 200
                            and executed.json()["case_id"] == replayed.json()["case_id"]
                        )
                        for r in (response, before, self_decision, decision, executed, replayed):
                            tid = r.headers.get("X-Trace-ID")
                            traces.append(
                                bool(
                                    client.app.state.store.rows(
                                        "SELECT trace_id FROM audit_traces WHERE trace_id=?", (tid,)
                                    )
                                )
                            )
                else:
                    response = client.post(
                        "/v1/copilot/ask", headers=headers, json={"question": case["question"]}
                    )
                    checks["http_status"] = response.status_code == 200
                    value = response.json()
                    checks["status"] = value.get("status") == case["status"]
                    if "intent" in case:
                        checks["intent"] = value.get("intent") == case["intent"]
                    if "contains" in case:
                        checks["grounded_answer"] = case["contains"] in value.get("answer", "")
                    if "expected_ids" in case:
                        rows = value.get("data", {}).get(case["data_field"], [])
                        checks["tool_accuracy"] = [r[case["id_field"]] for r in rows] == case[
                            "expected_ids"
                        ]
                    if "citation" in case:
                        citations = value.get("citations", [])
                        checks["citations"] = case["citation"] in {
                            c["policy_id"] for c in citations
                        }
                        checks["citation_source_match"] = all(
                            client.app.state.store.rows(
                                "SELECT content FROM fleet_policies WHERE policy_id=?",
                                (c["policy_id"],),
                            )[0]["content"]
                            == c["excerpt"]
                            for c in citations
                        )
                        citation_checks.append(
                            checks["citations"] and checks["citation_source_match"]
                        )
                    if case["status"] in {"degraded", "blocked", "needs_clarification"}:
                        checks["no_action"] = value.get("suggested_action") is None
                    tid = response.headers.get("X-Trace-ID")
                    traces.append(
                        bool(
                            client.app.state.store.rows(
                                "SELECT trace_id FROM audit_traces WHERE trace_id=?", (tid,)
                            )
                        )
                    )
                latencies.append((time.perf_counter() - started) * 1000)
                results.append(
                    {
                        "id": case["id"],
                        "passed": all(checks.values()),
                        "checks": checks,
                        "latency_ms": round(latencies[-1], 3),
                    }
                )

    def rate(values):
        return sum(values) / len(values) if values else 0

    task_rate = rate([r["passed"] for r in results])
    metrics = {
        "task_success_rate": task_rate,
        "policy_citation_rate": rate(citation_checks),
        "approval_gate_rate": rate(approval_checks),
        "trace_coverage": rate(traces),
        "p95_case_latency_ms": round(sorted(latencies)[math.ceil(len(latencies) * 0.95) - 1], 3),
        "cases": len(results),
        "policy_cases": len(citation_checks),
        "high_impact_workflows": len(approval_checks),
        "completed_api_requests": len(traces),
    }
    passed = (
        task_rate >= 0.9
        and metrics["policy_citation_rate"] == 1
        and metrics["approval_gate_rate"] == 1
        and metrics["trace_coverage"] >= 0.95
    )
    return {
        "passed": passed,
        "metrics": metrics,
        "results": results,
        "environment": {
            "python": platform.python_version(),
            "data_as_of": "2026-10-07",
            "provider": "deterministic_local",
        },
        "limitations": "Synthetic, rule-based tasks. Citation checks validate source matching; "
        "they do not establish semantic entailment for arbitrary questions. "
        "Latency covers full cases, including approval workflows, on this machine.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="eval/suite.jsonl")
    parser.add_argument("--output", default="reports/evaluation.json")
    args = parser.parse_args()
    report = run(args.suite)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "metrics": report["metrics"]}, indent=2))
    raise SystemExit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
