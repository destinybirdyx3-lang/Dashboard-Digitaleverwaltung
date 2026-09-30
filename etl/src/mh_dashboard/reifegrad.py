"""Reifegradmodell je Leistung (Dokument 3, Abschnitt 3.3) – reine Funktionen ohne Datenbankbezug.

Stufen (versioniert über ``REIFEGRAD_VERSION``):
  0  Nicht beschrieben    – kein öffentlich sichtbares Angebot, nicht online
  1  Information          – öffentlich sichtbare Dienstleistung im Serviceportal
  2  Formular             – zusätzlich Formular zum Herunterladen / Formular-Link / Dokument
  3  Online-Antrag        – Onlinedienst oder Online-Formular mit URL, oder PVOG-Onlinedienst (Mülheim) ok
  4  Ende-zu-Ende (ind.)  – Stufe 3 + Online-Identifizierung + Online-Zahlung (falls Kosten)
                            + digitale Weiterverarbeitung (DMS-Anbindung) + BundID-Anbindung
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

REIFEGRAD_VERSION = "2026.1"

STUFEN = {
    0: "Nicht beschrieben",
    1: "Information",
    2: "Formular",
    3: "Online-Antrag",
    4: "Ende-zu-Ende",
}

# Wertebereiche von optiGov sind noch nicht dokumentiert (offene Frage 2) – konservative Heuristik.
_KEINE_IDENTIFIZIERUNG = {"", "0", "00", "kein", "keins", "keine", "none", "ohne"}
_ONLINE_ZAHLUNG = ("online", "epay", "e-pay", "pmpayment", "paypal", "giropay", "kreditkarte", "karte", "sepa")
FLAECHENDECKEND_UEBERGREIFEND = {"landesweit flächendeckend", "bundesweit flächendeckend"}


def identifizierung_online(vertrauensniveau: str | None) -> bool:
    return (vertrauensniveau or "").strip().lower() not in _KEINE_IDENTIFIZIERUNG


def zahlung_online(zahlungsweise: str | None) -> bool:
    value = (zahlungsweise or "").lower()
    return any(token in value for token in _ONLINE_ZAHLUNG)


def ist_kommunal(typisierung: Iterable[str], kommunal: Sequence[str]) -> bool:
    return any(t.strip() in kommunal for t in typisierung)


@dataclass(frozen=True)
class OnlineZugang:
    url: str | None
    eigener_dienst: bool | None
    vertrauensniveau: str | None = None
    zahlungsweise: str | None = None


@dataclass(frozen=True)
class DienstleistungInfo:
    id: int
    aktuell_sichtbar: bool
    selbstauskunft_digital: bool
    anzahl_formular_downloads: int
    hat_kosten: bool
    hat_online_termin: bool
    zugaenge: tuple[OnlineZugang, ...] = ()

    @property
    def online(self) -> bool:
        return any(z.url for z in self.zugaenge)


@dataclass(frozen=True)
class Faehigkeiten:
    bund_id: bool = False
    dms_d3: bool = False


def stufe_dienstleistung(dl: DienstleistungInfo, faehigkeiten: Faehigkeiten) -> int:
    if not dl.aktuell_sichtbar:
        return 0
    if dl.online:
        if _ende_zu_ende(dl, faehigkeiten):
            return 4
        return 3
    if dl.anzahl_formular_downloads > 0:
        return 2
    return 1


def _ende_zu_ende(dl: DienstleistungInfo, f: Faehigkeiten) -> bool:
    if not (f.bund_id and f.dms_d3):
        return False
    for zugang in dl.zugaenge:
        if not zugang.url or not identifizierung_online(zugang.vertrauensniveau):
            continue
        if dl.hat_kosten and not zahlung_online(zugang.zahlungsweise):
            continue
        return True
    return False


@dataclass(frozen=True)
class PvogInfo:
    url: str
    online_ok: bool | None
    flaechendeckung: str | None = None
    eigener_dienst: bool | None = None


@dataclass
class LeistungErgebnis:
    reifegrad: int
    angeboten: bool
    online_eigen: bool
    online_inkl_uebergeordnet: bool
    online_url: str | None
    efa_nachnutzung: bool | None
    im_pvog_gemeldet: bool
    pvog_online_ok: bool | None
    selbstauskunft_digital: bool | None
    online_termin: bool
    dienstleistung_stufen: dict[int, int] = field(default_factory=dict)


def _pvog_ok(entries: Sequence[PvogInfo]) -> list[PvogInfo]:
    return [e for e in entries if e.url and e.online_ok is not False]


def bewerte_leistung(
    dienstleistungen: Sequence[DienstleistungInfo],
    pvog_eigen: Sequence[PvogInfo],
    pvog_uebergeordnet: Sequence[PvogInfo],
    faehigkeiten: Faehigkeiten,
) -> LeistungErgebnis:
    sichtbar = [d for d in dienstleistungen if d.aktuell_sichtbar]
    stufen = {d.id: stufe_dienstleistung(d, faehigkeiten) for d in sichtbar}
    reifegrad = max(stufen.values(), default=0)

    eigen_ok = _pvog_ok(pvog_eigen)
    if eigen_ok and reifegrad < 3:
        reifegrad = 3  # online laut PVOG, auch wenn im Portal (noch) nicht verlinkt

    online_eigen = reifegrad >= 3
    online_inkl = online_eigen or bool(_pvog_ok(pvog_uebergeordnet))

    zugaenge = [z for d in sichtbar for z in d.zugaenge if z.url]
    online_url = next((z.url for z in zugaenge), None) or next((e.url for e in eigen_ok), None)
    if online_url is None and online_inkl:
        online_url = next((e.url for e in _pvog_ok(pvog_uebergeordnet)), None)

    efa: bool | None = None
    if online_eigen:
        efa = any(z.eigener_dienst is False for z in zugaenge) or any(
            (e.flaechendeckung or "") in FLAECHENDECKEND_UEBERGREIFEND or e.eigener_dienst is False for e in eigen_ok
        )

    gemeldet = [e for e in pvog_eigen if e.url]
    pvog_status: bool | None = None
    if gemeldet:
        pvog_status = all(e.online_ok is not False for e in gemeldet)

    return LeistungErgebnis(
        reifegrad=reifegrad,
        angeboten=bool(sichtbar),
        online_eigen=online_eigen,
        online_inkl_uebergeordnet=online_inkl,
        online_url=online_url,
        efa_nachnutzung=efa,
        im_pvog_gemeldet=bool(gemeldet),
        pvog_online_ok=pvog_status,
        selbstauskunft_digital=any(d.selbstauskunft_digital for d in sichtbar) if sichtbar else None,
        online_termin=any(d.hat_online_termin for d in sichtbar),
        dienstleistung_stufen=stufen,
    )
