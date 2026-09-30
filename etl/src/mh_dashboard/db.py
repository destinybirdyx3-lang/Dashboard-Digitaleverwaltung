"""Datenbankzugriff: Verbindung, Migrationen, ETL-Läufe und Rohdaten."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

RAW_RETENTION_DAYS = 30


def connect(database_url: str) -> psycopg.Connection:
    return psycopg.connect(database_url, autocommit=False)


def migrate(conn: psycopg.Connection) -> list[str]:
    """Wendet alle SQL-Migrationen aus ``mh_dashboard/sql`` in Reihenfolge an (idempotent)."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS public.schema_migration (name text PRIMARY KEY, "
        "angewendet_am timestamptz NOT NULL DEFAULT now())"
    )
    done = {row[0] for row in conn.execute("SELECT name FROM public.schema_migration")}
    applied = []
    files = sorted(p for p in resources.files("mh_dashboard.sql").iterdir() if p.name.endswith(".sql"))
    for path in files:
        if path.name in done:
            continue
        conn.execute(path.read_text(encoding="utf-8"))
        conn.execute("INSERT INTO public.schema_migration (name) VALUES (%s)", (path.name,))
        applied.append(path.name)
    conn.commit()
    return applied


@contextmanager
def etl_lauf(conn: psycopg.Connection, quelle: str) -> Iterator[uuid.UUID]:
    """Protokolliert einen Lauf. Bei Fehlern wird zurückgerollt und der Fehler vermerkt."""
    lauf_id = uuid.uuid4()
    conn.execute("INSERT INTO raw.etl_lauf (lauf_id, quelle) VALUES (%s, %s)", (lauf_id, quelle))
    conn.commit()
    try:
        yield lauf_id
    except BaseException as exc:
        conn.rollback()
        conn.execute(
            "UPDATE raw.etl_lauf SET status='fehler', beendet=now(), fehler=%s WHERE lauf_id=%s",
            (f"{type(exc).__name__}: {exc}"[:2000], lauf_id),
        )
        conn.commit()
        raise
    else:
        conn.execute("UPDATE raw.etl_lauf SET status='ok', beendet=now() WHERE lauf_id=%s", (lauf_id,))
        conn.commit()


def store_raw(
    conn: psycopg.Connection, lauf_id: uuid.UUID, quelle: str, endpunkt: str, parameter: dict[str, Any], inhalt: Any
) -> None:
    text = json.dumps(inhalt, ensure_ascii=False, sort_keys=True, default=str)
    conn.execute(
        "INSERT INTO raw.api_response (lauf_id, quelle, endpunkt, parameter, inhalt_sha256, inhalt) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (
            lauf_id,
            quelle,
            endpunkt,
            Jsonb(parameter),
            hashlib.sha256(text.encode()).hexdigest(),
            Jsonb(json.loads(text)),
        ),
    )


def purge_raw(conn: psycopg.Connection) -> int:
    cur = conn.execute(
        "DELETE FROM raw.api_response WHERE abgerufen_am < now() - %s * interval '1 day'", (RAW_RETENTION_DAYS,)
    )
    conn.commit()
    return cur.rowcount


def set_quelle_stand(
    conn: psycopg.Connection, quelle: str, datensaetze: int, datenstand_extern: Any = None, demo: bool = False
) -> None:
    conn.execute(
        "INSERT INTO raw.quelle_stand (quelle, stand, datenstand_extern, datensaetze, demo) "
        "VALUES (%s, now(), %s, %s, %s) ON CONFLICT (quelle) DO UPDATE SET stand=excluded.stand, "
        "datenstand_extern=excluded.datenstand_extern, datensaetze=excluded.datensaetze, demo=excluded.demo",
        (quelle, datenstand_extern, datensaetze, demo),
    )


def previous_count(conn: psycopg.Connection, quelle: str) -> int | None:
    row = conn.execute("SELECT datensaetze FROM raw.quelle_stand WHERE quelle=%s", (quelle,)).fetchone()
    return row[0] if row else None
