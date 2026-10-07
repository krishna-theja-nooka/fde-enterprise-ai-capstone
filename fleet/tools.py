import re
import time
from datetime import timedelta


class ToolUnavailable(Exception):
    pass


class Tools:
    """Allowlisted, parameterized SQL. No user-provided SQL is accepted."""

    def __init__(self, store, settings):
        self.store = store
        self.settings = settings

    def call(self, name, operation, context):
        start = time.perf_counter()
        for attempt in range(1, 3):
            try:
                fault = context.get("fault")
                if fault in {"tool_failure", "tool_timeout"} or (
                    fault == "transient_tool" and attempt == 1
                ):
                    raise ToolUnavailable(
                        "tool timeout" if fault == "tool_timeout" else "simulated tool failure"
                    )
                if (time.perf_counter() - start) * 1000 > self.settings.tool_deadline_ms:
                    raise ToolUnavailable("tool deadline exceeded")
                value = operation()
                if (time.perf_counter() - start) * 1000 > self.settings.tool_deadline_ms:
                    raise ToolUnavailable("tool deadline exceeded")
                context["events"].append(
                    {"type": "tool", "name": name, "attempt": attempt, "status": "success"}
                )
                return value
            except ToolUnavailable:
                context["events"].append(
                    {"type": "tool", "name": name, "attempt": attempt, "status": "error"}
                )
                if attempt == 2:
                    raise
                context["retry_count"] += 1
                time.sleep(min(0.005, self.settings.tool_deadline_ms / 1000))
        raise ToolUnavailable("tool unavailable")  # pragma: no cover

    def _rows(self, sql, params=(), con=None):
        if con is not None:
            return [dict(row) for row in con.execute(sql, params).fetchall()]
        return self.store.rows(sql, params)

    def vehicle(self, vehicle_id, con=None):
        if not re.fullmatch(r"V-\d{3}", vehicle_id):
            raise ValueError("Invalid vehicle ID")
        rows = self._rows("SELECT * FROM vehicles WHERE vehicle_id=?", (vehicle_id,), con)
        if not rows:
            return None
        today = self.store.seed_date()
        return {
            "vehicle": rows[0],
            "maintenance": self._rows(
                "SELECT * FROM maintenance_events WHERE vehicle_id=? ORDER BY event_date DESC",
                (vehicle_id,),
                con,
            ),
            "alerts": self._rows(
                "SELECT * FROM telematics_alerts WHERE vehicle_id=? AND resolved=0",
                (vehicle_id,),
                con,
            ),
            "active_contracts": self._rows(
                "SELECT * FROM contracts WHERE vehicle_id=? AND start_date<=? AND end_date>=?",
                (vehicle_id, today.isoformat(), today.isoformat()),
                con,
            ),
        }

    def contracts(self, days):
        if not 1 <= days <= 90:
            raise ValueError("Contract window must be 1 to 90 days")
        today = self.store.seed_date()
        return self._rows(
            "SELECT * FROM contracts WHERE start_date<=? AND end_date BETWEEN ? AND ? "
            "ORDER BY end_date,contract_id LIMIT 100",
            (today.isoformat(), today.isoformat(), (today + timedelta(days=days)).isoformat()),
        )

    def anomalies(self):
        today = self.store.seed_date()
        return self._rows(
            "SELECT v.vehicle_id, v.status, "
            "(SELECT COUNT(*) FROM maintenance_events m WHERE m.vehicle_id=v.vehicle_id "
            "AND m.event_date BETWEEN ? AND ?) AS recent_maintenance_count, "
            "(SELECT COUNT(*) FROM telematics_alerts a WHERE a.vehicle_id=v.vehicle_id "
            "AND a.resolved=0 AND a.severity='critical') AS critical_alert_count "
            "FROM vehicles v WHERE recent_maintenance_count>=3 OR critical_alert_count>0 "
            "ORDER BY v.vehicle_id LIMIT 100",
            ((today - timedelta(days=30)).isoformat(), today.isoformat()),
        )

    def counts(self):
        return self._rows(
            "SELECT status,COUNT(*) AS count FROM vehicles GROUP BY status ORDER BY status"
        )
