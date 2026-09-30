from __future__ import annotations

import dataclasses
from pathlib import Path

import httpx
import respx
from fastapi.testclient import TestClient

from mh_dashboard.config import Settings
from mh_dashboard.guard_proxy import create_app
from mh_dashboard.sources.graphql_guard import QueryAllowlist

UPSTREAM = "https://optigov.example/graphql"
TOKEN = "https://optigov.example/oauth/token"


def _app(query_dir: Path) -> TestClient:
    settings = dataclasses.replace(
        Settings(),
        optigov_query_dir=query_dir,
        optigov_upstream_url=UPSTREAM,
        optigov_token_url=TOKEN,
        optigov_client_id="client",
        optigov_client_secret="geheim",
    )
    return TestClient(create_app(settings, httpx.Client()))


@respx.mock
def test_freigegebene_abfrage_wird_mit_token_weitergeleitet(query_dir: Path) -> None:
    respx.post(TOKEN).respond(json={"access_token": "abc", "expires_in": 300})
    upstream = respx.post(UPSTREAM).respond(json={"data": {"verwaltung": {"id": 1}}})
    query = QueryAllowlist(query_dir).get("VerwaltungFaehigkeiten")
    response = _app(query_dir).post("/graphql", json={"query": query.text, "variables": {"verwaltung": 1}})
    assert response.status_code == 200
    assert upstream.calls.last.request.headers["Authorization"] == "Bearer abc"


@respx.mock
def test_mutation_erreicht_optigov_nie(query_dir: Path) -> None:
    upstream = respx.post(UPSTREAM).respond(json={})
    response = _app(query_dir).post("/graphql", json={"query": "mutation { loescheBuerger(id: 1) }"})
    assert response.status_code == 403
    assert not upstream.called


@respx.mock
def test_antwort_mit_personenbezug_wird_blockiert(query_dir: Path) -> None:
    respx.post(TOKEN).respond(json={"access_token": "abc"})
    respx.post(UPSTREAM).respond(json={"data": {"verwaltung": {"id": 1, "email": "x@y.de"}}})
    query = QueryAllowlist(query_dir).get("VerwaltungFaehigkeiten")
    response = _app(query_dir).post("/graphql", json={"query": query.text, "variables": {"verwaltung": 1}})
    assert response.status_code == 502


def test_unerwartete_felder_in_anfrage(query_dir: Path) -> None:
    response = _app(query_dir).post("/graphql", json={"query": "{ x }", "extensions": {}})
    assert response.status_code == 400
