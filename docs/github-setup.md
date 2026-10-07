# GitHub setup guide

## Repository title and About

**Repository name:** `fde-enterprise-ai-capstone`

**Product title:** Fleet Intelligence Copilot

**About description:**

> Fleet operations AI capstone with policy citations, safe SQL tools, human approvals, audit traces, and reliability evaluations. Python, FastAPI, SQLite; synthetic data only.

Suggested topics: `python`, `fastapi`, `sqlite`, `rag`, `ai-agents`, `human-in-the-loop`, `llmops`, `observability`, `fleet-management`, `forward-deployed-engineer`, `evaluation`, `portfolio`.

## Upload online

1. Create the repository, extract the ZIP, and open its `fde-enterprise-ai-capstone` folder.
2. Upload the **contents** of that folder so `README.md`, `pyproject.toml`, `fleet`, `tests`, `eval`, `docs`, and `assets` appear at the repository root.
3. Show hidden files in your file manager. Ensure `.gitignore`, `.env.example`, `.dockerignore`, and `.github/workflows/ci.yml` and `release.yml` are included. If the browser omits them, use Add file → Create new file with those exact paths and paste the supplied contents.
4. Commit, open Actions, and review all CI matrix and container-smoke results. Fix any failed step before creating the release.
5. Set About description/topics and pin the repository on your profile. A CI badge is optional; use your actual owner/repository URL if adding one.

## v0.1.0 release

After CI is green, open Releases → Draft a new release. Choose tag `v0.1.0`, target `main`, and title **Fleet Intelligence Copilot v0.1.0**. Paste `docs/release-notes.md` and publish. The tag-push release workflow validates version, tests, and evaluation, then uploads source and JSON assets. It can update an already-created release rather than failing because it exists.

If repository policy prevents Actions from publishing, upload the source ZIP and `docs/evaluation-results.json` manually to the release after confirming validation. A GitHub release is not a cloud deployment. No package publishing is required; the project runs from source or Docker.

## Portfolio description

> Built Fleet Intelligence Copilot, a synthetic fleet operations capstone combining cited policy retrieval, bounded SQL tools, anomaly rules, separate human approvals, and auditable case execution. Added FastAPI interfaces, reliability evaluations, and operational documentation.

Use the measured report to describe test results, and explicitly identify synthetic data and deterministic orchestration in interviews.

