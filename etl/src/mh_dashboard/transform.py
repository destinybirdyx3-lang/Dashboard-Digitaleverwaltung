"""Berechnet aus ``core`` die Tages-Snapshots in ``mart``: Reifegrad je Leistung, Kennzahlen,
Qualitätsbefunde und Priorisierungsliste (Dokument 3)."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .load import is_eigen, url_host
from .reifegrad import (
    REIFEGRAD_VERSION,
    DienstleistungInfo,
    Faehigkeiten,
    LeistungErgebnis,
    OnlineZugang,
    PvogInfo,
    bewerte_leistung,
    ist_kommunal,
    stufe_dienstleistung,
)

VERALTET_NACH_TAGEN = 365
ADRESSATEN = {"001": "Bürgerinnen und Bürger", "002": "Unternehmen", "003": "Verwaltung"}


@dataclass
class Leistung:
    leika_schluessel: str
    bezeichnung: str
    typisierung: list[str]
    leistungsadressat: list[str]
    ozg_themenfeld: str | None
    ozg_themenfeld_label: str | None
    sdg_codes: list[str]
    in_fim: bool
    in_optigov_katalog: bool


@dataclass
class Dienstleistung:
    info: DienstleistungInfo
    name: str
    hat_beschreibung: bool
    hat_kosten: bool
    hat_unterlagen: bool
    hat_bearbeitungsdauer: bool
    anzahl_links_defekt: int
    erstellt_am: datetime
    bearbeitet_am: datetime | None
    leika: set[str]
    einrichtungen: set[int]


@dataclass
class Snapshot:
    stichtag: date
    leistungen: dict[str, Leistung]
    dienstleistungen: dict[int, Dienstleistung]
    pvog: dict[tuple[str, str], dict[str, list[PvogInfo]]]  # (ars, sicht) -> key -> Einträge
    faehigkeiten: Faehigkeiten
    fim_vorhanden: bool
    pvog_namen: dict[str, str]


def read_snapshot(conn: psycopg.Connection, stichtag: date, ars: str, eigene_hosts: Sequence[str]) -> Snapshot:
    leistungen = {
        r[0]: Leistung(r[0], r[1], list(r[2]), list(r[3]), r[4], r[5], list(r[6]), r[7], r[8])
        for r in conn.execute(
            "SELECT leika_schluessel, bezeichnung, typisierung, leistungsadressat, ozg_themenfeld, "
            "ozg_themenfeld_label, sdg_codes, in_fim, in_optigov_katalog FROM core.leistung"
        )
    }
    zugaenge: dict[int, list[OnlineZugang]] = defaultdict(list)
    for dl_id, url, eigen, vn, zw in conn.execute(
        "SELECT x.dienstleistung_id, o.url, o.eigener_dienst, o.vertrauensniveau, o.zahlungsweise "
        "FROM core.dienstleistung_onlinedienst x JOIN core.onlinedienst o ON o.optigov_id = x.onlinedienst_id"
    ):
        zugaenge[dl_id].append(OnlineZugang(url, eigen, vn, zw))
    for dl_id, url, vn in conn.execute(
        "SELECT x.dienstleistung_id, f.url, f.benoetigte_vertrauensstufe FROM core.dienstleistung_formular x "
        "JOIN core.formular f ON f.optigov_id = x.formular_id"
    ):
        zugaenge[dl_id].append(OnlineZugang(url, is_eigen(url_host(url), eigene_hosts), vn, None))

    leika: dict[int, set[str]] = defaultdict(set)
    for dl_id, key in conn.execute("SELECT dienstleistung_id, leika_schluessel FROM core.dienstleistung_leika"):
        leika[dl_id].add(key)
    einr: dict[int, set[int]] = defaultdict(set)
    for dl_id, e_id in conn.execute("SELECT dienstleistung_id, einrichtung_id FROM core.dienstleistung_einrichtung"):
        einr[dl_id].add(e_id)

    dienstleistungen = {}
    for row in conn.execute(
        "SELECT optigov_id, name, aktuell_sichtbar, selbstauskunft_digital, anzahl_formular_downloads, hat_kosten, "
        "hat_online_termin, hat_beschreibung, hat_unterlagen, hat_bearbeitungsdauer, anzahl_links_defekt, "
        "erstellt_am, bearbeitet_am FROM core.dienstleistung"
    ):
        info = DienstleistungInfo(row[0], row[2], row[3], row[4], row[5], row[6], tuple(zugaenge.get(row[0], ())))
        dienstleistungen[row[0]] = Dienstleistung(
            info,
            row[1],
            row[7],
            row[5],
            row[8],
            row[9],
            row[10],
            row[11],
            row[12],
            leika.get(row[0], set()),
            einr.get(row[0], set()),
        )

    pvog: dict[tuple[str, str], dict[str, list[PvogInfo]]] = defaultdict(lambda: defaultdict(list))
    for p_ars, sicht, key, url, ok, deckung, host in conn.execute(
        "SELECT ars, sicht, leika_schluessel, url, online_ok, flaechendeckung, url_host FROM core.pvog_eintrag "
        "WHERE aktiv IS DISTINCT FROM false"
    ):
        pvog[(p_ars, sicht)][key].append(PvogInfo(url, ok, deckung, is_eigen(host, eigene_hosts)))

    f_row = conn.execute("SELECT bund_id, dms_d3 FROM core.verwaltung_faehigkeit").fetchone()
    faehigkeiten = Faehigkeiten(bund_id=bool(f_row and f_row[0]), dms_d3=bool(f_row and f_row[1]))
    fim_vorhanden = any(leistung.in_fim for leistung in leistungen.values())
    pvog_namen = dict(
        conn.execute(
            "SELECT DISTINCT ON (leika_schluessel) leika_schluessel, leika_name FROM core.pvog_eintrag "
            "WHERE leika_name IS NOT NULL AND leika_name <> '' ORDER BY leika_schluessel, ars"
        ).fetchall()
    )
    return Snapshot(stichtag, leistungen, dienstleistungen, pvog, faehigkeiten, fim_vorhanden, pvog_namen)


@dataclass
class MartRow:
    leika_schluessel: str
    leistung: Leistung | None
    ergebnis: LeistungErgebnis
    in_grundgesamtheit: bool
    einrichtung_ids: list[int]
    dienstleistung_ids: list[int]

    @property
    def sdg_relevant(self) -> bool:
        return bool(self.leistung and self.leistung.sdg_codes)


def bewerte(snapshot: Snapshot, ars: str, kommunal: Sequence[str], modus: str) -> dict[str, MartRow]:
    dl_by_key: dict[str, list[Dienstleistung]] = defaultdict(list)
    for dl in snapshot.dienstleistungen.values():
        for key in dl.leika:
            dl_by_key[key].append(dl)
    eigen = snapshot.pvog.get((ars, "eigen"), {})
    ueber = snapshot.pvog.get((ars, "inkl_uebergeordnet"), {})

    # Nur aktuell gültige Katalogeinträge zählen: FIM ist führend; ohne FIM-Daten der LeiKa-Katalog aus optiGov.
    def im_katalog(v: Leistung) -> bool:
        return v.in_fim if snapshot.fim_vorhanden else v.in_optigov_katalog

    kommunal_keys = {
        k for k, v in snapshot.leistungen.items() if im_katalog(v) and ist_kommunal(v.typisierung, kommunal)
    }
    bekannt = {k for k, dls in dl_by_key.items() if any(d.info.aktuell_sichtbar for d in dls)} | set(eigen) | set(ueber)
    if modus == "fim_kommunal":
        grundgesamtheit = kommunal_keys
    else:  # „bekannt“: kommunal oder ohne Typisierung, aber in einer Mülheimer Quelle vorhanden
        ohne_typ = {k for k in bekannt if not (snapshot.leistungen.get(k) and snapshot.leistungen[k].typisierung)}
        grundgesamtheit = (kommunal_keys & bekannt) | ohne_typ

    rows: dict[str, MartRow] = {}
    for key in sorted(grundgesamtheit | bekannt):
        dls = dl_by_key.get(key, [])
        ergebnis = bewerte_leistung(
            [d.info for d in dls], eigen.get(key, []), ueber.get(key, []), snapshot.faehigkeiten
        )
        sichtbar = [d for d in dls if d.info.aktuell_sichtbar]
        rows[key] = MartRow(
            key,
            snapshot.leistungen.get(key),
            ergebnis,
            key in grundgesamtheit,
            sorted({e for d in sichtbar for e in d.einrichtungen}),
            sorted(d.info.id for d in sichtbar),
        )
    return rows


def _bezeichnung(row: MartRow, snapshot: Snapshot) -> str:
    if row.leistung and row.leistung.bezeichnung:
        return row.leistung.bezeichnung
    if row.dienstleistung_ids:
        return snapshot.dienstleistungen[row.dienstleistung_ids[0]].name
    return snapshot.pvog_namen.get(row.leika_schluessel) or f"Leistung {row.leika_schluessel}"


def kennzahlen(
    rows: dict[str, MartRow],
    snapshot: Snapshot,
    ars: str,
    benchmark: Sequence[str],
    einrichtung_eltern: dict[int, int | None],
    vor_30_tagen: set[str] | None,
) -> list[tuple]:
    """Liefert (kpi, dimension, zaehler, nenner, oeffentlich)."""
    g = [r for r in rows.values() if r.in_grundgesamtheit]
    n = len(g)
    out: list[tuple] = [
        ("grundgesamtheit", "gesamt", n, None, True),
        ("angebots_quote", "gesamt", sum(r.ergebnis.angeboten for r in g), n, True),
        ("online_quote", "gesamt", sum(r.ergebnis.online_eigen for r in g), n, True),
        ("online_quote_inkl_uebergeordnet", "gesamt", sum(r.ergebnis.online_inkl_uebergeordnet for r in g), n, True),
    ]
    for stufe in range(5):
        out.append(("reifegrad", f"stufe:{stufe}", sum(r.ergebnis.reifegrad == stufe for r in g), n, True))

    def gruppe(prefix: str, keyfn: Any, public: bool) -> None:
        groups: dict[str, list[MartRow]] = defaultdict(list)
        for r in g:
            for k in keyfn(r):
                groups[k].append(r)
        for k, members in groups.items():
            out.append(
                ("online_quote", f"{prefix}:{k}", sum(m.ergebnis.online_eigen for m in members), len(members), public)
            )

    gruppe("themenfeld", lambda r: [(r.leistung and r.leistung.ozg_themenfeld) or "ohne"], True)
    gruppe("adressat", lambda r: (r.leistung and r.leistung.leistungsadressat) or ["ohne"], True)

    def wurzel(e_id: int) -> int:
        seen = set()
        while einrichtung_eltern.get(e_id) and e_id not in seen:
            seen.add(e_id)
            e_id = einrichtung_eltern[e_id]  # type: ignore[assignment]
        return e_id

    gruppe("einrichtung", lambda r: [str(e) for e in r.einrichtung_ids], False)
    gruppe("organisation", lambda r: sorted({str(wurzel(e)) for e in r.einrichtung_ids}), False)

    sdg = [r for r in g if r.sdg_relevant]
    out.append(("sdg_erfuellung", "gesamt", sum(r.ergebnis.reifegrad >= 3 for r in sdg), len(sdg), True))
    angeboten = [r for r in g if r.ergebnis.angeboten]
    out.append(
        ("online_termin_quote", "gesamt", sum(r.ergebnis.online_termin for r in angeboten), len(angeboten), True)
    )
    online = [r for r in g if r.ergebnis.online_eigen and r.ergebnis.efa_nachnutzung is not None]
    out.append(("efa_quote", "gesamt", sum(bool(r.ergebnis.efa_nachnutzung) for r in online), len(online), False))
    if vor_30_tagen is not None:
        neu = [r for r in g if r.ergebnis.online_eigen and r.leika_schluessel not in vor_30_tagen]
        out.append(("neu_online_30_tage", "gesamt", len(neu), None, True))

    sichtbar = [d for d in snapshot.dienstleistungen.values() if d.info.aktuell_sichtbar]
    out.append(("leika_zuordnungsquote", "gesamt", sum(bool(d.leika) for d in sichtbar), len(sichtbar), False))

    keys = {r.leika_schluessel for r in g}
    for b_ars in (ars, *benchmark):
        entries = snapshot.pvog.get((b_ars, "eigen"))
        if entries is None:
            continue
        ok = sum(1 for k in keys if any(e.url and e.online_ok is not False for e in entries.get(k, [])))
        out.append(("benchmark_online_quote", f"ars:{b_ars}", ok, n, False))
    return out


def qualitaetsbefunde(rows: dict[str, MartRow], snapshot: Snapshot, ars: str) -> list[tuple]:
    """Liefert (befund, dienstleistung_id, leika_schluessel, einrichtung_ids, details)."""
    out: list[tuple] = []
    heute = datetime.combine(snapshot.stichtag, datetime.min.time(), tzinfo=UTC)
    eigen = snapshot.pvog.get((ars, "eigen"), {})
    faehig = snapshot.faehigkeiten
    for dl in snapshot.dienstleistungen.values():
        if not dl.info.aktuell_sichtbar:
            continue
        e_ids = sorted(dl.einrichtungen)
        if not dl.leika:
            out.append(("ohne_leika", dl.info.id, None, e_ids, {"name": dl.name}))
        if snapshot.fim_vorhanden:
            for key in sorted(dl.leika):
                leistung = snapshot.leistungen.get(key)
                if leistung is None or not leistung.in_fim:
                    out.append(("leika_unbekannt", dl.info.id, key, e_ids, {"name": dl.name}))
        if dl.anzahl_links_defekt:
            out.append(("link_defekt", dl.info.id, None, e_ids, {"name": dl.name, "anzahl": dl.anzahl_links_defekt}))
        online = stufe_dienstleistung(dl.info, faehig) >= 3
        if dl.info.selbstauskunft_digital != online:
            out.append(
                (
                    "widerspruch_selbstauskunft",
                    dl.info.id,
                    None,
                    e_ids,
                    {"name": dl.name, "selbstauskunft": dl.info.selbstauskunft_digital, "online": online},
                )
            )
        zuletzt = dl.bearbeitet_am or dl.erstellt_am
        if zuletzt.tzinfo is None:
            zuletzt = zuletzt.replace(tzinfo=UTC)
        if heute - zuletzt > timedelta(days=VERALTET_NACH_TAGEN):
            out.append(
                (
                    "veraltet",
                    dl.info.id,
                    None,
                    e_ids,
                    {"name": dl.name, "zuletzt_bearbeitet": zuletzt.date().isoformat()},
                )
            )
        fehlend = [
            name
            for name, ok in (
                ("Beschreibung", dl.hat_beschreibung),
                ("Kosten", dl.hat_kosten),
                ("Unterlagen", dl.hat_unterlagen),
                ("Bearbeitungsdauer", dl.hat_bearbeitungsdauer),
            )
            if not ok
        ]
        if fehlend:
            out.append(("unvollstaendig", dl.info.id, None, e_ids, {"name": dl.name, "fehlt": fehlend}))

    for key, row in rows.items():
        dls = [snapshot.dienstleistungen[i] for i in row.dienstleistung_ids]
        portal_online = any(d.info.online for d in dls)
        gemeldet = [e for e in eigen.get(key, []) if e.url]
        if portal_online and not gemeldet:
            out.append(("nicht_gemeldet", None, key, row.einrichtung_ids, {}))
        if gemeldet and not portal_online:
            out.append(("nicht_verlinkt", None, key, row.einrichtung_ids, {"pvog_url": gemeldet[0].url}))
        for entry in gemeldet:
            if entry.online_ok is False:
                out.append(("dienst_defekt", None, key, row.einrichtung_ids, {"url": entry.url}))
    return out


def priorisierung(rows: dict[str, MartRow]) -> list[tuple]:
    """(leika_schluessel, kategorie, rang, details) für Leistungen der Grundgesamtheit unter Stufe 3."""
    out = []
    for key, row in rows.items():
        e = row.ergebnis
        if not row.in_grundgesamtheit or e.reifegrad >= 3:
            continue
        if row.sdg_relevant:
            out.append((key, "sdg_pflicht", 1, {"reifegrad": e.reifegrad}))
        elif e.online_inkl_uebergeordnet:
            out.append((key, "quick_win", 2, {"reifegrad": e.reifegrad, "verfuegbar_unter": e.online_url}))
        elif e.reifegrad <= 1:
            out.append((key, "kommunale_luecke", 3, {"reifegrad": e.reifegrad}))
    return out


def run_transform(
    conn: psycopg.Connection,
    stichtag: date,
    ars: str,
    benchmark: Sequence[str],
    kommunal: Sequence[str],
    modus: str,
    eigene_hosts: Sequence[str],
) -> dict[str, int]:
    snapshot = read_snapshot(conn, stichtag, ars, eigene_hosts)
    rows = bewerte(snapshot, ars, kommunal, modus)
    eltern = dict(conn.execute("SELECT optigov_id, uebergeordnet_id FROM core.einrichtung").fetchall())
    vor30 = conn.execute(
        "SELECT count(*) > 0, array_agg(leika_schluessel) FILTER (WHERE online_eigen) "
        "FROM mart.leistung_reifegrad_tag WHERE stichtag = %s",
        (stichtag - timedelta(days=30),),
    ).fetchone()
    vor_30_tagen = set(vor30[1] or []) if vor30 and vor30[0] else None

    for table in ("mart.leistung_reifegrad_tag", "mart.kpi_tag", "mart.qualitaet_befund", "mart.priorisierung"):
        conn.execute(f"DELETE FROM {table} WHERE stichtag = %s", (stichtag,))

    with conn.cursor().copy(
        "COPY mart.leistung_reifegrad_tag (stichtag, leika_schluessel, bezeichnung, reifegrad, reifegrad_version, "
        "in_grundgesamtheit, angeboten, online_eigen, online_inkl_uebergeordnet, online_url, online_termin, "
        "efa_nachnutzung, im_pvog_gemeldet, pvog_online_ok, selbstauskunft_digital, sdg_relevant, ozg_themenfeld, "
        "ozg_themenfeld_label, leistungsadressat, einrichtung_ids, dienstleistung_ids) FROM STDIN"
    ) as copy:
        for key, r in rows.items():
            e, lst = r.ergebnis, r.leistung
            copy.write_row(
                (
                    stichtag,
                    key,
                    _bezeichnung(r, snapshot),
                    e.reifegrad,
                    REIFEGRAD_VERSION,
                    r.in_grundgesamtheit,
                    e.angeboten,
                    e.online_eigen,
                    e.online_inkl_uebergeordnet,
                    e.online_url,
                    e.online_termin,
                    e.efa_nachnutzung,
                    e.im_pvog_gemeldet,
                    e.pvog_online_ok,
                    e.selbstauskunft_digital,
                    r.sdg_relevant,
                    lst.ozg_themenfeld if lst else None,
                    lst.ozg_themenfeld_label if lst else None,
                    lst.leistungsadressat if lst else [],
                    r.einrichtung_ids,
                    r.dienstleistung_ids,
                )
            )

    kpis = kennzahlen(rows, snapshot, ars, benchmark, eltern, vor_30_tagen)
    with conn.cursor().copy(
        "COPY mart.kpi_tag (stichtag, kpi, dimension, zaehler, nenner, oeffentlich) FROM STDIN"
    ) as copy:
        for kpi, dim, zaehler, nenner, public in kpis:
            copy.write_row((stichtag, kpi, dim, zaehler, nenner, public))

    befunde = qualitaetsbefunde(rows, snapshot, ars)
    for befund, dl_id, key, e_ids, details in befunde:
        conn.execute(
            "INSERT INTO mart.qualitaet_befund (stichtag, befund, dienstleistung_id, leika_schluessel, "
            "einrichtung_ids, details) VALUES (%s, %s, %s, %s, %s, %s)",
            (stichtag, befund, dl_id, key, e_ids, Jsonb(details)),
        )
    prio = priorisierung(rows)
    for key, kategorie, rang, details in prio:
        conn.execute(
            "INSERT INTO mart.priorisierung (stichtag, leika_schluessel, kategorie, rang, details) "
            "VALUES (%s, %s, %s, %s, %s)",
            (stichtag, key, kategorie, rang, Jsonb(details)),
        )
    run_data_tests(conn, stichtag)
    return {"leistungen": len(rows), "kpis": len(kpis), "befunde": len(befunde), "priorisierung": len(prio)}


class DataTestError(RuntimeError):
    pass


DATA_TESTS = {
    "Quoten liegen zwischen 0 und 1": (
        "SELECT count(*) FROM mart.kpi_tag WHERE stichtag=%s AND wert IS NOT NULL AND (wert < 0 OR wert > 1)"
    ),
    "Reifegradverteilung ergibt die Grundgesamtheit": (
        "SELECT count(*) FROM (SELECT sum(zaehler) s, max(nenner) n FROM mart.kpi_tag "
        "WHERE stichtag=%s AND kpi='reifegrad') x WHERE x.s <> x.n"
    ),
    "Online-Leistungen haben Stufe >= 3": (
        "SELECT count(*) FROM mart.leistung_reifegrad_tag WHERE stichtag=%s AND online_eigen AND reifegrad < 3"
    ),
    "Grundgesamtheit ist nicht leer": (
        "SELECT CASE WHEN count(*) FILTER (WHERE in_grundgesamtheit) = 0 THEN 1 ELSE 0 END "
        "FROM mart.leistung_reifegrad_tag WHERE stichtag=%s"
    ),
}


def run_data_tests(conn: psycopg.Connection, stichtag: date) -> None:
    failed = [name for name, sql in DATA_TESTS.items() if conn.execute(sql, (stichtag,)).fetchone()[0]]
    if failed:
        raise DataTestError("Datentests fehlgeschlagen: " + "; ".join(failed))
