import json
import os
from dataclasses import dataclass, field
from datetime import date

DEMO_KEYS = {
    "demo-viewer": {"id": "viewer-1", "role": "viewer"},
    "demo-operator": {"id": "operator-1", "role": "operator"},
    "demo-approver": {"id": "approver-1", "role": "approver"},
}


@dataclass
class Settings:
    db_path: str = "runtime/fleet.db"
    demo_mode: bool = True
    keys: dict = field(default_factory=lambda: dict(DEMO_KEYS))
    requests_per_minute: int = 60
    approval_ttl_seconds: int = 900
    tool_deadline_ms: int = 250
    seed_date: date | None = None

    def validate(self):
        if min(self.requests_per_minute, self.approval_ttl_seconds, self.tool_deadline_ms) < 1:
            raise ValueError("Positive operational limits are required")
        if not self.keys:
            raise ValueError("API key configuration is required")
        for key, principal in self.keys.items():
            if (
                not key
                or not principal.get("id")
                or principal.get("role") not in {"viewer", "operator", "approver"}
            ):
                raise ValueError("Invalid API key principal")
        if not self.demo_mode and (
            any(key in DEMO_KEYS or len(key) < 32 for key in self.keys) or self.keys == DEMO_KEYS
        ):
            raise ValueError("Non-demo mode requires random API keys of at least 32 characters")

    @classmethod
    def from_env(cls):
        demo = os.getenv("FLEET_DEMO_MODE", "true").lower() == "true"
        key_json = os.getenv("FLEET_API_KEYS")
        return cls(
            db_path=os.getenv("FLEET_DB_PATH", "runtime/fleet.db"),
            demo_mode=demo,
            keys=json.loads(key_json) if key_json else (dict(DEMO_KEYS) if demo else {}),
            requests_per_minute=int(os.getenv("FLEET_REQUESTS_PER_MINUTE", "60")),
            approval_ttl_seconds=int(os.getenv("FLEET_APPROVAL_TTL_SECONDS", "900")),
            tool_deadline_ms=int(os.getenv("FLEET_TOOL_DEADLINE_MS", "250")),
            seed_date=date.fromisoformat(os.environ["FLEET_SEED_DATE"])
            if os.getenv("FLEET_SEED_DATE")
            else None,
        )
