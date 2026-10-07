import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

RESOURCES = Path(__file__).parent


def now():
    return datetime.now(UTC).isoformat()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class Store:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self, write=False):
        con = sqlite3.connect(self.path, timeout=2)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        try:
            if write:
                con.execute("BEGIN IMMEDIATE")
            yield con
            if write:
                con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def initialize(self, seed_date=None):
        with self.connect() as con:
            con.execute("PRAGMA journal_mode=WAL")
            con.executescript((RESOURCES / "data/schema.sql").read_text())
        with self.connect(write=True) as con:
            if con.execute("SELECT 1 FROM metadata WHERE key='seed_date'").fetchone():
                return
            today = seed_date or datetime.now(UTC).date()
            con.execute("INSERT INTO metadata VALUES ('seed_date',?)", (today.isoformat(),))
            seed = json.loads((RESOURCES / "data/seed.json").read_text())
            for v in seed["vehicles"]:
                con.execute("INSERT INTO vehicles VALUES (?,?,?,?,?,1)", tuple(v))
            for c in seed["contracts"]:
                cid, vid, customer, offset, rate = c
                con.execute(
                    "INSERT INTO contracts VALUES (?,?,?,?,?,?)",
                    (
                        cid,
                        vid,
                        customer,
                        (today - timedelta(days=300)).isoformat(),
                        (today + timedelta(days=offset)).isoformat(),
                        rate,
                    ),
                )
            for e in seed["maintenance_events"]:
                eid, vid, offset, category, severity, state, description = e
                con.execute(
                    "INSERT INTO maintenance_events VALUES (?,?,?,?,?,?,?)",
                    (
                        eid,
                        vid,
                        (today + timedelta(days=offset)).isoformat(),
                        category,
                        severity,
                        state,
                        description,
                    ),
                )
            for a in seed["telematics_alerts"]:
                aid, vid, offset, kind, severity, resolved = a
                con.execute(
                    "INSERT INTO telematics_alerts VALUES (?,?,?,?,?,?)",
                    (
                        aid,
                        vid,
                        (today + timedelta(days=offset)).isoformat(),
                        kind,
                        severity,
                        resolved,
                    ),
                )
            for policy in sorted((RESOURCES / "policies").glob("*.md")):
                lines = policy.read_text().strip().splitlines()
                con.execute(
                    "INSERT INTO fleet_policies VALUES (?,?,?,?,?,?)",
                    (
                        lines[1].split(": ")[1],
                        lines[0].removeprefix("# "),
                        lines[2].split(": ")[1],
                        lines[3].split(": ")[1],
                        "\n".join(lines[5:]),
                        "fleet/policies/" + policy.name,
                    ),
                )

    def rows(self, sql, params=()):
        with self.connect() as con:
            return [dict(row) for row in con.execute(sql, params).fetchall()]

    def seed_date(self):
        return date.fromisoformat(
            self.rows("SELECT value FROM metadata WHERE key='seed_date'")[0]["value"]
        )
