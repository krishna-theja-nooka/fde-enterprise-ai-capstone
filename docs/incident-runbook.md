# Incident runbook

| Symptom | Investigate | Immediate response | Recovery check |
| --- | --- | --- | --- |
| Policy retrieval unavailable | Trace retrieval event, required policy row, `/ready` policy count | Withhold recommendation; block proposals without required policy | Restore trusted policy and version; create a new proposal; run citation evaluation |
| Read tool failure | Trace tool name, attempt status, retry count; DB permissions and readiness | Return degraded evidence-free answer; do not substitute guessed data | Verify bounded tool lookup and fault regression |
| Action result uncertain | Approval status, case unique approval ID, action ledger, trace persistence flag | Inspect state before retry; never create a fresh proposal blindly | Replay same approval; confirm one case and one execution event |
| Unsafe request | Trace blocked outcome; role and approval-gate tests | Reject known unsafe request; no SQL/write access outside allowlist | Confirm no new case and no unauthorized approval |
| High latency | p95 window/sample cap, request route, DB locks and trace counts | Limit concurrency; keep one worker; withhold late tool results | Check lock contention, tool budget, and local regression target |
| Rate limit exceeded | 429 and Retry-After, principal ID, client retry pattern | Wait for the 60-second sliding window; prevent retry storms | Request succeeds after window; check quota test |
| Readiness fails | SQLite access, write probe, policy rows, WAL/disk space | Stop routing business traffic; preserve DB and backups | `/ready` returns 200 and evaluation passes |
| Approval rejected/expired/stale | Exact approval status, expiry UTC timestamp, changed evidence | No execution; re-propose with new evidence and a new idempotency key | Different approver reviews new snapshot |

## Triage procedure

Capture the `X-Trace-ID`, timestamp, route, business status, and affected vehicle ID. Use an approver account to inspect cross-user traces and metrics. Never copy API keys or raw customer prompts into an incident report. Confirm whether a case was actually committed before retrying an action.

The read-tool deadline rejects late results but does not forcibly cancel SQLite execution. Connection lock waits can last up to two seconds. A future network connector must implement real transport deadlines and idempotent reconciliation, not just elapsed-time checks.

## Demo drills

In demo mode, add `X-Demo-Fault: transient_tool`, `tool_failure`, `tool_timeout`, or `retrieval_failure` to an ask request. Tests cover these outcomes, stale/expired/rejected approvals, concurrency replay, and action-ledger rollback. Fault injection is unavailable outside demo mode.

## Incident report template

Record impact, detection time, trace/approval/case references, current state, verified cause, mitigation, restoration check, and a regression case. Separate observed facts from hypotheses. This repository contains no fabricated real-world incident report.

