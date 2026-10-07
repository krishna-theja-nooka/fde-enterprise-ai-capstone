PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS vehicles (
 vehicle_id TEXT PRIMARY KEY, depot TEXT NOT NULL, vehicle_type TEXT NOT NULL,
 status TEXT NOT NULL, odometer_km INTEGER NOT NULL CHECK(odometer_km>=0),
 version INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS contracts (
 contract_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
 customer_name TEXT NOT NULL, start_date TEXT NOT NULL, end_date TEXT NOT NULL,
 monthly_rate_usd INTEGER NOT NULL CHECK(monthly_rate_usd>=0)
);
CREATE TABLE IF NOT EXISTS maintenance_events (
 event_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
 event_date TEXT NOT NULL, category TEXT NOT NULL, severity TEXT NOT NULL,
 state TEXT NOT NULL, description TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS telematics_alerts (
 alert_id TEXT PRIMARY KEY, vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
 event_date TEXT NOT NULL, alert_type TEXT NOT NULL, severity TEXT NOT NULL, resolved INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS fleet_policies (
 policy_id TEXT PRIMARY KEY, title TEXT NOT NULL, section TEXT NOT NULL,
 version TEXT NOT NULL, content TEXT NOT NULL, source TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS approvals (
 approval_id TEXT PRIMARY KEY, requested_by TEXT NOT NULL, idempotency_key TEXT NOT NULL,
 action TEXT NOT NULL, vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id),
 payload_json TEXT NOT NULL, evidence_digest TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','rejected','executed')),
 decided_by TEXT, created_at TEXT NOT NULL, expires_at TEXT NOT NULL,
 UNIQUE(requested_by, idempotency_key)
);
CREATE TABLE IF NOT EXISTS cases (
 case_id TEXT PRIMARY KEY, approval_id TEXT UNIQUE NOT NULL REFERENCES approvals(approval_id),
 vehicle_id TEXT NOT NULL REFERENCES vehicles(vehicle_id), kind TEXT NOT NULL,
 description TEXT NOT NULL, created_by TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_traces (
 trace_id TEXT PRIMARY KEY, actor_id TEXT, path TEXT NOT NULL, method TEXT NOT NULL,
 http_status INTEGER NOT NULL, outcome TEXT NOT NULL, intent TEXT,
 latency_ms REAL NOT NULL, retry_count INTEGER NOT NULL,
 events_json TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS action_audit (
 event_id TEXT PRIMARY KEY, approval_id TEXT NOT NULL REFERENCES approvals(approval_id),
 actor_id TEXT NOT NULL, event TEXT NOT NULL, trace_id TEXT NOT NULL, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS feedback (
 trace_id TEXT NOT NULL REFERENCES audit_traces(trace_id), actor_id TEXT NOT NULL,
 score INTEGER NOT NULL CHECK(score BETWEEN 1 AND 5), PRIMARY KEY(trace_id,actor_id)
);
CREATE INDEX IF NOT EXISTS contracts_end ON contracts(end_date);
CREATE INDEX IF NOT EXISTS maintenance_vehicle ON maintenance_events(vehicle_id,event_date);
CREATE INDEX IF NOT EXISTS traces_created ON audit_traces(created_at);

