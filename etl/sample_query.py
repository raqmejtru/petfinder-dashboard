# etl/sample_query.py
from __future__ import annotations

import datetime as dt
import re
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.types import DateTime
from sqlalchemy.sql.elements import TextClause
from sqlalchemy.orm import Session
from sqlalchemy.engine import Engine, Connection

from backend.app.db import SessionLocal
from backend.app.pf_client import PetfinderClient


# Portable DDL: works on SQLite (treated as TEXT) and Postgres (true timestamptz)
DDL = """
CREATE TABLE IF NOT EXISTS tmp_animals_sample (
    id                  INTEGER PRIMARY KEY,
    name                TEXT,
    type                TEXT,
    age                 TEXT,
    gender              TEXT,
    status              TEXT,
    org_id              TEXT,
    city                TEXT,
    state               TEXT,
    published_at        TIMESTAMPTZ,
    status_changed_at   TIMESTAMPTZ,
    fetched_at          TIMESTAMPTZ
)
"""


def parse_petfinder_ts(ts: str | None) -> dt.datetime | None:
    """
    Convert a Petfinder API timestamp into a UTC, timezone-aware datetime.

    Normalizes offsets like ``+0000`` -> ``+00:00`` (and any ±HHMM) then returns
    a datetime aware of UTC.

    Args:
        ts: Timestamp string from the API (e.g. "2025-01-12T05:19:52+0000") or None.

    Returns:
        A timezone-aware datetime in UTC, or None.
    """
    if not ts:
        return None
    # Normalize +HHMM/-HHMM at end of string to +HH:MM/-HH:MM
    norm = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", ts.strip())
    dt_obj = dt.datetime.fromisoformat(norm)  # tz-aware
    return dt_obj.astimezone(dt.timezone.utc)


def _row(a: dict[str, Any]) -> dict[str, Any]:
    """
    Transform a Petfinder animal record into a DB-ready row.

    Timestamps are converted to timezone-aware UTC datetimes for insertion
    into TIMESTAMPTZ/DATETIME columns.

    Args:
        a: Raw animal JSON object from the Petfinder API.

    Returns:
        Mapping of column names to values for insertion.
    """
    contact = a.get("contact") or {}
    address = contact.get("address") or {}

    return {
        "id": a["id"],
        "name": a.get("name"),
        "type": a.get("type"),
        "age": a.get("age"),
        "gender": a.get("gender"),
        "status": a.get("status"),
        "org_id": a.get("organization_id"),
        "city": address.get("city"),
        "state": address.get("state"),
        "published_at": parse_petfinder_ts(a.get("published_at")),
        "status_changed_at": parse_petfinder_ts(a.get("status_changed_at")),
        "fetched_at": dt.datetime.now(dt.timezone.utc),
    }


def build_upsert_sql(dialect_name: str) -> str:
    """
    Return an INSERT..ON CONFLICT statement tailored to the DB dialect.

    For Postgres, cast datetime parameters to TIMESTAMPTZ explicitly.
    SQLite path omits casts (SQLite ignores types but round-trips ISO8601).
    """
    if dialect_name == "postgresql":
        return """
        INSERT INTO tmp_animals_sample
        (id, name, type, age, gender, status, org_id, city, state,
         published_at, status_changed_at, fetched_at)
        VALUES
        (:id, :name, :type, :age, :gender, :status, :org_id, :city, :state,
         (:published_at)::timestamptz,
         (:status_changed_at)::timestamptz,
         (:fetched_at)::timestamptz)
        ON CONFLICT (id) DO UPDATE SET
          name=EXCLUDED.name,
          type=EXCLUDED.type,
          age=EXCLUDED.age,
          gender=EXCLUDED.gender,
          status=EXCLUDED.status,
          org_id=EXCLUDED.org_id,
          city=EXCLUDED.city,
          state=EXCLUDED.state,
          published_at=EXCLUDED.published_at,
          status_changed_at=EXCLUDED.status_changed_at,
          fetched_at=EXCLUDED.fetched_at
        """
    # SQLite / others (no casts)
    return """
    INSERT INTO tmp_animals_sample
    (id, name, type, age, gender, status, org_id, city, state,
     published_at, status_changed_at, fetched_at)
    VALUES
    (:id, :name, :type, :age, :gender, :status, :org_id, :city, :state,
     :published_at, :status_changed_at, :fetched_at)
    ON CONFLICT(id) DO UPDATE SET
      name=excluded.name,
      type=excluded.type,
      age=excluded.age,
      gender=excluded.gender,
      status=excluded.status,
      org_id=excluded.org_id,
      city=excluded.city,
      state=excluded.state,
      published_at=excluded.published_at,
      status_changed_at=excluded.status_changed_at,
      fetched_at=excluded.fetched_at
    """


def upsert_stmt_for(db: Session) -> TextClause:
    """Build a typed, dialect-aware UPSERT statement for the current DB session."""
    bind: Engine | Connection = db.get_bind()
    dialect_name = bind.dialect.name
    sql = build_upsert_sql(dialect_name)
    return text(sql).bindparams(
        bindparam("published_at", type_=DateTime(timezone=True)),
        bindparam("status_changed_at", type_=DateTime(timezone=True)),
        bindparam("fetched_at", type_=DateTime(timezone=True)),
    )


def main() -> None:
    """Fetch animals from Petfinder using PARAMS and upsert into tmp_animals_sample."""

    # Query: senior female cats near Austin, TX
    PARAMS: dict[str, Any] = {
        "type": "cat",
        "age": "senior",
        "gender": "female",
        "location": "Austin, TX",
        "distance": 100,  # miles
        "limit": 100,  # per page; Petfinder pagination continues in the client
        "status": "adoptable",
    }

    start = dt.datetime.now(dt.timezone.utc)

    client = PetfinderClient()
    rows: list[dict[str, Any]] = [_row(a) for a in client.iter_animals(**PARAMS)]
    print(f"[etl] fetched={len(rows)} params={PARAMS}")

    if not rows:
        print("[etl] nothing to load; exiting")
        return

    with SessionLocal() as db:
        db.execute(text(DDL))
        stmt = upsert_stmt_for(db)
        # executemany for speed
        db.execute(stmt, rows)
        db.commit()

    dur = (dt.datetime.now(dt.timezone.utc) - start).total_seconds()
    print(f"[etl] loaded={len(rows)} table=tmp_animals_sample in {dur:.2f}s")


if __name__ == "__main__":
    main()
