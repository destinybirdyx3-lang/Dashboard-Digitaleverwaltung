"""Integrationstest: Demodaten → core → mart → Veröffentlichungspaket (benötigt PostgreSQL)."""

from __future__ import annotations

import csv
import dataclasses
import json
from datetime import date
from pathlib import Path

import psycopg
import pytest
from pypdf import PdfReader

from mh_dashboard import db, pipeline
from mh_dashboard.config import Settings
from mh_dashboard.load import PlausibilityError, check_plausibility

HEUTE = date(2026, 9, 30)


@pytest.fixture
def settings(database_url: str, tmp_path: Path) -> Settings:
    return dataclasses.replace(Settings(), database_url=database_url, output_dir=tmp_path)


def test_demo_ende_zu_ende(settings: Settings) -> None:
    with db.connect(settings.database_url) as conn:
        db.migrate(conn)
        assert db.migrate(conn) == []  # idempotent
        result = pipeline.load_demo(conn, settings, HEUTE, mit_historie=False)
        assert result["stichtage"] == 1

        # Keine Nutzungs- oder personenbezogenen Tabellen im Schema
        tabellen = {
            r[0]
            for r in conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema IN ('core','mart')"
            )
        }
        assert not {
            t
            for t in tabellen
            if any(x in t for x in ("antrag", "termin", "buerger", "mitarbeiter", "statistik", "nutzung"))
        }

        # Datentests greifen: Online-Leistungen haben Stufe >= 3, Verteilung = Grundgesamtheit
        n = conn.execute("SELECT count(*) FROM mart.leistung_reifegrad_tag WHERE in_grundgesamtheit").fetchone()[0]
        verteilung = conn.execute("SELECT sum(zaehler) FROM mart.kpi_tag WHERE kpi='reifegrad'").fetchone()[0]
        assert n > 50 and verteilung == n
        befunde = {r[0] for r in conn.execute("SELECT DISTINCT befund FROM mart.qualitaet_befund")}
        assert {"nicht_gemeldet", "unvollstaendig", "widerspruch_selbstauskunft"} <= befunde
        kategorien = {r[0] for r in conn.execute("SELECT DISTINCT kategorie FROM mart.priorisierung")}
        assert "quick_win" in kategorien

    pub = settings.output_dir / "veroeffentlichung"
    ueber = json.loads((pub / "data" / "uebersicht.json").read_text())
    assert ueber["demo"] is True and ueber["stichtag"] == HEUTE.isoformat()
    assert 0 < ueber["kennzahlen"]["online_quote"]["wert"] < 1
    # interne Kennzahlen gelangen nicht in die öffentlichen Daten
    text = (pub / "data" / "uebersicht.json").read_text()
    assert "benchmark" not in text and "einrichtung" not in text and "efa_quote" not in text
    leistungen = json.loads((pub / "data" / "leistungen.json").read_text())["leistungen"]
    assert leistungen and set(leistungen[0]) == {
        "leika",
        "bezeichnung",
        "reifegrad",
        "online",
        "online_inkl_uebergeordnet",
        "url",
        "online_termin",
        "sdg",
        "themenfeld",
        "adressat",
        "grundgesamtheit",
        "angeboten",
    }

    pdf = PdfReader(pub / "exporte" / "uebersicht.pdf")
    assert len(pdf.pages) == 1, "Die Übersicht muss auf eine Seite passen"
    assert pdf.metadata.title.startswith("Digitalisierungsstand")
    catalog = pdf.trailer["/Root"]
    assert "/StructTreeRoot" in catalog and catalog["/MarkInfo"]["/Marked"]  # getaggtes PDF (PDF/UA)
    assert catalog["/Lang"] == "de"

    with (pub / "exporte" / "leistungen.csv").open(encoding="utf-8-sig") as f:
        rows = list(csv.reader(f, delimiter=";"))
    assert rows[0][0] == "LeiKa-Schlüssel" and len(rows) == len(leistungen) + 1


def test_zweiter_lauf_ueberschreibt_stichtag(settings: Settings) -> None:
    with db.connect(settings.database_url) as conn:
        db.migrate(conn)
        pipeline.load_demo(conn, settings, HEUTE, mit_historie=False)
        erster = conn.execute("SELECT count(*) FROM mart.kpi_tag").fetchone()[0]
        pipeline.transform(conn, settings, HEUTE, eigene_hosts=("muelheim.example",))
        assert conn.execute("SELECT count(*) FROM mart.kpi_tag").fetchone()[0] == erster


def test_fehlgeschlagener_lauf_wird_protokolliert(settings: Settings) -> None:
    with db.connect(settings.database_url) as conn:
        db.migrate(conn)
        with pytest.raises(RuntimeError), db.etl_lauf(conn, "fim"):
            raise RuntimeError("Quelle nicht erreichbar")
        status, fehler = conn.execute("SELECT status, fehler FROM raw.etl_lauf").fetchone()
        assert status == "fehler" and "nicht erreichbar" in fehler


def test_plausibilitaet() -> None:
    check_plausibility(100, 110, 0.2, "x")
    with pytest.raises(PlausibilityError):
        check_plausibility(100, 50, 0.2, "x")
    with pytest.raises(PlausibilityError):
        check_plausibility(None, 0, 0.2, "x")


def test_export_ohne_daten_schlaegt_fehl(settings: Settings) -> None:
    with db.connect(settings.database_url) as conn:
        db.migrate(conn)
        with pytest.raises(RuntimeError, match="Keine Snapshots"):
            pipeline.export(conn, settings)
        assert isinstance(conn, psycopg.Connection)
