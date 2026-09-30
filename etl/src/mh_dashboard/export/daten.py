"""Stellt die öffentlich freigegebenen Daten aus ``mart`` zusammen – einheitlich für Webseite, PDF,
CSV/XLSX und API. Hier wird entschieden, was öffentlich ist; interne Kennzahlen bleiben außen vor."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import psycopg

from ..reifegrad import REIFEGRAD_VERSION, STUFEN

THEMENFELDER = {
    "arbeit_ruhestand": "Arbeit & Ruhestand",
    "bauen_wohnen": "Bauen & Wohnen",
    "bildung": "Bildung",
    "ein_auswanderung": "Ein- & Auswanderung",
    "engagement_hobby": "Engagement & Hobby",
    "familie_kind": "Familie & Kind",
    "forschung_foerderung": "Forschung & Förderung",
    "gesundheit": "Gesundheit",
    "mobilitaet_reisen": "Mobilität & Reisen",
    "querschnittsleistungen": "Querschnittsleistungen",
    "recht_ordnung": "Recht & Ordnung",
    "steuern_zoll": "Steuern & Zoll",
    "umwelt": "Umwelt",
    "unternehmensfuehrung_entwicklung": "Unternehmensführung & -entwicklung",
    "ohne": "Ohne Themenfeld-Zuordnung",
}
ADRESSATEN = {"001": "Bürgerinnen und Bürger", "002": "Unternehmen", "003": "Verwaltung", "ohne": "Ohne Zuordnung"}
QUELLEN = {
    "optigov": "Serviceportal der Stadt (optiGov)",
    "fim": "FIM-Portal (fimportal.de)",
    "datahub": "Dashboard Digitale Verwaltung / PVOG (api.ozg-umsetzung.de)",
}


def letzter_stichtag(conn: psycopg.Connection) -> date | None:
    row = conn.execute("SELECT max(stichtag) FROM mart.leistung_reifegrad_tag").fetchone()
    return row[0] if row else None


def _kpi(conn: psycopg.Connection, stichtag: date, public_only: bool) -> dict[tuple[str, str], dict[str, Any]]:
    sql = "SELECT kpi, dimension, zaehler, nenner, wert FROM mart.kpi_tag WHERE stichtag=%s"
    if public_only:
        sql += " AND oeffentlich"
    return {
        (k, d): {
            "zaehler": float(z),
            "nenner": float(n) if n is not None else None,
            "wert": float(w) if w is not None else None,
        }
        for k, d, z, n, w in conn.execute(sql, (stichtag,))
    }


def _quote_vor(conn: psycopg.Connection, stichtag: date, tage: int) -> float | None:
    row = conn.execute(
        "SELECT wert FROM mart.kpi_tag WHERE kpi='online_quote' AND dimension='gesamt' "
        "AND stichtag <= %s ORDER BY stichtag DESC LIMIT 1",
        (stichtag - timedelta(days=tage),),
    ).fetchone()
    return float(row[0]) if row and row[0] is not None else None


def quellen_stand(conn: psycopg.Connection) -> tuple[list[dict[str, Any]], bool]:
    rows = conn.execute(
        "SELECT quelle, stand, datenstand_extern, datensaetze, demo FROM raw.quelle_stand ORDER BY quelle"
    ).fetchall()
    quellen = [
        {
            "quelle": q,
            "name": QUELLEN.get(q, q),
            "abgerufen": stand.isoformat(),
            "datenstand": (extern or stand.date()).isoformat(),
            "datensaetze": n,
        }
        for q, stand, extern, n, _demo in rows
    ]
    return quellen, any(r[4] for r in rows)


def uebersicht(conn: psycopg.Connection, stichtag: date, kommune: str, ars: str) -> dict[str, Any]:
    kpi = _kpi(conn, stichtag, public_only=True)

    def get(name: str, dim: str = "gesamt") -> dict[str, Any] | None:
        return kpi.get((name, dim))

    online = get("online_quote")
    vorjahr = _quote_vor(conn, stichtag, 365)
    quellen, demo = quellen_stand(conn)
    themen = sorted(
        (
            {"code": d.split(":", 1)[1], "label": THEMENFELDER.get(d.split(":", 1)[1], d.split(":", 1)[1]), **v}
            for (k, d), v in kpi.items()
            if k == "online_quote" and d.startswith("themenfeld:")
        ),
        key=lambda t: (t["code"] == "ohne", -(t["wert"] or 0), t["label"]),
    )
    adressaten = [
        {"code": d.split(":", 1)[1], "label": ADRESSATEN.get(d.split(":", 1)[1], d), **v}
        for (k, d), v in sorted(kpi.items())
        if k == "online_quote" and d.startswith("adressat:")
    ]
    verteilung = [
        {"stufe": s, "label": STUFEN[s], **(get("reifegrad", f"stufe:{s}") or {"zaehler": 0})} for s in range(5)
    ]
    return {
        "stichtag": stichtag.isoformat(),
        "kommune": kommune,
        "ars": ars,
        "demo": demo,
        "reifegrad_version": REIFEGRAD_VERSION,
        "stufen": STUFEN,
        "quellen": quellen,
        "kennzahlen": {
            "grundgesamtheit": (get("grundgesamtheit") or {}).get("zaehler"),
            "online_quote": online,
            "online_quote_inkl_uebergeordnet": get("online_quote_inkl_uebergeordnet"),
            "angebots_quote": get("angebots_quote"),
            "neu_online_30_tage": (get("neu_online_30_tage") or {}).get("zaehler"),
            "veraenderung_vorjahr_prozentpunkte": (
                round((online["wert"] - vorjahr) * 100, 1)
                if online and online["wert"] is not None and vorjahr is not None
                else None
            ),
            "sdg_erfuellung": get("sdg_erfuellung"),
            "online_termin_quote": get("online_termin_quote"),
        },
        "reifegrad_verteilung": verteilung,
        "themenfelder": themen,
        "adressaten": adressaten,
    }


def entwicklung(conn: psycopg.Connection, stichtag: date, tage: int = 730) -> dict[str, Any]:
    rows = conn.execute(
        "SELECT stichtag, kpi, dimension, zaehler, wert FROM mart.kpi_tag WHERE oeffentlich AND stichtag BETWEEN "
        "%s AND %s AND ((kpi IN ('online_quote','online_quote_inkl_uebergeordnet') AND dimension='gesamt') "
        "OR kpi='reifegrad') ORDER BY stichtag",
        (stichtag - timedelta(days=tage), stichtag),
    ).fetchall()
    tage_map: dict[date, dict[str, Any]] = {}
    for tag, kpi, dim, zaehler, wert in rows:
        eintrag = tage_map.setdefault(tag, {"stichtag": tag.isoformat(), "reifegrad": [0] * 5})
        if kpi == "reifegrad":
            eintrag["reifegrad"][int(dim.split(":")[1])] = int(zaehler)
        else:
            eintrag[kpi] = float(wert) if wert is not None else None
    reihe = list(tage_map.values())
    if len(reihe) > 120:  # auf Wochenwerte verdichten (jeweils letzter Tag der Woche)
        woche: dict[tuple[int, int], dict[str, Any]] = {}
        for eintrag in reihe:
            woche[date.fromisoformat(eintrag["stichtag"]).isocalendar()[:2]] = eintrag
        reihe = list(woche.values())
    return {"stichtag": stichtag.isoformat(), "reihe": reihe}


def leistungen(conn: psycopg.Connection, stichtag: date) -> list[dict[str, Any]]:
    """Öffentliche Leistungsliste: nur Angebotsmerkmale, keine internen Angaben."""
    rows = conn.execute(
        "SELECT leika_schluessel, bezeichnung, reifegrad, online_eigen, online_inkl_uebergeordnet, online_url, "
        "online_termin, sdg_relevant, ozg_themenfeld, leistungsadressat, in_grundgesamtheit, angeboten "
        "FROM mart.leistung_reifegrad_tag WHERE stichtag=%s AND (in_grundgesamtheit OR angeboten "
        "OR online_inkl_uebergeordnet) ORDER BY bezeichnung",
        (stichtag,),
    ).fetchall()
    return [
        {
            "leika": r[0],
            "bezeichnung": r[1],
            "reifegrad": r[2],
            "online": r[3],
            "online_inkl_uebergeordnet": r[4],
            "url": r[5] if (r[3] or r[4]) else None,
            "online_termin": r[6],
            "sdg": r[7],
            "themenfeld": r[8] or "ohne",
            "adressat": list(r[9]),
            "grundgesamtheit": r[10],
            "angeboten": r[11],
        }
        for r in rows
    ]
