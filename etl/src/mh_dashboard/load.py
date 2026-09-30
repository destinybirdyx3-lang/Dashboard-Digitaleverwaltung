"""Überführt validierte Quelldaten in die core-Tabellen.

Jede Quelle ersetzt ihre core-Tabellen vollständig innerhalb einer Transaktion (täglicher Voll-Abgleich);
so werden auch Löschungen erkannt. Schlägt eine Quelle fehl, bleiben ihre Daten vom Vortag stehen.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date
from typing import Any
from urllib.parse import urlparse

import psycopg

from .sources.datahub import PvogRow, Sicht
from .sources.fim import FimSteckbrief
from .sources.optigov import (
    DienstleistungNode,
    EinrichtungNode,
    FormularNode,
    LeikaschluesselNode,
    OnlinedienstNode,
    VerwaltungFaehigkeiten,
)


class PlausibilityError(RuntimeError):
    """Die Datenmenge weicht zu stark vom Vortag ab – Veröffentlichung wird angehalten."""


def check_plausibility(previous: int | None, current: int, max_deviation: float, quelle: str) -> None:
    if current == 0:
        raise PlausibilityError(f"{quelle}: keine Datensätze erhalten.")
    if previous and abs(current - previous) / previous > max_deviation:
        raise PlausibilityError(f"{quelle}: {current} statt {previous} Datensätze (Abweichung > {max_deviation:.0%}).")


def url_host(url: str | None) -> str | None:
    if not url:
        return None
    host = urlparse(url).hostname
    return host.lower() if host else None


def is_eigen(host: str | None, eigene_hosts: Sequence[str]) -> bool | None:
    if host is None:
        return None
    return any(host == h or host.endswith("." + h) for h in eigene_hosts)


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def aktuell_sichtbar(node: DienstleistungNode, today: date) -> bool:
    if not node.oeffentlich_anzeigen:
        return False

    def _date(jahr: int | None, monat: int | None, tag: int | None, default: date) -> date:
        if not jahr:
            return default
        try:
            return date(jahr, monat or 1, tag or 1)
        except ValueError:
            return default

    von = _date(node.sichtbar_von_jahr, node.sichtbar_von_monat, node.sichtbar_von_tag, date.min)
    bis = _date(node.sichtbar_bis_jahr, node.sichtbar_bis_monat, node.sichtbar_bis_tag, date.max)
    return von <= today <= bis


def _replace(conn: psycopg.Connection, table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> int:
    conn.execute(f"DELETE FROM {table}")
    count = 0
    with conn.cursor().copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)
            count += 1
    return count


def load_optigov(
    conn: psycopg.Connection,
    *,
    dienstleistungen: list[DienstleistungNode],
    onlinedienste: list[OnlinedienstNode],
    formulare: list[FormularNode],
    einrichtungen: list[EinrichtungNode],
    leikaschluessel: list[LeikaschluesselNode],
    faehigkeiten: VerwaltungFaehigkeiten,
    eigene_hosts: Sequence[str],
    today: date,
) -> int:
    for table in (
        "core.dienstleistung_leika",
        "core.dienstleistung_einrichtung",
        "core.dienstleistung_onlinedienst",
        "core.dienstleistung_formular",
    ):
        conn.execute(f"DELETE FROM {table}")

    _replace(
        conn,
        "core.einrichtung",
        ("optigov_id", "name", "kurzbezeichnung", "typ", "uebergeordnet_id", "oeffentlich"),
        (
            (
                e.id,
                e.name,
                e.kurzbezeichnung,
                e.einrichtungstyp.name if e.einrichtungstyp else None,
                e.uebergeordnete_einrichtung.id if e.uebergeordnete_einrichtung else None,
                e.oeffentlich_anzeigen,
            )
            for e in einrichtungen
        ),
    )

    count = _replace(
        conn,
        "core.dienstleistung",
        (
            "optigov_id",
            "name",
            "oeffentlich",
            "aktuell_sichtbar",
            "selbstauskunft_digital",
            "hat_beschreibung",
            "hat_kosten",
            "hat_unterlagen",
            "hat_bearbeitungsdauer",
            "anzahl_formular_downloads",
            "hat_online_termin",
            "anzahl_links",
            "anzahl_links_defekt",
            "themenfelder",
            "infodienst_aktualisiert",
            "erstellt_am",
            "bearbeitet_am",
        ),
        (
            (
                d.id,
                d.leistungsname,
                d.oeffentlich_anzeigen,
                aktuell_sichtbar(d, today),
                d.digitalisiert,
                _has_text(d.hat_kurztext),
                _has_text(d.kosten) or d.kostenpunkte.totalCount > 0,
                _has_text(d.unterlagen),
                _has_text(d.bearbeitungsdauer),
                d.formulare_downloads.totalCount + d.formulare_links.totalCount + d.dokumente.totalCount,
                any(not t.intern for t in d.terminvorlagen.nodes),
                len(d.links.nodes),
                sum(1 for link in d.links.nodes if link.erreichbar is False),
                sorted({t.name for t in d.themenfelder.nodes}),
                d.infodienst_dienstleistung.aktualisiert if d.infodienst_dienstleistung else None,
                d.erstellt,
                d.bearbeitet,
            )
            for d in dienstleistungen
        ),
    )

    leika_rows: set[tuple[int, str, str]] = set()
    for d in dienstleistungen:
        for ref in d.leikaschluessel.nodes:
            leika_rows.add((d.id, ref.schluessel.strip(), "direkt"))
        info = d.infodienst_dienstleistung
        if info and info.leikaschluessel:
            for key in info.leikaschluessel.replace(";", ",").split(","):
                if key.strip():
                    leika_rows.add((d.id, key.strip(), "infodienst"))
    _append(
        conn,
        "core.dienstleistung_leika",
        ("dienstleistung_id", "leika_schluessel", "herkunft"),
        [r for r in leika_rows if len(r[1]) == 14 and r[1].isdigit()],
    )
    _append(
        conn,
        "core.dienstleistung_einrichtung",
        ("dienstleistung_id", "einrichtung_id"),
        {(d.id, e.id) for d in dienstleistungen for e in d.einrichtungen.nodes},
    )

    known = {d.id for d in dienstleistungen}
    _replace(
        conn,
        "core.onlinedienst",
        (
            "optigov_id",
            "name",
            "typ",
            "url",
            "url_host",
            "eigener_dienst",
            "vertrauensniveau",
            "zahlungsweise",
            "formular_id",
        ),
        (
            (
                o.id,
                o.name,
                o.typ,
                o.url,
                url_host(o.url),
                is_eigen(url_host(o.url), eigene_hosts),
                o.vertrauensniveau,
                o.zahlungsweise,
                o.formular.id if o.formular else None,
            )
            for o in onlinedienste
        ),
    )
    _append(
        conn,
        "core.dienstleistung_onlinedienst",
        ("dienstleistung_id", "onlinedienst_id"),
        {(d.id, o.id) for o in onlinedienste for d in o.dienstleistungen.nodes if d.id in known}
        | {(d.id, o.id) for d in dienstleistungen for o in d.onlinedienste.nodes},
    )

    _replace(
        conn,
        "core.formular",
        ("optigov_id", "titel", "url", "benoetigte_vertrauensstufe", "anbieter"),
        ((f.id, f.titel, f.url, f.benoetigte_vertrauensstufe, f.formularserver.anbieter) for f in formulare),
    )
    _append(
        conn,
        "core.dienstleistung_formular",
        ("dienstleistung_id", "formular_id"),
        {(d.id, f.id) for f in formulare for d in f.dienstleistungen.nodes if d.id in known}
        | {(d.id, f.id) for d in dienstleistungen for f in d.formulare.nodes},
    )

    conn.execute("UPDATE core.leistung SET in_optigov_katalog = false")
    for node in leikaschluessel:
        if not (len(node.schluessel) == 14 and node.schluessel.isdigit()):
            continue
        conn.execute(
            "INSERT INTO core.leistung (leika_schluessel, bezeichnung, leistungstyp, typisierung, sdg_codes, "
            "pv_lagen_codes, in_optigov_katalog) VALUES (%s, %s, %s, %s, %s, %s, true) "
            "ON CONFLICT (leika_schluessel) DO UPDATE SET in_optigov_katalog = true, "
            "typisierung = CASE WHEN core.leistung.in_fim THEN core.leistung.typisierung "
            "ELSE excluded.typisierung END, "
            "sdg_codes = CASE WHEN core.leistung.in_fim THEN core.leistung.sdg_codes ELSE excluded.sdg_codes END",
            (
                node.schluessel,
                node.bezeichnung or node.bezeichnung2,
                node.leistungstyp,
                [node.typ] if node.typ else [],
                [c for c in (node.sdg_code or "").split(",") if c.strip()],
                [c.strip() for c in (node.portalverbund_lagen_codes or "").split(",") if c.strip()],
            ),
        )

    conn.execute("DELETE FROM core.verwaltung_faehigkeit")
    modul = faehigkeiten.modulkonfiguration
    conn.execute(
        "INSERT INTO core.verwaltung_faehigkeit (bund_id, muk, dms_d3, meet, buergerservice) "
        "VALUES (%s, %s, %s, %s, %s)",
        (
            faehigkeiten.bund_id is not None,
            faehigkeiten.muk is not None or bool(modul and modul.muk),
            bool(modul and modul.dms_d3),
            bool(modul and modul.meet),
            bool(modul and modul.buergerservice),
        ),
    )
    return count


def _append(conn: psycopg.Connection, table: str, columns: Sequence[str], rows: Iterable[Sequence[Any]]) -> None:
    with conn.cursor().copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def load_fim(conn: psycopg.Connection, steckbriefe: Iterable[FimSteckbrief], full: bool = True) -> int:
    if full:
        conn.execute("UPDATE core.leistung SET in_fim = false")
    count = 0
    for s in steckbriefe:
        conn.execute(
            "INSERT INTO core.leistung (leika_schluessel, bezeichnung, leistungstyp, typisierung, leistungsadressat, "
            "ozg_ids, ozg_themenfeld, ozg_themenfeld_label, sdg_codes, pv_lagen_codes, fim_freigabe_status, "
            "fim_geaendert_am, in_fim) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,true) "
            "ON CONFLICT (leika_schluessel) DO UPDATE SET bezeichnung=excluded.bezeichnung, "
            "leistungstyp=excluded.leistungstyp, typisierung=excluded.typisierung, "
            "leistungsadressat=excluded.leistungsadressat, ozg_ids=excluded.ozg_ids, "
            "ozg_themenfeld=excluded.ozg_themenfeld, ozg_themenfeld_label=excluded.ozg_themenfeld_label, "
            "sdg_codes=excluded.sdg_codes, pv_lagen_codes=excluded.pv_lagen_codes, "
            "fim_freigabe_status=excluded.fim_freigabe_status, fim_geaendert_am=excluded.fim_geaendert_am, "
            "in_fim=true",
            (
                s.leika_schluessel,
                s.bezeichnung,
                s.leistungstyp,
                s.typisierung,
                s.leistungsadressat,
                s.ozg_ids,
                s.ozg_themenfeld,
                s.ozg_themenfeld_label,
                s.sdg_codes,
                s.pv_lagen_codes,
                s.freigabe_status,
                s.geaendert_am,
            ),
        )
        count += 1
    return count


def load_pvog(conn: psycopg.Connection, ars: str, sicht: Sicht, rows: list[PvogRow]) -> tuple[int, date | None]:
    conn.execute("DELETE FROM core.pvog_eintrag WHERE ars=%s AND sicht=%s", (ars, sicht))
    _append(
        conn,
        "core.pvog_eintrag",
        (
            "ars",
            "sicht",
            "ars_name",
            "leika_schluessel",
            "leika_name",
            "url",
            "url_host",
            "ozg_id",
            "online_ok",
            "aktiv",
            "flaechendeckung",
            "begruendung_nicht_beruecksichtigt",
            "datenstand_pvog",
        ),
        (
            (
                ars,
                sicht,
                r.ars_name,
                r.leika_key,
                r.leika_name,
                r.url,
                url_host(r.url),
                r.ozgid,
                r.online_ok,
                None if r.aktiv is None else r.aktiv == "ja",
                r.art_flaechendeckung,
                r.begruendung_nicht_beruecksichtigt,
                r.datenstand_pvog_import,
            )
            for r in rows
        ),
    )
    stand = max((r.datenstand_pvog_import for r in rows if r.datenstand_pvog_import), default=None)
    return len(rows), stand
