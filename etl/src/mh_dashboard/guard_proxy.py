"""Egress-Proxy vor optiGov (Dokument 5, Abschnitt 5.3).

Nur dieser Dienst kennt die optiGov-Zugangsdaten. Der ETL-Worker schickt seine Abfragen hierher;
der Proxy lässt ausschließlich freigegebene, lesende Abfragen durch und prüft auch die Antwort.
Start: ``uvicorn mh_dashboard.guard_proxy:app --host 0.0.0.0 --port 8081``
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx
from fastapi import Body, FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .config import Settings, get_settings
from .sources.graphql_guard import GuardViolation, QueryAllowlist, check_response

log = logging.getLogger("mh_dashboard.guard_proxy")


class TokenProvider:
    """OAuth2 Client-Credentials gegen optiGov; Token wird bis kurz vor Ablauf zwischengespeichert."""

    def __init__(self, settings: Settings, client: httpx.Client) -> None:
        self.settings = settings
        self.client = client
        self._token: str | None = None
        self._expires_at = 0.0
        self._lock = threading.Lock()

    def get(self) -> str:
        with self._lock:
            if self._token and time.monotonic() < self._expires_at - 60:
                return self._token
            s = self.settings
            if not (s.optigov_token_url and s.optigov_client_id and s.optigov_client_secret):
                raise RuntimeError("optiGov-Zugangsdaten sind nicht konfiguriert.")
            response = self.client.post(
                s.optigov_token_url,
                data={"grant_type": "client_credentials"},
                auth=(s.optigov_client_id, s.optigov_client_secret),
            )
            response.raise_for_status()
            body = response.json()
            self._token = body["access_token"]
            self._expires_at = time.monotonic() + float(body.get("expires_in", 300))
            return self._token


def create_app(settings: Settings | None = None, upstream: httpx.Client | None = None) -> FastAPI:
    settings = settings or get_settings()
    allowlist = QueryAllowlist(settings.optigov_query_dir)
    http = upstream or httpx.Client(timeout=settings.http_timeout)
    tokens = TokenProvider(settings, http)
    app = FastAPI(title="optiGov Guard-Proxy", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/healthz")
    def healthz() -> dict[str, Any]:
        return {"status": "ok", "freigegebene_abfragen": allowlist.operations}

    @app.post("/graphql")
    def graphql(body: Any = Body(...)) -> JSONResponse:  # noqa: B008 – sync: läuft im Threadpool
        if not isinstance(body, dict) or set(body) - {"query", "operationName", "variables"}:
            raise HTTPException(status_code=400, detail="Unerwarteter Aufbau der Anfrage.")
        query = body.get("query")
        if not isinstance(query, str):
            raise HTTPException(status_code=400, detail="query fehlt.")
        try:
            allowlist.check_request(query, body.get("operationName"), body.get("variables"))
        except GuardViolation as exc:
            log.warning("Abfrage abgelehnt: %s", exc)
            raise HTTPException(status_code=403, detail=str(exc)) from exc

        if not settings.optigov_upstream_url:
            raise HTTPException(status_code=503, detail="optiGov-Upstream nicht konfiguriert.")
        response = http.post(
            settings.optigov_upstream_url,
            json={k: body[k] for k in ("query", "operationName", "variables") if k in body},
            headers={"Authorization": f"Bearer {tokens.get()}"},
        )
        if response.status_code != 200:
            log.error("optiGov antwortete mit HTTP %s", response.status_code)
            raise HTTPException(status_code=502, detail=f"optiGov: HTTP {response.status_code}")
        payload = response.json()
        try:
            check_response(payload)
        except GuardViolation as exc:
            log.error("Antwort verworfen: %s", exc)
            raise HTTPException(status_code=502, detail="Antwort enthielt gesperrte Daten.") from exc
        return JSONResponse(payload)

    return app


def __getattr__(name: str) -> Any:  # lazy: ``uvicorn mh_dashboard.guard_proxy:app``
    if name == "app":
        return create_app()
    raise AttributeError(name)
