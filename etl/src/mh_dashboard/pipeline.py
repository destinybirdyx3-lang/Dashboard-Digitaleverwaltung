"""Ablauf des täglichen Laufs (Dokument 4, Abschnitt 4.3).

Jede Quelle läuft in einer eigenen Transaktion. Fällt eine Quelle aus, bleiben ihre Daten vom Vortag
erhalten; transformiert und veröffentlicht wird trotzdem, der Datenstand weist das Alter aus.
Schlagen Plausibilitätsprüfungen oder Datentests fehl, wird nicht veröffentlicht.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import psycopg

from . import db, load
from .config import Settings
from .demo import DEMO_HOSTS, DemoWelt, historie
from .export import writer
from .sources.datahub import DatahubClient, parse_csv
from .sources.fim import FimClient, parse_steckbrief
from .sources.graphql_guard import QueryAllowlist
from .sources.http import make_client
from .sources.optigov import (
    DienstleistungNode,
    EinrichtungNode,
    FormularNode,
    LeikaschluesselNode,
    OnlinedienstNode,
    OptigovClient,
    VerwaltungFaehigkeiten,
)
from .transform import run_transform

log = logging.getLogger("mh_dashboard")


def fetch_optigov(conn: psycopg.Connection, settings: Settings) -> int:
    allowlist = QueryAllowlist(settings.optigov_query_dir)
    with db.etl_lauf(conn, "optigov") as lauf_id, make_client(settings.http_timeout) as http:
        client = OptigovClient(settings.optigov_guard_url, allowlist, http, settings.optigov_verwaltung_id)
        dienstleistungen = client.dienstleistungen()
        load.check_plausibility(
            db.previous_count(conn, "optigov"), len(dienstleistungen), settings.max_abweichung, "optiGov"
        )
        count = load.load_optigov(
            conn,
            dienstleistungen=dienstleistungen,
            onlinedienste=client.onlinedienste(),
            formulare=client.formulare(),
            einrichtungen=client.einrichtungen(),
            leikaschluessel=client.leikaschluessel(),
            faehigkeiten=client.faehigkeiten(),
            eigene_hosts=settings.eigene_hosts,
            today=date.today(),
        )
        for operation, variables, data in client.raw_pages:
            db.store_raw(conn, lauf_id, "optigov", operation, variables, data)
        db.set_quelle_stand(conn, "optigov", count)
    return count


def fetch_fim(conn: psycopg.Connection, settings: Settings) -> int:
    with db.etl_lauf(conn, "fim") as lauf_id, make_client(settings.http_timeout) as http:
        client = FimClient(settings.fim_base_url, http)
        steckbriefe = list(client.steckbriefe())
        load.check_plausibility(db.previous_count(conn, "fim"), len(steckbriefe), settings.max_abweichung, "FIM")
        count = load.load_fim(conn, steckbriefe)
        for url, params, payload in client.raw_pages:
            db.store_raw(conn, lauf_id, "fim", url, params, payload)
        db.set_quelle_stand(conn, "fim", count)
    return count


def fetch_datahub(conn: psycopg.Connection, settings: Settings) -> int:
    with db.etl_lauf(conn, "datahub") as lauf_id, make_client(settings.http_timeout) as http:
        client = DatahubClient(settings.datahub_base_url, http)
        total, stand = 0, None
        jobs: list[tuple[str, Any]] = [(settings.ars, "eigen"), (settings.ars, "inkl_uebergeordnet")]
        jobs += [(ars, "eigen") for ars in settings.benchmark_ars]
        for ars, sicht in jobs:
            rows = client.open_pvog(ars, include_above=sicht == "inkl_uebergeordnet")
            if ars == settings.ars and sicht == "eigen":
                load.check_plausibility(
                    db.previous_count(conn, "datahub"), len(rows), settings.max_abweichung, "Data Hub"
                )
                total = len(rows)
            _, s = load.load_pvog(conn, ars, sicht, rows)
            stand = stand or s
        for url, params, text in client.raw:
            db.store_raw(conn, lauf_id, "datahub", url, params, {"csv": text})
        db.set_quelle_stand(conn, "datahub", total, stand)
    return total


def transform(
    conn: psycopg.Connection, settings: Settings, stichtag: date, eigene_hosts: tuple[str, ...] | None = None
) -> dict[str, int]:
    with db.etl_lauf(conn, "transform"):
        return run_transform(
            conn,
            stichtag,
            settings.ars,
            settings.benchmark_ars,
            settings.kommunal_typisierungen,
            settings.grundgesamtheit_modus,
            eigene_hosts or settings.eigene_hosts,
        )


def export(conn: psycopg.Connection, settings: Settings, stichtag: date | None = None) -> dict[str, Any]:
    with db.etl_lauf(conn, "export"):
        return writer.build(conn, settings.output_dir, settings.kommune_name, settings.ars, stichtag)


def run_all(conn: psycopg.Connection, settings: Settings) -> dict[str, Any]:
    ergebnis: dict[str, Any] = {"quellen": {}}
    for name, job in (("datahub", fetch_datahub), ("fim", fetch_fim), ("optigov", fetch_optigov)):
        try:
            ergebnis["quellen"][name] = job(conn, settings)
        except Exception as exc:  # noqa: BLE001 – Quelle ausgefallen: Vortagesdaten bleiben stehen
            log.exception("Quelle %s fehlgeschlagen", name)
            ergebnis["quellen"][name] = f"Fehler: {exc}"
            if isinstance(exc, load.PlausibilityError):
                raise
    ergebnis["transform"] = transform(conn, settings, date.today())
    ergebnis["export"] = export(conn, settings)
    db.purge_raw(conn)
    return ergebnis


def load_demo(conn: psycopg.Connection, settings: Settings, heute: date, mit_historie: bool = True) -> dict[str, Any]:
    """Lädt Demodaten (inkl. Historie) über dieselben Parser/Ladefunktionen und veröffentlicht sie."""
    welt = DemoWelt(heute)
    steckbriefe = [s for s in (parse_steckbrief(i) for i in welt.fim()) if s]
    stichtage = historie(heute) if mit_historie else [heute]
    for tag in stichtage:
        with db.etl_lauf(conn, "demo"):
            og = welt.optigov(tag)
            load.load_fim(conn, steckbriefe)
            load.load_optigov(
                conn,
                dienstleistungen=[DienstleistungNode.model_validate(n) for n in og["dienstleistungen"]],
                onlinedienste=[OnlinedienstNode.model_validate(n) for n in og["onlinedienste"]],
                formulare=[FormularNode.model_validate(n) for n in og["formulare"]],
                einrichtungen=[EinrichtungNode.model_validate(n) for n in og["einrichtungen"]],
                leikaschluessel=[LeikaschluesselNode.model_validate(n) for n in og["leikaschluessel"]],
                faehigkeiten=VerwaltungFaehigkeiten.model_validate(og["faehigkeiten"]),
                eigene_hosts=DEMO_HOSTS,
                today=tag,
            )
            stand = None
            for ars, sicht in [(settings.ars, "eigen"), (settings.ars, "inkl_uebergeordnet")] + [
                (a, "eigen") for a in settings.benchmark_ars
            ]:
                _, s = load.load_pvog(conn, ars, sicht, parse_csv(welt.pvog_csv(tag, ars, sicht)))
                stand = stand or s
            db.set_quelle_stand(conn, "optigov", len(og["dienstleistungen"]), tag, demo=True)
            db.set_quelle_stand(conn, "fim", len(steckbriefe), tag, demo=True)
            db.set_quelle_stand(conn, "datahub", len(og["dienstleistungen"]), stand, demo=True)
        transform(conn, settings, tag, eigene_hosts=DEMO_HOSTS)
    return {"stichtage": len(stichtage), "export": export(conn, settings, heute)}
