# Evaluation report — v0.1.0

## Measured local results

Recorded on 2026-10-07 with Python 3.12.14, a fresh pinned-dependency environment, SQLite, and deterministic orchestration. The fixed synthetic data snapshot is 2026-10-07. The JSON result in `evaluation-results.json` is the committed measurement; reruns produce different timings and trace IDs.

| Metric | Target | Actual | Evidence scope |
| --- | --- | --- | --- |
| Task success | ≥90% | 100% | 34/34 independently authored cases |
| Policy citation coverage | 100% | 100% | 15/15 policy-bearing ask cases; required policy present and excerpts source-matched |
| High-impact approval gate | 100% | 100% | 3/3 action types blocked before approval; operator decision forbidden |
| Durable trace coverage | ≥95% | 100% | 49/49 completed business API calls in the evaluator |
| Local p95 full-case latency | <1,000 ms regression budget | 23.095 ms | Nearest rank over 34 cases, including approval workflows |
| Automated tests | All pass | 60 passed | Unit/API/workflow/fault/concurrency/evaluation tests |
| Statement coverage | ≥85% CI gate | 98.36% | 659/670 executable statements under pytest; evaluator CLI entry not included |
| Ruff lint and format | Pass | Passed | Checked in the fresh environment |

Tool accuracy cases compare manually selected vehicle/contract IDs and maintenance counts against API results. Approval workflow cases verify an empty case state before approval, different-role decisions, approved execution, and replay identity. Unit tests extend this to stale evidence in four source types, rejection, expiry, self-approval across two keys, cross-user access, concurrent execution, and atomic rollback when the action ledger fails.

## Test groups

The 34-case suite includes normal vehicle explanations, contract-date boundaries, policy retrieval, fleet counts, anomalies, and action recommendations; ambiguous/bulk/unknown questions; unsafe prompts; transient retry; timeout, persistent tool, and retrieval failure; and three complete high-impact approval workflows. Expected outcomes are checked into `eval/suite.jsonl`, not generated from the answers under test.

The negative evaluator test deliberately changes expected outcomes and confirms that the aggregate fails. A quota recovery test checks the sliding window. Tool deadlines, audit-storage failure, and readiness failure produce explicit fallback/error behavior.

## Reproduce

```bash
python -m pip install -r requirements-dev.lock
python -m pip install --no-deps --no-build-isolation -e .
python -m ruff check .
python -m ruff format --check .
python -m pytest
python -m fleet.evaluate --output reports/evaluation.json
```

Evaluation uses a fresh temporary database and cannot overwrite your demo database. The CLI returns exit code 1 when an aggregate target fails. CI uploads measured JSON and coverage for each Python matrix version. Committed baseline results are not a claim that GitHub CI has already run in your account.

## Limits

Citation tests verify that a required policy is cited and each excerpt matches the source. They do not measure semantic entailment, general natural-language groundedness, or model quality. The suite tests a known deterministic intent grammar and a small controlled corpus. Unknown phrasing can require clarification. A 100% synthetic pass rate does not establish real customer task success.

Approval coverage samples all three implemented action types, supported by negative tests; it does not prove a future connector has safe external side effects. Trace coverage excludes health/static/docs calls and database-outage requests, which explicitly report unavailable audit storage. There is no load, penetration, chaos-at-scale, or live customer study.

Python 3.12, dependency installation, wheel contents, local API behavior, and the real browser demo are checked locally. Python 3.11 and Docker execution are not locally available; included CI jobs are the validation path. No cloud deployment, GitHub publication, or release publication is claimed.

The pinned Starlette/httpx test client emits a deprecation warning while remaining functional. It does not fail these tests; a future dependency refresh should validate the recommended client migration in both Python versions. External model API cost is zero; hosting/compute cost is outside that measurement.
