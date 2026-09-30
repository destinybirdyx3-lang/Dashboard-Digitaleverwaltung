from __future__ import annotations

from mh_dashboard.reifegrad import (
    DienstleistungInfo,
    Faehigkeiten,
    OnlineZugang,
    PvogInfo,
    bewerte_leistung,
    ist_kommunal,
    stufe_dienstleistung,
)

KEINE = Faehigkeiten()
VOLL = Faehigkeiten(bund_id=True, dms_d3=True)


def dl(**kw) -> DienstleistungInfo:
    base = dict(
        id=1,
        aktuell_sichtbar=True,
        selbstauskunft_digital=False,
        anzahl_formular_downloads=0,
        hat_kosten=False,
        hat_online_termin=False,
        zugaenge=(),
    )
    return DienstleistungInfo(**(base | kw))


def test_stufen_der_dienstleistung() -> None:
    assert stufe_dienstleistung(dl(aktuell_sichtbar=False), KEINE) == 0
    assert stufe_dienstleistung(dl(), KEINE) == 1
    assert stufe_dienstleistung(dl(anzahl_formular_downloads=2), KEINE) == 2
    online = (OnlineZugang("https://a.example", True, "substanziell", "epayment"),)
    assert stufe_dienstleistung(dl(zugaenge=online), KEINE) == 3
    assert stufe_dienstleistung(dl(zugaenge=online), VOLL) == 4


def test_ende_zu_ende_braucht_identifizierung_und_zahlung() -> None:
    ohne_id = (OnlineZugang("https://a.example", True, "keins", "epayment"),)
    assert stufe_dienstleistung(dl(zugaenge=ohne_id), VOLL) == 3
    ohne_zahlung = (OnlineZugang("https://a.example", True, "hoch", "bar vor Ort"),)
    assert stufe_dienstleistung(dl(zugaenge=ohne_zahlung, hat_kosten=True), VOLL) == 3
    assert stufe_dienstleistung(dl(zugaenge=ohne_zahlung, hat_kosten=False), VOLL) == 4


def test_pvog_hebt_auf_stufe_3_und_nicht_ok_zaehlt_nicht() -> None:
    e = bewerte_leistung([dl()], [PvogInfo("https://efa.example", True, "landesweit flächendeckend")], [], KEINE)
    assert e.reifegrad == 3 and e.online_eigen and e.efa_nachnutzung and e.im_pvog_gemeldet
    e = bewerte_leistung([dl()], [PvogInfo("https://x.example", False)], [], KEINE)
    assert e.reifegrad == 1 and not e.online_eigen and e.pvog_online_ok is False


def test_uebergeordnet_online_ist_nicht_eigen() -> None:
    e = bewerte_leistung([], [], [PvogInfo("https://land.example", True)], KEINE)
    assert e.reifegrad == 0 and not e.online_eigen and e.online_inkl_uebergeordnet
    assert e.online_url == "https://land.example"


def test_bester_reifegrad_mehrerer_dienstleistungen() -> None:
    e = bewerte_leistung([dl(id=1), dl(id=2, anzahl_formular_downloads=1)], [], [], KEINE)
    assert e.reifegrad == 2 and e.dienstleistung_stufen == {1: 1, 2: 2}


def test_kommunal() -> None:
    assert ist_kommunal(["3"], ("3", "5")) and not ist_kommunal(["1", "2"], ("3", "5"))
