"""Erzeugt das Veröffentlichungspaket: JSON für die Webseite, PDF-Übersicht (1 Seite, PDF/UA),
CSV/XLSX. Das Paket wird in einem temporären Verzeichnis gebaut und atomar ausgetauscht."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import shutil
from calendar import monthrange
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import psycopg
from jinja2 import Environment, PackageLoader, select_autoescape
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.worksheet.table import Table, TableStyleInfo

from ..reifegrad import REIFEGRAD_VERSION, STUFEN
from . import daten

LIZENZ = "Datenlizenz Deutschland – Namensnennung – Version 2.0 (dl-de/by-2-0)"
LEISTUNG_SPALTEN = [
    ("leika", "LeiKa-Schlüssel"),
    ("bezeichnung", "Leistung"),
    ("reifegrad", "Reifegrad"),
    ("reifegrad_label", "Reifegrad (Bezeichnung)"),
    ("online", "Online (Stadt)"),
    ("online_inkl_uebergeordnet", "Online (inkl. Land/Bund)"),
    ("url", "Onlinedienst"),
    ("online_termin", "Online-Termin"),
    ("sdg", "EU-SDG-relevant"),
    ("themenfeld_label", "Themenfeld"),
    ("adressat_label", "Adressat"),
    ("grundgesamtheit", "In Grundgesamtheit"),
]


def _de_datum(value: str | date) -> str:
    d = date.fromisoformat(value) if isinstance(value, str) else value
    return d.strftime("%d.%m.%Y")


def _render_pdf(data: dict[str, Any], target: Path) -> None:
    from weasyprint import HTML  # schwerer Import nur bei Bedarf

    env = Environment(
        loader=PackageLoader("mh_dashboard.export", "templates"), autoescape=select_autoescape(["html", "j2"])
    )

    def pct(v: dict[str, Any] | None) -> str:
        if not v or v.get("nenner") in (None, 0):
            return "–"
        return f"{v['zaehler'] / v['nenner'] * 100:.0f} %".replace(".", ",")

    def zahl(v: float | None) -> str:
        return "–" if v is None else f"{int(v):,}".replace(",", ".")

    k = data["kennzahlen"]
    html = env.get_template("uebersicht.html.j2").render(
        d=data,
        k=k,
        themen=data["themenfelder"],
        stichtag_de=_de_datum(data["stichtag"]),
        quellen_kurz="optiGov, FIM-Portal, Dashboard Digitale Verwaltung (PVOG)",
        pct=pct,
        zahl=zahl,
        datum=_de_datum,
        anteil=lambda v: "–" if not v else f"{zahl(v['zaehler'])} von {zahl(v['nenner'])}",
        pp=lambda v: "–" if v is None else f"{v:+.1f}".replace(".", ","),
        breite=lambda z, n: 0 if not n else round(float(z) / float(n) * 100, 2),
    )
    HTML(string=html).write_pdf(target, pdf_variant="pdf/ua-1")


def _leistung_zeilen(liste: list[dict[str, Any]]) -> list[dict[str, Any]]:
    zeilen = []
    for item in liste:
        zeile = dict(item)
        zeile["reifegrad_label"] = STUFEN[item["reifegrad"]]
        zeile["themenfeld_label"] = daten.THEMENFELDER.get(item["themenfeld"], item["themenfeld"])
        zeile["adressat_label"] = ", ".join(daten.ADRESSATEN.get(a, a) for a in item["adressat"])
        for key in ("online", "online_inkl_uebergeordnet", "online_termin", "sdg", "grundgesamtheit"):
            zeile[key] = "ja" if item[key] else "nein"
        zeilen.append(zeile)
    return zeilen


def _write_csv(path: Path, headers: list[tuple[str, str]], rows: list[dict[str, Any]]) -> None:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow([label for _, label in headers])
    for row in rows:
        writer.writerow(["" if row.get(key) is None else _csv_safe(row.get(key)) for key, _ in headers])
    path.write_text("﻿" + buffer.getvalue(), encoding="utf-8")  # BOM für Excel


def _csv_safe(value: Any) -> Any:
    """Schutz vor CSV-/Formel-Injection beim Öffnen in Tabellenkalkulationen."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _write_xlsx(path: Path, rows: list[dict[str, Any]], meta: dict[str, str]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Leistungen"
    ws.append([label for _, label in LEISTUNG_SPALTEN])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for row in rows:
        ws.append([_csv_safe(row.get(key)) for key, _ in LEISTUNG_SPALTEN])
    if rows:
        ref = f"A1:{chr(ord('A') + len(LEISTUNG_SPALTEN) - 1)}{len(rows) + 1}"
        table = Table(displayName="Leistungen", ref=ref)
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        ws.add_table(table)
    ws.freeze_panes = "A2"
    for column, width in zip("ABCDEFGHIJKL", (16, 60, 10, 20, 14, 22, 50, 14, 14, 30, 28, 18), strict=True):
        ws.column_dimensions[column].width = width
    info = wb.create_sheet("Metadaten")
    for key, value in meta.items():
        info.append([key, value])
    info.column_dimensions["A"].width = 24
    info.column_dimensions["B"].width = 90
    wb.properties.title = meta["Titel"]
    wb.properties.creator = meta["Herausgeber"]
    wb.save(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(
    conn: psycopg.Connection, output_dir: Path, kommune: str, ars: str, stichtag: date | None = None
) -> dict[str, Any]:
    stichtag = stichtag or daten.letzter_stichtag(conn)
    if stichtag is None:
        raise RuntimeError("Keine Snapshots in mart vorhanden – zuerst transformieren.")

    output_dir.mkdir(parents=True, exist_ok=True)
    ziel = output_dir / "veroeffentlichung"
    tmp = output_dir / f".veroeffentlichung-{datetime.now(UTC):%Y%m%d%H%M%S%f}"
    (tmp / "data").mkdir(parents=True)
    (tmp / "exporte").mkdir()
    archiv = output_dir / "archiv"
    archiv.mkdir(exist_ok=True)

    ueber = daten.uebersicht(conn, stichtag, kommune, ars)
    liste = daten.leistungen(conn, stichtag)
    verlauf = daten.entwicklung(conn, stichtag)
    meta = {
        "Titel": f"Digitalisierungsstand {kommune}",
        "Herausgeber": f"Stadt {kommune}",
        "Stichtag": stichtag.isoformat(),
        "Methodik-Version": REIFEGRAD_VERSION,
        "Lizenz": LIZENZ,
        "Quellen": "; ".join(f"{q['name']} (Stand {q['datenstand']})" for q in ueber["quellen"]),
        "Hinweis": "Nur Angebotsdaten – keine Nutzungs- oder personenbezogenen Daten."
        + (" ACHTUNG: Demodaten." if ueber["demo"] else ""),
    }

    zeilen = _leistung_zeilen(liste)
    _write_csv(tmp / "exporte" / "leistungen.csv", LEISTUNG_SPALTEN, zeilen)
    _write_xlsx(tmp / "exporte" / "leistungen.xlsx", zeilen, meta)
    kpi_rows = conn.execute(
        "SELECT stichtag, kpi, dimension, zaehler, nenner, wert FROM mart.kpi_tag WHERE oeffentlich "
        "ORDER BY stichtag, kpi, dimension"
    ).fetchall()
    _write_csv(
        tmp / "exporte" / "kennzahlen.csv",
        [
            ("stichtag", "Stichtag"),
            ("kpi", "Kennzahl"),
            ("dimension", "Dimension"),
            ("zaehler", "Zähler"),
            ("nenner", "Nenner"),
            ("wert", "Wert"),
        ],
        [dict(zip(("stichtag", "kpi", "dimension", "zaehler", "nenner", "wert"), r, strict=True)) for r in kpi_rows],
    )
    _render_pdf(ueber, tmp / "exporte" / "uebersicht.pdf")

    # Archiv: Übersicht zum Monatsende dauerhaft ablegen
    if stichtag.day == monthrange(stichtag.year, stichtag.month)[1]:
        shutil.copy2(tmp / "exporte" / "uebersicht.pdf", archiv / f"uebersicht-{stichtag:%Y-%m}.pdf")
    archiv_liste = sorted((p.name for p in archiv.glob("uebersicht-*.pdf")), reverse=True)

    exporte = {
        "stichtag": stichtag.isoformat(),
        "dateien": [
            {"art": "uebersicht_pdf", "pfad": "exporte/uebersicht.pdf", "titel": "Übersicht (PDF, 1 Seite)"},
            {"art": "leistungen_csv", "pfad": "exporte/leistungen.csv", "titel": "Leistungen (CSV)"},
            {"art": "leistungen_xlsx", "pfad": "exporte/leistungen.xlsx", "titel": "Leistungen (Excel)"},
            {"art": "kpi_csv", "pfad": "exporte/kennzahlen.csv", "titel": "Kennzahlen-Zeitreihe (CSV)"},
        ],
        "archiv": [{"monat": n[len("uebersicht-") : -4], "pfad": f"archiv/{n}"} for n in archiv_liste],
        "lizenz": LIZENZ,
    }
    for datei in exporte["dateien"]:
        p = tmp / datei["pfad"]
        datei["groesse"] = p.stat().st_size
        datei["sha256"] = _sha256(p)

    for name, inhalt in (
        ("uebersicht.json", ueber),
        ("leistungen.json", {"stichtag": stichtag.isoformat(), "leistungen": liste}),
        ("entwicklung.json", verlauf),
        ("exporte.json", exporte),
    ):
        (tmp / "data" / name).write_text(
            json.dumps(inhalt, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )

    # atomarer Austausch
    alt = output_dir / ".veroeffentlichung-alt"
    if alt.exists():
        shutil.rmtree(alt)
    if ziel.exists():
        ziel.rename(alt)
    tmp.rename(ziel)
    if alt.exists():
        shutil.rmtree(alt)

    conn.execute("DELETE FROM mart.export WHERE stichtag=%s", (stichtag,))
    for datei in exporte["dateien"]:
        conn.execute(
            "INSERT INTO mart.export (stichtag, art, sichtbarkeit, pfad, sha256, methodik_version) "
            "VALUES (%s, %s, 'oeffentlich', %s, %s, %s)",
            (stichtag, datei["art"], datei["pfad"], datei["sha256"], REIFEGRAD_VERSION),
        )
    conn.commit()
    return {"stichtag": stichtag.isoformat(), "verzeichnis": str(ziel), "leistungen": len(liste)}
