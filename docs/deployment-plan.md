# Deployment plan

## Local / Docker pilot

Run the README's Python commands with one worker and localhost binding. `.env.example` is a reference, not an automatic configuration loader. The first startup initializes schema and seed data; later startups preserve approvals, cases, and the original snapshot date.

For Docker, `docker compose up --build` publishes `127.0.0.1:8000`. The process runs as a non-root user and stores SQLite in the `fleet-data` named volume. `/ready` checks DB read/write access and policy completeness. Do not remove the volume to solve a problem without preserving audit records.

The local verification environment does not include a Docker daemon or Python 3.11. CI has explicit container-build/smoke and Python 3.11/3.12 jobs. Their results are not claimed until GitHub executes them. Python 3.12 installation, tests, evaluation, and the live UI recording are verified locally.

## Rollout stages

1. **Shadow:** read-only synthetic data, operator feedback, and independently authored task cases.
2. **Customer read pilot:** approved data connectors and SSO; no writes; compare answers against source-system records.
3. **Approval pilot:** sandbox case connector, dual identities, audit export, idempotency, and reconciliation of uncertain results.
4. **Controlled live actions:** separate business sign-off, scoped service account, live monitoring, recovery tests, and an on-call owner.

Cloud hosting is a future design, not a completed deployment. A single node with a persistent volume can retain SQLite for a small pilot. Before multiple instances, migrate transactional state to PostgreSQL, rate limits to a shared backend, and traces to an operational store. Use managed identity and scoped network egress for enterprise systems.

## Backup and recovery

Use SQLite's online backup API for a consistent backup of a live database. Copying only the main `.db` file while WAL is active is not a complete backup. Stop writes, verify the backup using `PRAGMA integrity_check`, and test restoring into a new path before changing the service configuration. Keep backup permissions restricted and retention approved.

On application rollback, retain the existing volume and verify schema compatibility before using an older image. This v0.1.0 schema has no migration framework; future changes require numbered migrations, an upgrade test, and a restore plan. Do not roll back database contents after executing an external action without reconciliation.

## Release acceptance

Ruff, tests, coverage threshold, evaluation targets, container smoke, and manual walkthrough must pass. Verify version/tag consistency. Create tag `v0.1.0`, publish notes, and attach the source ZIP and measured JSON. The release workflow validates the tag before publishing or updating existing release assets. The offline repository includes release files and instructions; publishing is performed in the user's GitHub account.

References: [FastAPI Docker deployment](https://fastapi.tiangolo.com/deployment/docker/), [Python SQLite documentation](https://docs.python.org/3/library/sqlite3.html).

