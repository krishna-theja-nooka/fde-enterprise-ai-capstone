import json
from pathlib import Path

from fleet.evaluate import run


def test_regression_targets():
    report = run("eval/suite.jsonl")
    assert report["passed"], report["results"]
    assert report["metrics"]["approval_gate_rate"] == 1
    assert report["metrics"]["policy_citation_rate"] == 1
    assert report["metrics"]["trace_coverage"] >= 0.95
    assert report["metrics"]["task_success_rate"] >= 0.90
    # Local demo budget, not a production latency promise.
    assert report["metrics"]["p95_case_latency_ms"] < 1000


def test_evaluation_detects_wrong_expectation(tmp_path):
    suite = [json.loads(line) for line in Path("eval/suite.jsonl").read_text().splitlines()]
    for case in suite:
        if case.get("mode") != "workflow":
            case["status"] = "deliberately_wrong"
    path = tmp_path / "wrong.jsonl"
    path.write_text("\n".join(json.dumps(c) for c in suite))
    assert run(path)["passed"] is False
