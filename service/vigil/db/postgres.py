from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
import psycopg2.extras

from vigil.config import settings

_SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def get_connection():
    return psycopg2.connect(settings.postgres_dsn)


@contextmanager
def cursor() -> Iterator[psycopg2.extras.DictCursor]:
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_schema() -> None:
    with open(_SCHEMA_PATH) as f:
        ddl = f.read()
    with cursor() as cur:
        cur.execute(ddl)


def insert_alert(customer_id: str, typology_hint: str, score: float) -> int:
    with cursor() as cur:
        cur.execute(
            """
            INSERT INTO alerts (customer_id, typology_hint, score)
            VALUES (%s, %s, %s)
            RETURNING id
            """,
            (customer_id, typology_hint, score),
        )
        return cur.fetchone()["id"]


def get_alert(alert_id: int) -> dict | None:
    with cursor() as cur:
        cur.execute("SELECT * FROM alerts WHERE id = %s", (alert_id,))
        row = cur.fetchone()
        return dict(row) if row else None


def list_queue(status: str = "OPEN", limit: int = 100) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM alerts WHERE status = %s ORDER BY score DESC LIMIT %s",
            (status, limit),
        )
        return [dict(r) for r in cur.fetchall()]


def list_dispositions(alert_id: int) -> list[dict]:
    with cursor() as cur:
        cur.execute(
            "SELECT * FROM dispositions WHERE alert_id = %s ORDER BY decided_at",
            (alert_id,),
        )
        return [dict(r) for r in cur.fetchall()]


class AlreadyDecidedError(Exception):
    """Raised when a disposition is attempted on an alert that is no longer OPEN."""


def record_disposition(alert_id: int, decision: str, rationale: str, analyst: str) -> dict:
    """
    Atomically flips an alert's status from OPEN to a terminal state and
    appends the audit-trail row, in one transaction. The UPDATE is
    conditioned on `status = 'OPEN'` and we check `cur.rowcount` --
    exactly the same check-and-act-as-one-statement pattern used for
    the governance gate elsewhere in this portfolio, so two analysts
    racing to decide the same alert can't both "win": the second one's
    UPDATE matches zero rows and is told plainly that the alert was
    already decided, instead of silently overwriting the first
    decision or leaving two conflicting disposition rows.
    """
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                UPDATE alerts
                SET status = %s, decided_at = now()
                WHERE id = %s AND status = 'OPEN'
                RETURNING id
                """,
                (decision, alert_id),
            )
            updated = cur.fetchone()
            if updated is None:
                raise AlreadyDecidedError(f"alert {alert_id} is not OPEN (already decided or does not exist)")

            cur.execute(
                """
                INSERT INTO dispositions (alert_id, decision, rationale, analyst)
                VALUES (%s, %s, %s, %s)
                RETURNING *
                """,
                (alert_id, decision, rationale, analyst),
            )
            disposition = dict(cur.fetchone())
        conn.commit()
        return disposition
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
