import json
import math
import threading
import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

from fleet.db import now


class RateLimiter:
    def __init__(self, limit):
        self.limit = limit
        self.windows = defaultdict(deque)
        self.lock = threading.Lock()

    def allow(self, actor_id):
        current = time.monotonic()
        with self.lock:
            window = self.windows[actor_id]
            while window and window[0] <= current - 60:
                window.popleft()
            if len(window) >= self.limit:
                return False
            window.append(current)
            return True


def save_trace(store, context, path, method, status, latency):
    with store.connect(write=True) as con:
        con.execute(
            "INSERT INTO audit_traces VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                context["trace_id"],
                context.get("actor_id"),
                path,
                method,
                status,
                context.get("outcome", "error" if status >= 400 else "completed"),
                context.get("intent"),
                round(latency, 3),
                context["retry_count"],
                json.dumps(context["events"]),
                now(),
            ),
        )


def summary(store):
    since = (datetime.now(UTC) - timedelta(hours=24)).isoformat()
    rows = store.rows(
        "SELECT http_status,outcome,latency_ms,retry_count FROM audit_traces "
        "WHERE created_at>=? ORDER BY created_at DESC LIMIT 10000",
        (since,),
    )
    n = len(rows)
    latencies = sorted(r["latency_ms"] for r in rows)
    statuses = defaultdict(int)
    for row in rows:
        statuses[row["outcome"]] += 1

    def percentile(p):
        return latencies[max(0, math.ceil(p * n) - 1)] if n else 0

    return {
        "window": "last_24_hours",
        "sample_limit": 10000,
        "sample_capped": n == 10000,
        "requests": n,
        "requests_by_outcome": dict(statuses),
        "p50_latency_ms": percentile(0.5),
        "p95_latency_ms": percentile(0.95),
        "http_error_rate": sum(r["http_status"] >= 400 for r in rows) / n if n else 0,
        "degraded_rate": statuses.get("degraded", 0) / n if n else 0,
        "retry_count": sum(r["retry_count"] for r in rows),
        "provider": "deterministic_local",
        "external_model_calls": 0,
        "estimated_model_cost_usd": 0,
        "cost_scope": "External model cost only; excludes hosting",
    }
