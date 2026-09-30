"""Synthetische Demodaten im exakten Format der drei Schnittstellen.

Die Daten laufen durch dieselben Parser, Validierungen und Ladefunktionen wie im Echtbetrieb. Sie sind
eindeutig als Demo erkennbar: LeiKa-Schlüssel beginnen mit ``00``, alle URLs nutzen ``.example``-Domains,
Vergleichskommunen heißen „Vergleichskommune A/B/C“, und ``raw.quelle_stand.demo`` ist gesetzt.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

DEMO_HOSTS = ("muelheim.example",)
ARS_DEMO_NAMEN = {
    "051130000000": "Vergleichskommune A",
    "051120000000": "Vergleichskommune B",
    "051190000000": "Vergleichskommune C",
}

# (Leistung, OZG-Themenfeld, Adressat, SDG-relevant, Typisierung)
KATALOG: list[tuple[str, str, str, bool, str]] = [
    ("Wohnsitz anmelden", "ein_auswanderung", "001", True, "3"),
    ("Wohnsitz abmelden", "ein_auswanderung", "001", True, "3"),
    ("Meldebescheinigung beantragen", "querschnittsleistungen", "001", False, "3"),
    ("Personalausweis beantragen", "querschnittsleistungen", "001", True, "3"),
    ("Reisepass beantragen", "mobilitaet_reisen", "001", False, "3"),
    ("Führungszeugnis beantragen", "recht_ordnung", "001", False, "1"),
    ("Hundesteuer anmelden", "steuern_zoll", "001", False, "6"),
    ("Hundesteuer abmelden", "steuern_zoll", "001", False, "6"),
    ("Zweitwohnungsteuer erklären", "steuern_zoll", "001", False, "6"),
    ("Gewerbe anmelden", "unternehmensfuehrung_entwicklung", "002", True, "3"),
    ("Gewerbe ummelden", "unternehmensfuehrung_entwicklung", "002", True, "3"),
    ("Gewerbe abmelden", "unternehmensfuehrung_entwicklung", "002", True, "3"),
    ("Gaststättenerlaubnis beantragen", "unternehmensfuehrung_entwicklung", "002", True, "5"),
    ("Sondernutzung öffentlicher Verkehrsflächen beantragen", "mobilitaet_reisen", "002", False, "5"),
    ("Baugenehmigung beantragen", "bauen_wohnen", "001", True, "5"),
    ("Bauvoranfrage stellen", "bauen_wohnen", "001", False, "5"),
    ("Abgeschlossenheitsbescheinigung beantragen", "bauen_wohnen", "001", False, "3"),
    ("Wohngeld beantragen", "bauen_wohnen", "001", False, "2/3"),
    ("Wohnberechtigungsschein beantragen", "bauen_wohnen", "001", False, "5"),
    ("Bewohnerparkausweis beantragen", "mobilitaet_reisen", "001", False, "3"),
    ("Parkerleichterung für Menschen mit Behinderung beantragen", "mobilitaet_reisen", "001", False, "3"),
    ("Fahrzeug zulassen", "mobilitaet_reisen", "001", True, "3"),
    ("Fahrzeug außer Betrieb setzen", "mobilitaet_reisen", "001", True, "3"),
    ("Fahrerlaubnis erstmalig beantragen", "mobilitaet_reisen", "001", True, "3"),
    ("Internationalen Führerschein beantragen", "mobilitaet_reisen", "001", False, "3"),
    ("Kita-Platz beantragen", "familie_kind", "001", False, "6"),
    ("Elternbeitrag Kindertagesbetreuung festsetzen", "familie_kind", "001", False, "6"),
    ("Unterhaltsvorschuss beantragen", "familie_kind", "001", False, "3"),
    ("Beistandschaft beantragen", "familie_kind", "001", False, "3"),
    ("Geburt anzeigen", "familie_kind", "001", True, "3"),
    ("Geburtsurkunde beantragen", "familie_kind", "001", True, "3"),
    ("Eheschließung anmelden", "familie_kind", "001", False, "3"),
    ("Eheurkunde beantragen", "familie_kind", "001", True, "3"),
    ("Sterbeurkunde beantragen", "familie_kind", "001", False, "3"),
    ("Kirchenaustritt erklären", "querschnittsleistungen", "001", False, "4"),
    ("Schulanmeldung Grundschule", "bildung", "001", False, "5"),
    ("Schülerfahrkosten erstatten", "bildung", "001", False, "5"),
    ("Bildungs- und Teilhabeleistungen beantragen", "bildung", "001", False, "3"),
    ("Musikschule anmelden", "bildung", "001", False, "6"),
    ("Volkshochschulkurs buchen", "bildung", "001", False, "6"),
    ("Ehrenamtskarte beantragen", "engagement_hobby", "001", False, "5"),
    ("Fischereischein beantragen", "engagement_hobby", "001", False, "5"),
    ("Veranstaltung anmelden", "engagement_hobby", "002", False, "5"),
    ("Sportstätte buchen", "engagement_hobby", "001", False, "6"),
    ("Aufenthaltstitel verlängern", "ein_auswanderung", "001", True, "3"),
    ("Einbürgerung beantragen", "ein_auswanderung", "001", False, "3"),
    ("Verpflichtungserklärung abgeben", "ein_auswanderung", "001", False, "3"),
    ("Hilfe zum Lebensunterhalt beantragen", "arbeit_ruhestand", "001", False, "3"),
    ("Grundsicherung im Alter beantragen", "arbeit_ruhestand", "001", False, "3"),
    ("Schwerbehindertenausweis beantragen", "gesundheit", "001", False, "5"),
    ("Blindengeld beantragen", "gesundheit", "001", False, "5"),
    ("Belehrung nach Infektionsschutzgesetz", "gesundheit", "001", False, "3"),
    ("Trinkwasseruntersuchung anzeigen", "gesundheit", "002", False, "3"),
    ("Sperrmüll anmelden", "umwelt", "001", False, "6"),
    ("Baumfällung beantragen", "umwelt", "001", False, "6"),
    ("Abfallbehälter ändern", "umwelt", "001", False, "6"),
    ("Grundstücksentwässerung genehmigen", "umwelt", "001", False, "5"),
    ("Waffenbesitzkarte beantragen", "recht_ordnung", "001", False, "3"),
    ("Fundsache melden", "recht_ordnung", "001", False, "5"),
    ("Lärmschutz-Ausnahme beantragen", "recht_ordnung", "002", False, "5"),
    ("Anwohnerbeschwerde Ordnungsamt melden", "recht_ordnung", "001", False, "6"),
    ("Hebammenhilfe Förderung beantragen", "forschung_foerderung", "001", False, "6"),
    ("Wirtschaftsförderung Zuschuss beantragen", "forschung_foerderung", "002", False, "6"),
    ("Elterngeld beantragen", "familie_kind", "001", False, "2"),
    ("BAföG beantragen", "bildung", "001", False, "2"),
    ("Rentenauskunft anfordern", "arbeit_ruhestand", "001", False, "1"),
]

EINRICHTUNGEN = [
    (1, "Dezernat I – Bürgerservice und Ordnung", None),
    (2, "Dezernat II – Bauen und Umwelt", None),
    (3, "Dezernat III – Jugend, Schule, Soziales", None),
    (4, "Dezernat IV – Finanzen", None),
    (11, "Bürgeramt", 1),
    (12, "Standesamt", 1),
    (13, "Ordnungsamt", 1),
    (14, "Straßenverkehrsamt", 1),
    (15, "Ausländerbehörde", 1),
    (21, "Bauaufsicht", 2),
    (22, "Umweltamt", 2),
    (23, "Wohnungsamt", 2),
    (31, "Jugendamt", 3),
    (32, "Schulamt", 3),
    (33, "Sozialamt", 3),
    (34, "Gesundheitsamt", 3),
    (35, "Kultur- und Bildungseinrichtungen", 3),
    (41, "Steueramt", 4),
    (42, "Wirtschaftsförderung", 4),
]
THEMA_EINRICHTUNG = {
    "ein_auswanderung": 15,
    "querschnittsleistungen": 11,
    "mobilitaet_reisen": 14,
    "recht_ordnung": 13,
    "steuern_zoll": 41,
    "unternehmensfuehrung_entwicklung": 42,
    "bauen_wohnen": 21,
    "familie_kind": 31,
    "bildung": 32,
    "engagement_hobby": 35,
    "arbeit_ruhestand": 33,
    "gesundheit": 34,
    "umwelt": 22,
    "forschung_foerderung": 42,
}


@dataclass
class DemoLeistung:
    key: str
    name: str
    themenfeld: str
    adressat: str
    sdg: bool
    typisierung: str
    dl_id: int | None
    beschrieben_seit: date | None
    download: bool
    online_seit: date | None
    online_eigen_host: bool
    pvog_gemeldet: bool
    pvog_ok: bool
    uebergeordnet_online: bool
    termin: bool
    widerspruch: bool
    zuletzt_bearbeitet: date
    vollstaendig: bool
    link_defekt: bool
    leika_zugeordnet: bool
    kosten: bool
    zahlung_online: bool
    identifizierung: bool


class DemoWelt:
    """Deterministische Demowelt; ``quellen(stichtag)`` liefert den Stand zu einem Stichtag."""

    def __init__(self, heute: date, seed: int = 4711) -> None:
        self.heute = heute
        rnd = random.Random(seed)
        self.leistungen: list[DemoLeistung] = []
        verrichtungen = ["", " (Änderung)", " (Verlängerung)"]
        dl_id = 100
        for idx, (name, thema, adressat, sdg, typ) in enumerate(KATALOG):
            for v_idx, suffix in enumerate(verrichtungen):
                if v_idx and rnd.random() < 0.55:
                    continue
                key = f"00{idx:04d}{v_idx:02d}{rnd.randint(0, 999999):06d}"
                kommunal = typ in ("2/3", "3", "5", "6")
                angeboten = kommunal and rnd.random() < 0.9 or (not kommunal and rnd.random() < 0.3)
                start = heute - timedelta(days=rnd.randint(400, 1400))
                online_seit = None
                if angeboten and rnd.random() < 0.62:
                    online_seit = heute - timedelta(days=int(rnd.betavariate(1.2, 1.6) * 1500))
                self.leistungen.append(
                    DemoLeistung(
                        key=key,
                        name=name + suffix,
                        themenfeld=thema,
                        adressat=adressat,
                        sdg=sdg,
                        typisierung=typ,
                        dl_id=(dl_id := dl_id + 1) if angeboten else None,
                        beschrieben_seit=start if angeboten else None,
                        download=rnd.random() < 0.6,
                        online_seit=online_seit,
                        online_eigen_host=rnd.random() < 0.55,
                        pvog_gemeldet=rnd.random() < 0.85,
                        pvog_ok=rnd.random() < 0.93,
                        uebergeordnet_online=rnd.random() < 0.25,
                        termin=rnd.random() < 0.35,
                        widerspruch=rnd.random() < 0.08,
                        zuletzt_bearbeitet=heute - timedelta(days=rnd.randint(3, 700)),
                        vollstaendig=rnd.random() < 0.7,
                        link_defekt=rnd.random() < 0.06,
                        leika_zugeordnet=rnd.random() < 0.95,
                        kosten=rnd.random() < 0.5,
                        zahlung_online=rnd.random() < 0.6,
                        identifizierung=rnd.random() < 0.4,
                    )
                )
        # ein Onlinedienst, der nur im PVOG gemeldet, aber nicht im Portal verlinkt ist
        self.nur_pvog = {x.key for x in self.leistungen if x.dl_id and not x.online_seit and rnd.random() < 0.08}
        self._rnd_seed = seed

    # ----------------------------------------------------------------- optiGov
    def optigov(self, t: date) -> dict[str, Any]:
        ts = datetime.combine(t, datetime.min.time(), tzinfo=UTC)
        dls, onlinedienste, formulare = [], [], []
        for x in self.leistungen:
            if not x.dl_id or not x.beschrieben_seit or x.beschrieben_seit > t:
                continue
            online = x.online_seit is not None and x.online_seit <= t
            od_ids = [x.dl_id * 10] if online else []
            if online:
                host = DEMO_HOSTS[0] if x.online_eigen_host else "efa.land-nrw.example"
                onlinedienste.append(
                    {
                        "id": x.dl_id * 10,
                        "externe_id": None,
                        "name": f"Online-Antrag: {x.name}",
                        "typ": "antrag",
                        "url": f"https://{host}/antrag/{x.key}",
                        "vertrauensniveau": "substanziell" if x.identifizierung else "keins",
                        "zahlungsweise": "epayment" if x.zahlung_online else "keine",
                        "erstellt": x.online_seit.isoformat() + "T08:00:00+00:00",
                        "bearbeitet": None,
                        "formular": None,
                        "dienstleistungen": {"totalCount": 1, "edges": [{"node": {"id": x.dl_id}}]},
                    }
                )
            bearbeitet = min(x.zuletzt_bearbeitet, t)
            dls.append(
                {
                    "id": x.dl_id,
                    "externe_id": None,
                    "leistungsname": x.name,
                    "leistungsbezeichnung": x.name,
                    "digitalisiert": online != x.widerspruch,
                    "oeffentlich_anzeigen": True,
                    "in_listen_anzeigen": True,
                    "sichtbar_von_tag": None,
                    "sichtbar_von_monat": None,
                    "sichtbar_von_jahr": None,
                    "sichtbar_bis_tag": None,
                    "sichtbar_bis_monat": None,
                    "sichtbar_bis_jahr": None,
                    "erstellt": x.beschrieben_seit.isoformat() + "T09:00:00+00:00",
                    "bearbeitet": bearbeitet.isoformat() + "T10:00:00+00:00",
                    "hat_kurztext": f"Kurzbeschreibung: {x.name}.",
                    "kosten": "Gebühr laut Satzung." if x.kosten and x.vollstaendig else None,
                    "bearbeitungsdauer": "ca. 2 Wochen" if x.vollstaendig else None,
                    "unterlagen": "Personalausweis" if x.vollstaendig else None,
                    "leikaschluessel": _conn([{"schluessel": x.key}] if x.leika_zugeordnet else []),
                    "infodienst_dienstleistung": None,
                    "onlinedienste": _conn([{"id": i} for i in od_ids]),
                    "formulare": _conn([]),
                    "formulare_downloads": {"totalCount": 1 if x.download else 0},
                    "formulare_links": {"totalCount": 0},
                    "dokumente": {"totalCount": 0},
                    "terminvorlagen": _conn([{"id": x.dl_id, "intern": False}] if x.termin else []),
                    "einrichtungen": _conn([{"id": THEMA_EINRICHTUNG[x.themenfeld]}]),
                    "themenfelder": _conn([{"id": 1, "name": x.themenfeld.replace("_", " ").title()}]),
                    "kostenpunkte": {"totalCount": 1 if x.kosten else 0},
                    "links": _conn([{"id": x.dl_id, "erreichbar": not x.link_defekt}]),
                }
            )
        einrichtungen = [
            {
                "id": i,
                "name": n,
                "kurzbezeichnung": None,
                "oeffentlich_anzeigen": True,
                "einrichtungstyp": {"id": 1 if p is None else 2, "name": "Dezernat" if p is None else "Amt"},
                "uebergeordnete_einrichtung": {"id": p} if p else None,
            }
            for i, n, p in EINRICHTUNGEN
        ]
        leika = [
            {
                "id": i,
                "schluessel": x.key,
                "bezeichnung": x.name,
                "bezeichnung2": x.name,
                "leistungsgruppierung": None,
                "verrichtung": None,
                "typ": x.typisierung,
                "leistungstyp": "lov",
                "sdg_code": "1030300" if x.sdg else None,
                "sdg_informationsbereich": None,
                "status_code": 1,
                "status_bezeichnung": "freigegeben",
                "portalverbund_lagen_codes": None,
                "bearbeitet": ts.isoformat(),
                "dienstleistungen": _conn([{"id": x.dl_id}] if x.dl_id else []),
            }
            for i, x in enumerate(self.leistungen, start=1)
        ]
        faehigkeiten = {
            "id": 1,
            "name": "Stadt Mülheim an der Ruhr (Demo)",
            "bundesland": "Nordrhein-Westfalen",
            "bund_id": {"id": 1, "umgebung": "produktiv", "ablaufdatum": "2027-12-31T00:00:00+00:00"},
            "muk": {"id": 1, "umgebung": "produktiv"},
            "modulkonfiguration": {
                "buergerservice": True,
                "meet": True,
                "meet_formulare": False,
                "warteschlange": True,
                "dms_d3": True,
                "muk": True,
            },
            "gebiete": _conn([{"name": "Mülheim an der Ruhr", "schluessel": "051170000000"}]),
        }
        return {
            "dienstleistungen": dls,
            "onlinedienste": onlinedienste,
            "formulare": formulare,
            "einrichtungen": einrichtungen,
            "leikaschluessel": leika,
            "faehigkeiten": faehigkeiten,
        }

    # ----------------------------------------------------------------- FIM
    def fim(self) -> list[dict[str, Any]]:
        return [
            {
                "leistungsschluessel": x.key,
                "title": x.name,
                "leistungstyp": "lov",
                "typisierung": [x.typisierung],
                "leistungsadressat": [x.adressat],
                "ozg": [
                    {
                        "leistungsschluessel": x.key,
                        "id": str(10000 + i),
                        "leistung": x.name,
                        "themenfeld": x.themenfeld,
                        "themenfeld_label": x.themenfeld,
                        "vollzugsbehoerden": [],
                    }
                ],
                "sdg": ["1030300"] if x.sdg else [],
                "klassifizierung": [],
                "freigabe_status": 6,
                "geaendert_datum_zeit": "2026-01-15T10:00:00",
            }
            for i, x in enumerate(self.leistungen)
        ]

    # ----------------------------------------------------------------- PVOG
    def pvog_csv(self, t: date, ars: str, sicht: str) -> str:
        rnd = random.Random(f"{self._rnd_seed}-{ars}-{sicht}")
        rows = []
        stand = (t - timedelta(days=1)).isoformat()
        name = "Mülheim an der Ruhr" if ars == "051170000000" else ARS_DEMO_NAMEN.get(ars, "Vergleichskommune")
        for x in self.leistungen:
            if ars == "051170000000":
                online = x.online_seit is not None and x.online_seit <= t and x.pvog_gemeldet
                online = online or x.key in self.nur_pvog
                ok = x.pvog_ok
                if not online and sicht == "inkl_uebergeordnet" and x.uebergeordnet_online:
                    online, ok = True, True
                host = DEMO_HOSTS[0] if x.online_eigen_host else "efa.land-nrw.example"
            else:
                quote = {"051130000000": 0.55, "051120000000": 0.42, "051190000000": 0.37}.get(ars, 0.4)
                online = x.typisierung in ("2/3", "3", "5", "6") and rnd.random() < quote
                ok = rnd.random() < 0.95
                host = "portal.vergleich.example"
            if not online:
                continue
            flaeche = "landesweit flächendeckend" if host.startswith("efa.") else "in mind. einer Kommune verfügbar"
            rows.append(
                {
                    "leika_key": x.key,
                    "leika_name": x.name,
                    "ars": ars,
                    "ars_name": name,
                    "ars_federal_state": "05",
                    "bundesland": "Nordrhein-Westfalen",
                    "leika_bezeichnung": x.name,
                    "ozgid": "",
                    "ozg_bezeichnung": "",
                    "url": f"https://{host}/antrag/{x.key}",
                    "online_status": "ok" if ok else "nicht ok",
                    "aktiv": "ja",
                    "art_flaechendeckung": flaeche,
                    "begruendung_nicht_beruecksichtigt": "",
                    "export_datum": stand,
                    "datenstand_pvog_import": stand,
                }
            )
        buffer = io.StringIO()
        fields = [
            "leika_key",
            "leika_name",
            "ars",
            "ars_name",
            "ars_federal_state",
            "bundesland",
            "leika_bezeichnung",
            "ozgid",
            "ozg_bezeichnung",
            "url",
            "online_status",
            "aktiv",
            "art_flaechendeckung",
            "begruendung_nicht_beruecksichtigt",
            "export_datum",
            "datenstand_pvog_import",
        ]
        writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
        return buffer.getvalue()


def _conn(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    return {"totalCount": len(nodes), "edges": [{"node": n} for n in nodes]}


def historie(heute: date) -> list[date]:
    """Stichtage für die Demo-Historie: 12 Monate wöchentlich, letzte 35 Tage täglich, Monatsenden."""
    tage = {heute - timedelta(days=d) for d in range(0, 35)}
    tage |= {heute - timedelta(weeks=w) for w in range(5, 53)}
    tage |= {heute - timedelta(days=365)}
    return sorted(tage)
