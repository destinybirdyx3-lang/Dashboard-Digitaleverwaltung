"""Tests der internen API: OIDC-Prüfung (mit Testschlüssel) und Endpunkte auf Demodaten."""

from __future__ import annotations

import dataclasses
import time
from datetime import date
from pathlib import Path
from unittest import mock

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from mh_dashboard import db, pipeline
from mh_dashboard.api import auth
from mh_dashboard.api.app import create_app
from mh_dashboard.config import Settings

ISSUER = "https://sso.example/realms/stadt"
AUDIENCE = "dashboard-intern"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def token(rollen: list[str], **extra: object) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "u1",
        "iat": now,
        "exp": now + 300,
        "preferred_username": "m.muster",
        "realm_access": {"roles": rollen},
    } | extra
    return jwt.encode(claims, KEY, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture
def client(database_url: str, tmp_path: Path) -> TestClient:
    settings = dataclasses.replace(
        Settings(),
        database_url=database_url,
        output_dir=tmp_path,
        env="test",
        oidc_issuer=ISSUER,
        oidc_audience=AUDIENCE,
        oidc_jwks_url="https://sso.example/certs",
    )
    with db.connect(database_url) as conn:
        db.migrate(conn)
        pipeline.load_demo(conn, settings, date(2026, 9, 30), mit_historie=False)
    signing_key = mock.Mock(key=KEY.public_key())
    with mock.patch.object(auth, "_jwks_client") as jwks:
        jwks.return_value.get_signing_key_from_jwt.return_value = signing_key
        yield TestClient(create_app(settings))


def test_ohne_token_401(client: TestClient) -> None:
    assert client.get("/api/intern/steuerung").status_code == 401


def test_falsche_rolle_403(client: TestClient) -> None:
    r = client.get("/api/intern/steuerung", headers={"Authorization": f"Bearer {token(['andere'])}"})
    assert r.status_code == 403


@pytest.mark.parametrize("extra", [{"exp": int(time.time()) - 100}, {"aud": "fremd"}, {"iss": "https://boese.example"}])
def test_ungueltige_tokens(client: TestClient, extra: dict) -> None:
    r = client.get("/api/intern/me", headers={"Authorization": f"Bearer {token(['dashboard-intern'], **extra)}"})
    assert r.status_code == 401


def test_gefaelschte_signatur(client: TestClient) -> None:
    fremd = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    t = jwt.encode(
        {
            "iss": ISSUER,
            "aud": AUDIENCE,
            "sub": "x",
            "iat": 1,
            "exp": int(time.time()) + 60,
            "realm_access": {"roles": ["dashboard-admin"]},
        },
        fremd,
        algorithm="RS256",
    )
    assert client.get("/api/intern/me", headers={"Authorization": f"Bearer {t}"}).status_code == 401


def test_steuerung_und_organisation(client: TestClient) -> None:
    h = {"Authorization": f"Bearer {token(['dashboard-intern'])}"}
    s = client.get("/api/intern/steuerung", headers=h)
    assert s.status_code == 200 and s.headers["cache-control"] == "no-store"
    body = s.json()
    assert body["priorisierung"] and {b["name"] for b in body["benchmark"]} >= {"Vergleichskommune A"}
    org = client.get("/api/intern/organisationseinheiten", headers=h).json()
    assert any("gesamt" in e for e in org["einheiten"])
    einheit = next(e["id"] for e in org["einheiten"] if "direkt" in e)
    liste = client.get(f"/api/intern/leistungen?einrichtung={einheit}", headers=h).json()["leistungen"]
    assert liste and all(einheit in item["einrichtung_ids"] for item in liste)


def test_qualitaet_nur_fuer_redaktion(client: TestClient) -> None:
    intern = {"Authorization": f"Bearer {token(['dashboard-intern'])}"}
    red = {"Authorization": f"Bearer {token(['dashboard-redaktion'])}"}
    assert client.get("/api/intern/qualitaet", headers=intern).status_code == 403
    q = client.get("/api/intern/qualitaet?befund=unvollstaendig", headers=red).json()
    assert q["eintraege"] and all(e["befund"] == "unvollstaendig" for e in q["eintraege"])
    assert client.get("/api/intern/qualitaet?befund=x", headers=red).status_code == 422
    csv_text = client.get("/api/intern/qualitaet.csv", headers=red).text
    assert csv_text.startswith("﻿Befund;")


def test_auth_disabled_nur_in_dev() -> None:
    with pytest.raises(RuntimeError):
        dataclasses.replace(Settings(), auth_disabled=True, env="prod").validate()
