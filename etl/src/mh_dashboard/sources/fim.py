"""Abruf der Leistungssteckbriefe aus dem FIM-Portal (öffentlich, ohne Authentifizierung).

Die Antwort der Steckbrief-Endpunkte ist in der OpenAPI-Spezifikation nicht typisiert (``schema: {}``).
Der Parser ist deshalb tolerant gegenüber Namensvarianten, verlangt aber einen gültigen
14-stelligen Leistungsschlüssel. Die genaue Struktur wird in Phase 1 an echten Antworten festgezurrt.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import datetime
from typing import Any

import httpx
from pydantic import BaseModel

from .http import request

PAGE_SIZE = 200
LEIKA_RE = re.compile(r"^\d{14}$")
PVLAGEN_URI = "urn:xoev-de:fim:codeliste:pvlagen"


class FimSteckbrief(BaseModel):
    leika_schluessel: str
    bezeichnung: str
    leistungstyp: str | None = None
    typisierung: list[str] = []
    leistungsadressat: list[str] = []
    ozg_ids: list[str] = []
    ozg_themenfeld: str | None = None
    ozg_themenfeld_label: str | None = None
    sdg_codes: list[str] = []
    pv_lagen_codes: list[str] = []
    freigabe_status: int | None = None
    geaendert_am: datetime | None = None


def _first(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if item.get(key) not in (None, "", []):
            return item[key]
    return None


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _code(value: Any) -> str:
    if isinstance(value, dict):
        return str(_first(value, "code", "value", "id") or "")
    return str(value)


def parse_steckbrief(item: dict[str, Any]) -> FimSteckbrief | None:
    schluessel = _first(item, "leistungsschluessel", "leika_schluessel", "id")
    schluessel = next((str(s) for s in _as_list(schluessel) if LEIKA_RE.match(str(s))), None)
    if schluessel is None:
        return None
    ozg = [o for o in _as_list(item.get("ozg")) if isinstance(o, dict)]
    sdg = _as_list(_first(item, "sdg", "sdg_codes", "informationsbereich_sdg", "sdg_informationsbereiche"))
    if isinstance(item.get("informationsbereiche_sdg"), dict):
        sdg = _as_list(item["informationsbereiche_sdg"].get("informationsbereich_sdg1"))
    klassifizierung = [k for k in _as_list(item.get("klassifizierung")) if isinstance(k, dict)]
    status = _first(item, "freigabe_status", "status_katalog")
    geaendert = _first(item, "geaendert_datum_zeit", "letzte_aenderung", "last_update")
    return FimSteckbrief(
        leika_schluessel=schluessel,
        bezeichnung=str(
            _first(item, "title", "leistungsbezeichnung", "bezeichnung", "leistungsbezeichnung_2") or "Kein Titel"
        ),
        leistungstyp=_first(item, "leistungstyp"),
        typisierung=[_code(t) for t in _as_list(item.get("typisierung")) if _code(t)],
        leistungsadressat=[_code(a) for a in _as_list(item.get("leistungsadressat")) if _code(a)],
        ozg_ids=[str(o["id"]) for o in ozg if o.get("id") is not None],
        ozg_themenfeld=next((o.get("themenfeld") for o in ozg if o.get("themenfeld")), None),
        ozg_themenfeld_label=next((o.get("themenfeld_label") for o in ozg if o.get("themenfeld_label")), None),
        sdg_codes=[_code(s) for s in sdg if _code(s) and _code(s) != "0000000"],
        pv_lagen_codes=[
            str(k["value"])
            for k in klassifizierung
            if str(k.get("list_uri", "")).startswith(PVLAGEN_URI) and k.get("value")
        ],
        freigabe_status=int(status) if isinstance(status, (int, str)) and str(status).isdigit() else None,
        geaendert_am=geaendert,
    )


class FimClient:
    def __init__(self, base_url: str, http: httpx.Client) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http
        self.raw_pages: list[tuple[str, dict[str, Any], Any]] = []

    def steckbriefe(self, updated_since: datetime | None = None) -> Iterator[FimSteckbrief]:
        offset = 0
        while True:
            params: dict[str, Any] = {"limit": PAGE_SIZE, "offset": offset, "order_by": "leistungsschluessel_asc"}
            if updated_since:
                params["updated_since"] = updated_since.isoformat()
            url = f"{self.base_url}/api/v1/leistung-steckbriefe"
            payload = request(self.http, "GET", url, params=params).json()
            self.raw_pages.append((url, params, payload))
            items = payload.get("items", []) if isinstance(payload, dict) else payload
            for item in items:
                parsed = parse_steckbrief(item) if isinstance(item, dict) else None
                if parsed:
                    yield parsed
            offset += len(items)
            total = payload.get("total_count") if isinstance(payload, dict) else None
            if not items or (total is not None and offset >= total):
                return
