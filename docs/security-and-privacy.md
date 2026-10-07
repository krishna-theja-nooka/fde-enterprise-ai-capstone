# Security and privacy

## Enforced controls

User identity and role are resolved from server-configured keys; requests cannot assert a role. Viewers cannot propose or execute. Approvers cannot execute another user's proposal. The proposing user cannot approve their own action even if they hold another key mapped to the approver role. Non-approvers see only their own approvals, cases, and traces. Feedback belongs to the original request owner.

Only named read tools execute SQL, with placeholders for variable values. The copilot does not accept SQL strings, arbitrary tool names, URLs, shell commands, uploaded policies, or action payload text. Pydantic rejects extra fields. Output rendering uses `textContent`, not untrusted `innerHTML`.

All three write-action types require an independently approved proposal. Evidence is checked under a write lock; policy or fleet changes invalidate approval. Execution is atomic and idempotent. A model cannot bypass these checks because they are enforced by the action service independently of orchestration.

## Demo and non-demo modes

Public `demo-*` keys are intentionally included for localhost demonstrations and screen recordings. They provide no meaningful identity verification on a shared service. Do not expose demo mode publicly.

Non-demo startup requires a nonempty `FLEET_API_KEYS` JSON mapping with keys at least 32 characters long; built-in demo keys are rejected. Use separate random secrets and distinct user IDs. `X-Demo-Fault` is rejected in this mode. A length check alone does not prove randomness; generate and rotate secrets through the deployment secret manager. SSO, expiry, revocation, and multi-tenant authorization remain future work.

## Data handling

The fixture contains no VINs, addresses, real names, GPS locations, or customer identifiers. Application traces retain actor IDs, route templates, statuses, policy IDs, and tool names, omitting raw question bodies, credentials, and generated answers. Proposed descriptions are generated from fixed templates rather than user text. Feedback stores scores only. Reverse proxies and infrastructure may log more; configure them separately.

For a real engagement, obtain approved retention periods, consent, regional storage requirements, and a deletion process before ingestion. Restrict filesystem and backup access, encrypt volumes and transport, and export audits to a tamper-evident backend. No retention deletion endpoint is provided by this demo; operators cannot delete audit records through the API.

## Threat model and limits

Keyword screening blocks known unsafe prompts but is not robust semantic moderation. Safety does not depend on exhaustive keyword detection: unknown inputs cannot introduce a new SQL query or write operation. Policy files and database administrators remain trusted. Local SQLite audits can be edited by a privileged administrator. This is a single fictional tenant, not a claim of enterprise tenant isolation.

Before shared deployment: add TLS/SSO, role lifecycle management, tenant scoping, HTTP body limits at the ingress, distributed quotas, dependency scanning, immutable audits, approved connectors, and review of model data flow. Pin reviewed action revisions and container digests for hardened releases. The included workflows use maintained major action references for a portfolio demo.

