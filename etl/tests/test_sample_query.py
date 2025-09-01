# etl/tests/test_sample_query.py
import copy
import datetime as dt
from typing import Any
from collections.abc import Iterator
import pytest

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from etl.sample_query import _row, DDL, upsert_stmt_for
from etl.tests.sample_animals import sample_animals


def as_utc_dt(value: Any) -> dt.datetime:
    """
    Coerce DB-returned timestamp into a tz-aware UTC datetime.
    - SQLite may return strings like 'YYYY-MM-DD HH:MM:SS(.ffffff)'
    - Postgres returns tz-aware datetimes
    """
    if isinstance(value, dt.datetime):
        # ensure UTC awareness
        return value if value.tzinfo else value.replace(tzinfo=dt.timezone.utc)
    if isinstance(value, str):
        s = value.strip()
        # add a 'T' to satisfy fromisoformat if needed
        if "T" not in s and " " in s:
            s = s.replace(" ", "T", 1)
        # add +00:00 if no offset present
        if s[-6] not in "+-" and not s.endswith("Z"):
            s = s + "+00:00"
        return dt.datetime.fromisoformat(s).astimezone(dt.timezone.utc)
    raise TypeError(f"Unexpected timestamp type: {type(value)}")


@pytest.fixture
def in_memory_db() -> Iterator[Session]:
    engine = create_engine("sqlite:///:memory:", future=True)
    SessionLocal = sessionmaker(bind=engine, future=True)
    with SessionLocal() as session:
        session.execute(text(DDL))
        yield session


def test_insert_sample_animals(in_memory_db: Session) -> None:
    """Smoke: insert all fixtures, verify count and UTC-aware datetimes."""
    stmt = upsert_stmt_for(in_memory_db)
    for a in sample_animals:
        in_memory_db.execute(stmt, _row(a))
    in_memory_db.commit()

    rows = in_memory_db.execute(
        text("SELECT id, name, published_at FROM tmp_animals_sample ORDER BY id")
    ).fetchall()

    assert len(rows) == len(sample_animals)
    for r in rows:
        # SQLite returns tuples by default: (id, name, published_at)
        pub = as_utc_dt(r.published_at if hasattr(r, "published_at") else r[2])
        assert isinstance(pub, dt.datetime)
        assert pub.tzinfo == dt.timezone.utc

    # Check a known row (Shelina)
    shelina = next(r for r in rows if (r.id if hasattr(r, "id") else r[0]) == 77813886)
    s_pub = as_utc_dt(shelina.published_at if hasattr(shelina, "published_at") else shelina[2])
    assert s_pub == dt.datetime(2025, 8, 16, 12, 28, 2, tzinfo=dt.timezone.utc)


def test_upsert_updates_existing_rows(in_memory_db: Session) -> None:
    """
    Inserting again with the same ID but different values should UPDATE the row,
    not create a duplicate.
    """
    stmt = upsert_stmt_for(in_memory_db)

    # 1) Initial load
    for a in sample_animals:
        in_memory_db.execute(stmt, _row(a))
    in_memory_db.commit()

    # Baseline counts
    before_count = in_memory_db.execute(
        text("SELECT COUNT(*) FROM tmp_animals_sample")
    ).scalar_one()

    # 2) Modify one record (same id) and upsert again
    modified = copy.deepcopy(sample_animals)
    # Pick Shelina (id=77813886): change status + published_at
    for rec in modified:
        if rec["id"] == 77813886:
            rec["status"] = "adopted"
            rec["published_at"] = "2025-08-17T00:00:00+0000"  # next day UTC
            rec["name"] = "Shelina (Updated)"
            break

    for a in modified:
        in_memory_db.execute(stmt, _row(a))
    in_memory_db.commit()

    # 3) Assert row count unchanged (no duplicate IDs)
    after_count = in_memory_db.execute(text("SELECT COUNT(*) FROM tmp_animals_sample")).scalar_one()
    assert after_count == before_count

    # 4) Assert the targeted row was actually updated
    row = (
        in_memory_db.execute(
            text(
                """
            SELECT id, name, status, published_at
            FROM tmp_animals_sample
            WHERE id = :id
        """
            ),
            {"id": 77813886},
        )
        .mappings()
        .one()
    )

    assert row["name"] == "Shelina (Updated)"
    assert row["status"] == "adopted"
    assert as_utc_dt(row["published_at"]) == dt.datetime(2025, 8, 17, 0, 0, tzinfo=dt.timezone.utc)
