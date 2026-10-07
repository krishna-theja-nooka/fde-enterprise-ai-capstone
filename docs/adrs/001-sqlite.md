# ADR-001 — SQLite for the synthetic pilot

**Status:** accepted. A local file removes service setup and paid dependencies while supporting transactions, foreign keys, and concurrency tests. WAL and `BEGIN IMMEDIATE` serialize approved writes. Tradeoff: one-node operation, finite lock waits, no tenant platform or managed failover. Revisit for multiple instances or live fleet integrations.

