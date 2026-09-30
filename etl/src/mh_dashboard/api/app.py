"""Interne, rein lesende API für die Steuerungs-, Organisations- und Qualitätssicht.

Start: ``uvicorn mh_dashboard.api.app:app`` (hinter oauth2-proxy und nginx, nur im Intranet).
Die Datenbankrolle darf nur ``mart`` und ``core.einrichtung`` lesen (Least Privilege).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterator
from datetime import date
from typing import Any

import psycopg
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse

from ..config import Settings, get_settings
from ..export import daten
from ..export.writer import csv_safe
from ..reifegrad import STUFEN
from .auth import Benutzer, aktueller_benutzer, redaktion

BEFUNDE = {
    "ohne_leika": "Dienstleistung ohne LeiKa-Schlüssel",
    "leika_unbekannt": "LeiKa-Schlüssel im FIM-Katalog unbekannt",
    "nicht_gemeldet": "Online im Portal, aber nicht im PVOG gemeldet",
    "nicht_verlinkt": "Im PVOG gemeldet, aber im Portal nicht verlinkt",
    "dienst_defekt": "Onlinedienst laut PVOG nicht funktionsfähig",
    "link_defekt": "Defekter Link in der Leistungsbeschreibung",
    "widerspruch_selbstauskunft": "Selbstauskunft „digitalisiert“ widerspricht dem Reifegrad",
    "veraltet": "Beschreibung länger als 12 Monate nicht bearbeitet",
    "unvollstaendig": "Beschreibung unvollständig",
}
KATEGORIEN = {
    "sdg_pflicht": "EU-SDG-Pflicht, noch nicht online",
    "quick_win": "Quick Win: Onlinedienst von Land/Bund/EfA verfügbar, nicht verlinkt",
    "kommunale_luecke": "Kommunal zuständig, nur Information oder nicht beschrieben",
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    dev = settings.env == "dev"
    app = FastAPI(
        title="Digitalisierungs-Dashboard – interne API",
        docs_url="/api/intern/docs" if dev else None,
        redoc_url=None,
        openapi_url="/api/intern/openapi.json" if dev else None,
    )
    app.dependency_overrides[get_settings] = lambda: settings

    @app.middleware("http")
    async def sicherheits_header(request: Request, call_next: Any) -> Response:
        response: Response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    def conn() -> Iterator[psycopg.Connection]:
        with psycopg.connect(
            settings.database_url, autocommit=True, options="-c default_transaction_read_only=on"
        ) as c:
            yield c

    def stichtag(c: psycopg.Connection) -> date:
        tag = daten.letzter_stichtag(c)
        if tag is None:
            raise HTTPException(503, "Noch keine Daten vorhanden.")
        return tag

    @app.get("/api/intern/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/intern/me")
    def me(benutzer: Benutzer = Depends(aktueller_benutzer)) -> dict[str, Any]:  # noqa: B008
        return {"name": benutzer.name, "redaktion": benutzer.ist_redaktion}

    @app.get("/api/intern/steuerung")
    def steuerung(
        _: Benutzer = Depends(aktueller_benutzer),  # noqa: B008
        c: psycopg.Connection = Depends(conn),  # noqa: B008
    ) -> dict[str, Any]:
        tag = stichtag(c)
        kpis = {
            (k, d): {
                "zaehler": float(z),
                "nenner": float(n) if n is not None else None,
                "wert": float(w) if w is not None else None,
            }
            for k, d, z, n, w in c.execute(
                "SELECT kpi, dimension, zaehler, nenner, wert FROM mart.kpi_tag WHERE stichtag=%s", (tag,)
            )
        }
        namen = dict(
            c.execute(
                "SELECT DISTINCT ON (ars) ars, ars_name FROM core.pvog_eintrag WHERE ars_name IS NOT NULL ORDER BY ars"
            ).fetchall()
        )
        benchmark = sorted(
            (
                {
                    "ars": d.split(":", 1)[1],
                    "name": namen.get(d.split(":", 1)[1]) or d.split(":", 1)[1],
                    "eigene": d.split(":", 1)[1] == settings.ars,
                    **v,
                }
                for (k, d), v in kpis.items()
                if k == "benchmark_online_quote"
            ),
            key=lambda b: -(b["wert"] or 0),
        )
        prio = [
            {
                "leika": r[0],
                "bezeichnung": r[1],
                "kategorie": r[2],
                "kategorie_label": KATEGORIEN[r[2]],
                "rang": r[3],
                "reifegrad": r[4],
                "verfuegbar_unter": r[5],
                "einrichtung_ids": list(r[6]),
            }
            for r in c.execute(
                "SELECT p.leika_schluessel, l.bezeichnung, p.kategorie, p.rang, l.reifegrad, "
                "p.details->>'verfuegbar_unter', l.einrichtung_ids FROM mart.priorisierung p "
                "JOIN mart.leistung_reifegrad_tag l USING (stichtag, leika_schluessel) WHERE p.stichtag=%s "
                "ORDER BY p.rang, l.bezeichnung",
                (tag,),
            )
        ]
        return {
            "stichtag": tag.isoformat(),
            "kennzahlen": {
                "online_quote": kpis.get(("online_quote", "gesamt")),
                "efa_quote": kpis.get(("efa_quote", "gesamt")),
                "leika_zuordnungsquote": kpis.get(("leika_zuordnungsquote", "gesamt")),
                "sdg_erfuellung": kpis.get(("sdg_erfuellung", "gesamt")),
            },
            "benchmark": benchmark,
            "priorisierung": prio,
            "kategorien": KATEGORIEN,
        }

    @app.get("/api/intern/organisationseinheiten")
    def organisationseinheiten(
        _: Benutzer = Depends(aktueller_benutzer),  # noqa: B008
        c: psycopg.Connection = Depends(conn),  # noqa: B008
    ) -> dict[str, Any]:
        tag = stichtag(c)
        einheiten = {
            r[0]: {"id": r[0], "name": r[1], "typ": r[2], "uebergeordnet_id": r[3]}
            for r in c.execute("SELECT optigov_id, name, typ, uebergeordnet_id FROM core.einrichtung")
        }
        for kpi_dim, z, n, w in c.execute(
            "SELECT dimension, zaehler, nenner, wert FROM mart.kpi_tag WHERE stichtag=%s AND kpi='online_quote' "
            "AND (dimension LIKE 'einrichtung:%%' OR dimension LIKE 'organisation:%%')",
            (tag,),
        ):
            art, _, e_id = kpi_dim.partition(":")
            eintrag = einheiten.get(int(e_id))
            if eintrag is not None:
                eintrag["gesamt" if art == "organisation" else "direkt"] = {
                    "zaehler": float(z),
                    "nenner": float(n),
                    "wert": float(w) if w is not None else None,
                }
        return {
            "stichtag": tag.isoformat(),
            "einheiten": sorted(einheiten.values(), key=lambda e: (e["uebergeordnet_id"] or 0, e["name"])),
        }

    @app.get("/api/intern/leistungen")
    def leistungen(
        einrichtung: int | None = Query(default=None),  # noqa: B008
        _: Benutzer = Depends(aktueller_benutzer),  # noqa: B008
        c: psycopg.Connection = Depends(conn),  # noqa: B008
    ) -> dict[str, Any]:
        tag = stichtag(c)
        sql = (
            "SELECT leika_schluessel, bezeichnung, reifegrad, online_eigen, online_inkl_uebergeordnet, online_url, "
            "im_pvog_gemeldet, pvog_online_ok, efa_nachnutzung, selbstauskunft_digital, einrichtung_ids, "
            "in_grundgesamtheit FROM mart.leistung_reifegrad_tag WHERE stichtag=%s"
        )
        params: list[Any] = [tag]
        if einrichtung is not None:
            sql += " AND %s = ANY(einrichtung_ids)"
            params.append(einrichtung)
        rows = c.execute(sql + " ORDER BY bezeichnung", params).fetchall()
        return {
            "stichtag": tag.isoformat(),
            "stufen": STUFEN,
            "leistungen": [
                {
                    "leika": r[0],
                    "bezeichnung": r[1],
                    "reifegrad": r[2],
                    "online": r[3],
                    "online_inkl_uebergeordnet": r[4],
                    "url": r[5],
                    "im_pvog_gemeldet": r[6],
                    "pvog_online_ok": r[7],
                    "efa": r[8],
                    "selbstauskunft": r[9],
                    "einrichtung_ids": list(r[10]),
                    "grundgesamtheit": r[11],
                }
                for r in rows
            ],
        }

    def _befunde(c: psycopg.Connection, befund: str | None, einrichtung: int | None) -> tuple[date, list[dict]]:
        tag = stichtag(c)
        sql = (
            "SELECT q.befund, q.dienstleistung_id, q.leika_schluessel, q.einrichtung_ids, q.details, l.bezeichnung "
            "FROM mart.qualitaet_befund q LEFT JOIN mart.leistung_reifegrad_tag l "
            "ON l.stichtag=q.stichtag AND l.leika_schluessel=q.leika_schluessel WHERE q.stichtag=%s"
        )
        params: list[Any] = [tag]
        if befund:
            if befund not in BEFUNDE:
                raise HTTPException(422, "Unbekannter Befund.")
            sql += " AND q.befund=%s"
            params.append(befund)
        if einrichtung is not None:
            sql += " AND %s = ANY(q.einrichtung_ids)"
            params.append(einrichtung)
        rows = c.execute(sql + " ORDER BY q.befund, q.dienstleistung_id NULLS LAST", params).fetchall()
        return tag, [
            {
                "befund": r[0],
                "befund_label": BEFUNDE[r[0]],
                "dienstleistung_id": r[1],
                "leika": r[2],
                "einrichtung_ids": list(r[3]),
                "details": r[4],
                "bezeichnung": (r[4] or {}).get("name") or r[5] or r[2],
            }
            for r in rows
        ]

    @app.get("/api/intern/qualitaet")
    def qualitaet(
        befund: str | None = None,
        einrichtung: int | None = None,
        _: Benutzer = Depends(redaktion),  # noqa: B008
        c: psycopg.Connection = Depends(conn),  # noqa: B008
    ) -> dict[str, Any]:
        tag, eintraege = _befunde(c, befund, einrichtung)
        zaehlung = dict(
            c.execute(
                "SELECT befund, count(*) FROM mart.qualitaet_befund WHERE stichtag=%s GROUP BY befund", (tag,)
            ).fetchall()
        )
        return {
            "stichtag": tag.isoformat(),
            "befunde": BEFUNDE,
            "anzahl": {k: zaehlung.get(k, 0) for k in BEFUNDE},
            "eintraege": eintraege,
        }

    @app.get("/api/intern/qualitaet.csv")
    def qualitaet_csv(
        befund: str | None = None,
        einrichtung: int | None = None,
        _: Benutzer = Depends(redaktion),  # noqa: B008
        c: psycopg.Connection = Depends(conn),  # noqa: B008
    ) -> Response:
        tag, eintraege = _befunde(c, befund, einrichtung)
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
        writer.writerow(
            [
                "Befund",
                "Leistung/Dienstleistung",
                "Dienstleistung-ID",
                "LeiKa-Schlüssel",
                "Organisationseinheiten",
                "Details",
            ]
        )
        for e in eintraege:
            writer.writerow(
                [
                    e["befund_label"],
                    csv_safe(e["bezeichnung"]),
                    e["dienstleistung_id"] or "",
                    e["leika"] or "",
                    ",".join(map(str, e["einrichtung_ids"])),
                    csv_safe(_details(e["details"])),
                ]
            )
        return Response(
            "﻿" + buffer.getvalue(),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="qualitaet-{tag.isoformat()}.csv"'},
        )

    @app.exception_handler(psycopg.OperationalError)
    def db_fehler(_request: Request, _exc: psycopg.OperationalError) -> JSONResponse:
        return JSONResponse({"detail": "Datenbank nicht erreichbar."}, status_code=503)

    return app


def _details(details: dict[str, Any]) -> str:
    teile = []
    for key, value in (details or {}).items():
        if key == "name":
            continue
        teile.append(f"{key}: {', '.join(value) if isinstance(value, list) else value}")
    return "; ".join(teile)


def __getattr__(name: str) -> Any:
    if name == "app":
        return create_app()
    raise AttributeError(name)
