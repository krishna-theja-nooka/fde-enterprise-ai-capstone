# Demo walkthrough

The checked-in MP4 is an actual browser recording of the local synthetic app. It has no narration, generated avatars, or claimed customer deployment.

1. Ask “Why is vehicle V-102 unavailable?” Inspect maintenance evidence and P-SAFETY citation.
2. Ask “Which contracts end in the next 30 days?” Verify four contract records in the snapshot.
3. Propose an escalation for V-102 as `demo-operator`. Note status `pending` and review the policy-cited payload.
4. Attempt execution before approval. The server refuses with HTTP 409; no case is created.
5. Change the key to `demo-approver`; review the proposal and approve it.
6. Change back to `demo-operator`; execute. Inspect the generated case and approval ID.
7. Review action-audit events and trace/metrics endpoints through `/docs`.

The script uses seeded fictional data. Dates follow the fixed demo snapshot; latency and generated IDs vary per recording. For an interview, explain the customer workflow, trust boundaries, fail-closed behavior, and why a recommendation case is different from a real vehicle assignment.

