# API specification

Interactive OpenAPI is available at `/docs`; machine-readable schema is `/openapi.json`. `/health`, `/ready`, and the dashboard are public; `/v1/` endpoints require `X-API-Key`.

The repository also includes [a captured OpenAPI schema](openapi.json) and [actual synthetic request/response examples](demo-api-responses.json), including a rejected pre-approval execution and successful approved case creation.

| Method | Path | Permission / result |
| --- | --- | --- |
| GET | `/health` | Liveness; version and demo flag |
| GET | `/ready` | DB read/write probe and required policy count; 503 when unavailable |
| POST | `/v1/copilot/ask` | All roles; answer, clarification, blocked, or degraded result |
| POST | `/v1/actions/propose` | Operator; pending proposal with cited evidence |
| GET | `/v1/approvals/{approval_id}` | Owner or approver; full proposed payload |
| POST | `/v1/approvals/{approval_id}/decision` | Different approver; approve/reject a live proposal |
| POST | `/v1/approvals/{approval_id}/execute` | Proposing operator; creates one approved case |
| GET | `/v1/cases` | Own cases; approvers see most recent 100 across users |
| GET | `/v1/policies/{policy_id}` | All roles; original cited policy content |
| GET | `/v1/traces/{trace_id}` | Owner or approver; metadata and tool events |
| GET | `/v1/audit/actions/{approval_id}` | Owner or approver; proposal/decision/execution ledger |
| GET | `/v1/metrics/summary` | Approver; rolling latency, retries, errors, and outcomes |
| POST | `/v1/feedback` | Request owner; score 1–5, upsert per trace/user |

## Ask

```json
{"question":"Why is vehicle V-102 unavailable?"}
```

The response has `trace_id`, `intent`, `risk`, `status`, `answer`, `data`, `citations`, `suggested_action`, and `warnings`. A citation contains `policy_id`, `title`, `section`, `version`, `excerpt`, and repository-relative `source`. V-102 returns the recorded brake safety hold; trace IDs vary per request. Questions have a 1,000-character limit. Extra request fields are rejected.

## Full approved action

```bash
# 1. Operator proposes; copy approval_id from the response.
curl http://127.0.0.1:8000/v1/actions/propose \
  -H 'X-API-Key: demo-operator' -H 'Content-Type: application/json' \
  -d '{"action":"replacement_recommendation","vehicle_id":"V-102","idempotency_key":"replacement-demo-001"}'

# 2. Different approver reads the exact payload before deciding.
curl http://127.0.0.1:8000/v1/approvals/APPROVAL_ID -H 'X-API-Key: demo-approver'
curl http://127.0.0.1:8000/v1/approvals/APPROVAL_ID/decision \
  -H 'X-API-Key: demo-approver' -H 'Content-Type: application/json' -d '{"decision":"approve"}'

# 3. Original operator executes. Repeating this returns the same case.
curl -X POST http://127.0.0.1:8000/v1/approvals/APPROVAL_ID/execute -H 'X-API-Key: demo-operator'
```

`APPROVAL_ID` is a placeholder; replace it with the actual ID. Proposal responses include `approval_id`, `requested_by`, `action`, `vehicle_id`, `status`, `decided_by`, creation/expiry timestamps, and `payload` containing the generated case description and policy citation. The UI exposes no editable case payload after proposal creation.

Execution returns `case_id`, `approval_id`, `vehicle_id`, `kind`, `description`, `created_by`, and `created_at`. No real assignment, notification, or contract change occurs.

## Error and fallback contract

- 401: missing/invalid API key; 403: role, ownership, self-approval, or non-demo fault violation.
- 404: unknown record; 409: ineligible vehicle, expired/stale/undecided/rejected approval, or idempotency conflict.
- 422: invalid body, ID shape, unknown extra field, or unknown demo fault.
- 429: per-principal quota exhausted; retry after 60 seconds.
- 503: unavailable storage/tool or fail-closed action evidence.
- An ask request can return HTTP 200 with `status=degraded`, empty evidence and citations, and an explicit error explanation. Business outcome must be checked separately from HTTP status.
- Fault details and exception internals are not returned. `X-Trace-ID` correlates all responses; durable traces depend on audit storage availability.

