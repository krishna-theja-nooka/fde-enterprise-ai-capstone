# Assumptions and scope

- All seed records and policy documents are fictional and checked into the repository.
- The seed contains 12 vehicles, 8 contracts, 10 maintenance events, 5 telematics alerts, and 4 policy documents. Cases, approvals, feedback, and audit records start empty.
- Contract and event dates are offsets from the UTC seed date. The snapshot date is persisted, not advanced every day. Evaluation always seeds 2026-10-07. Reset only an expendable local demo database to generate a new snapshot; do not reset a database containing valuable audit records.
- Intent selection, SQL tools, anomaly rules, and recommendations are deterministic. No paid or open-weight language model is used. Hugging Face is a possible future adapter, not an installed dependency.
- Policy retrieval uses lexical token overlap with mandatory policy selection for sensitive workflows. Trusted files are ingested once during initialization. There is no public document-upload endpoint.
- All action types require approval, even the lower-impact support-case path. The replacement action creates a recommendation case only.
- A proposal is limited to one vehicle. The system asks for clarification instead of bulk execution.
- A single SQLite file and one application process serve the local demo. This does not establish multi-tenant or distributed operation.
- Roles are server-side API-key mappings. Public demo credentials are allowed only for isolated local testing.
- Read tools retry a simulated transient failure once. Degraded responses contain no unverified recommendation. External model cost is zero; compute and hosting costs are not zero by implication.
- Fleet data is read-only through the API. Case execution modifies only cases, approvals, and their audit ledger within one transaction.

