from __future__ import annotations

import os
import uuid
from pathlib import Path

import psycopg
import pytest

REPO = Path(__file__).resolve().parents[2]
QUERY_DIR = REPO / "integration" / "optigov" / "queries"


@pytest.fixture
def query_dir() -> Path:
    return QUERY_DIR


@pytest.fixture
def database_url() -> str:
    """Eigene Test-Datenbank je Test; benötigt MH_TEST_DATABASE_URL (Admin-Verbindung)."""
    admin_url = os.environ.get("MH_TEST_DATABASE_URL")
    if not admin_url:
        pytest.skip("MH_TEST_DATABASE_URL nicht gesetzt – Integrationstest übersprungen")
    name = f"mh_test_{uuid.uuid4().hex[:10]}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    base, _, _ = admin_url.rpartition("/")
    yield f"{base}/{name}"
    with psycopg.connect(admin_url, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
