"""Authentifizierung der internen API über OIDC (städtisches SSO, z. B. Keycloak/ADFS).

Vor der API steht ein Auth-Proxy (oauth2-proxy), der die Anmeldung übernimmt und das Access-Token
weiterreicht. Die API prüft das Token trotzdem selbst (Signatur via JWKS, Aussteller, Zielgruppe,
Ablauf) – Zero Trust auch im internen Netz.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import jwt
from fastapi import Depends, HTTPException, Request, status

from ..config import Settings, get_settings

ROLLE_INTERN = os.environ.get("MH_ROLLE_INTERN", "dashboard-intern")
ROLLE_REDAKTION = os.environ.get("MH_ROLLE_REDAKTION", "dashboard-redaktion")
ROLLE_ADMIN = os.environ.get("MH_ROLLE_ADMIN", "dashboard-admin")
ALGORITHMEN = ["RS256", "RS384", "RS512", "ES256", "ES384", "PS256"]


@dataclass(frozen=True)
class Benutzer:
    name: str
    rollen: frozenset[str]

    @property
    def ist_redaktion(self) -> bool:
        return bool(self.rollen & {ROLLE_REDAKTION, ROLLE_ADMIN})


@lru_cache(maxsize=1)
def _jwks_client(url: str) -> jwt.PyJWKClient:
    return jwt.PyJWKClient(url, cache_keys=True, lifespan=3600)


def _claim(payload: dict[str, Any], path: str) -> Any:
    value: Any = payload
    for part in path.split("."):
        value = value.get(part) if isinstance(value, dict) else None
    return value


def _token(request: Request) -> str | None:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    return request.headers.get("x-forwarded-access-token")


def benutzer_aus_token(token: str, settings: Settings) -> Benutzer:
    if not (settings.oidc_jwks_url and settings.oidc_issuer and settings.oidc_audience):
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "OIDC ist nicht konfiguriert.")
    try:
        key = _jwks_client(settings.oidc_jwks_url).get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            key.key,
            algorithms=ALGORITHMEN,
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            leeway=30,
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Ungültiges Token.") from exc
    rollen = _claim(payload, settings.oidc_roles_claim) or []
    if isinstance(rollen, str):
        rollen = rollen.split()
    name = payload.get("preferred_username") or payload.get("name") or payload["sub"]
    return Benutzer(name=str(name), rollen=frozenset(str(r) for r in rollen))


def aktueller_benutzer(request: Request, settings: Settings = Depends(get_settings)) -> Benutzer:  # noqa: B008
    if settings.auth_disabled:  # nur MH_ENV=dev (siehe Settings.validate)
        return Benutzer("entwicklung", frozenset({ROLLE_INTERN, ROLLE_REDAKTION}))
    token = _token(request)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Anmeldung erforderlich.")
    benutzer = benutzer_aus_token(token, settings)
    if not benutzer.rollen & {ROLLE_INTERN, ROLLE_REDAKTION, ROLLE_ADMIN}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Keine Berechtigung für das interne Dashboard.")
    return benutzer


def redaktion(benutzer: Benutzer = Depends(aktueller_benutzer)) -> Benutzer:  # noqa: B008
    if not benutzer.ist_redaktion:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für die Portalredaktion.")
    return benutzer
