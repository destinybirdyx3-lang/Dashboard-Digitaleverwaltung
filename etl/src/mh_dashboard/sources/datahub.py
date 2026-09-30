"""Abruf aus dem Data Hub des Dashboards Digitale Verwaltung (Open-PVOG), öffentlich.

Bevorzugt wird der gestreamte CSV-Export; bei HTTP 413 (zu groß) wird paginiert per JSON geladen.
"""

from __future__ import annotations

import csv
import io
import re
from collections.abc import Iterator
from datetime import date
from typing import Any, Literal

import httpx
from pydantic import BaseModel, field_validator

from .http import request

Sicht = Literal["eigen", "inkl_uebergeordnet"]


class PvogRow(BaseModel):
    leika_key: str
    leika_name: str | None = None
    ars: str
    ars_name: str | None = None
    ozgid: int | None = None
    ozg_bezeichnung: str | None = None
    url: str = ""
    online_status: str | None = None
    aktiv: str | None = None
    art_flaechendeckung: str | None = None
    begruendung_nicht_beruecksichtigt: str | None = None
    datenstand_pvog_import: date | None = None

    @field_validator("leika_key")
    @classmethod
    def _leika(cls, value: str) -> str:
        if not re.fullmatch(r"\d{14}", value):
            raise ValueError("leika_key muss 14 Ziffern haben")
        return value

    @field_validator("ars")
    @classmethod
    def _ars(cls, value: str) -> str:
        if not re.fullmatch(r"\d{12}", value):
            raise ValueError("ars muss 12 Ziffern haben")
        return value

    @field_validator("online_status")
    @classmethod
    def _status(cls, value: str | None) -> str | None:
        if value not in (None, "ok", "nicht ok"):
            raise ValueError(f"unbekannter online_status {value!r}")
        return value

    @field_validator("ozgid", "datenstand_pvog_import", "url", mode="before")
    @classmethod
    def _empty(cls, value: Any, info: Any) -> Any:
        if value in ("", None):
            return "" if info.field_name == "url" else None
        return value

    @property
    def online_ok(self) -> bool | None:
        return None if self.online_status is None else self.online_status == "ok"


_FIELDS = set(PvogRow.model_fields)


def _normalise(row: dict[str, Any]) -> dict[str, Any]:
    cleaned = {}
    for key, value in row.items():
        if key is None:
            continue
        name = re.sub(r"(?<!^)(?=[A-Z])", "_", key.strip()).lower()
        if name in _FIELDS:
            cleaned[name] = value.strip() if isinstance(value, str) else value
    return cleaned


def parse_csv(text: str) -> list[PvogRow]:
    text = text.lstrip("﻿")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    return [PvogRow.model_validate(_normalise(row)) for row in csv.DictReader(io.StringIO(text), dialect=dialect)]


class DatahubClient:
    def __init__(self, base_url: str, http: httpx.Client) -> None:
        self.base_url = base_url.rstrip("/")
        self.http = http
        self.raw: list[tuple[str, dict[str, Any], str]] = []

    def open_pvog(self, ars: str, include_above: bool) -> list[PvogRow]:
        params = {"filetype": "csv", "includeAbove": str(include_above).lower(), "includeBelow": "false"}
        url = f"{self.base_url}/public/v1/dash/open-pvog/{ars}/export"
        try:
            response = request(self.http, "GET", url, params=params)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 413:
                raise
            return list(self._paged(ars, include_above))
        self.raw.append((url, params, response.text))
        return parse_csv(response.text)

    def _paged(self, ars: str, include_above: bool) -> Iterator[PvogRow]:
        page = 0
        while True:
            params = {"page": page, "size": 100, "includeAbove": str(include_above).lower(), "includeBelow": "false"}
            payload = request(self.http, "GET", f"{self.base_url}/public/v1/dash/open-pvog/{ars}", params=params).json()
            for row in payload.get("content", []):
                yield PvogRow.model_validate(_normalise(row))
            page += 1
            if page >= int(payload.get("page", {}).get("totalPages", 0)):
                return
