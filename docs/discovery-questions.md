# Customer discovery questions

## Workflow and impact

1. Which daily questions cause the most context switching? Walk through the last unavailable-vehicle incident.
2. Who makes the final replacement decision, and what evidence do they require?
3. What counts as an escalation, and when is a support case sufficient?
4. Which actions must never be automated? Are monetary limits or depot-specific controls required?
5. How are bulk actions reviewed today? Would one proposal per vehicle be acceptable for a pilot?

## Data and integrations

6. Which system owns vehicle availability, maintenance clearance, contracts, and telematics events?
7. Are stable vehicle and contract IDs shared across systems? How are duplicates resolved?
8. What freshness guarantees exist? Who owns policy updates and effective dates?
9. Can tools expose read-only scoped APIs instead of direct database access?
10. Does the case system support idempotency and an immutable audit reference?

## Trust and rollout

11. Which identity provider, roles, tenant boundaries, retention rules, and regional restrictions apply?
12. May prompts contain customer details or sensitive location data? Where can model inference run?
13. What response time, availability, and degraded behavior do users require?
14. What representative questions and failure examples can be reviewed as a gold test set?
15. Who will approve a shadow pilot, receive incident reports, and sign off on action execution?

Answers are deliberately unfilled: this repository does not invent a real customer's responses. Scope changes must become documented assumptions, evaluation cases, and approval rules before implementation.

