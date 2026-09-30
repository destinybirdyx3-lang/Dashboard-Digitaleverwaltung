from __future__ import annotations

from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from pydantic import ValidationError

from mh_dashboard.demo import DemoWelt
from mh_dashboard.sources.datahub import DatahubClient, parse_csv
from mh_dashboard.sources.fim import FimClient, parse_steckbrief
from mh_dashboard.sources.graphql_guard import QueryAllowlist
from mh_dashboard.sources.optigov import OptigovClient

CSV_KOMMA = (
    "leika_key,leika_name,ars,ars_name,url,online_status,aktiv,art_flaechendeckung,datenstand_pvog_import,ozgid\n"
    "99041006017000,Hundehaltung anmelden,051170000000,Mülheim,https://x.example/a,ok,ja,"
    "landesweit flächendeckend,2026-09-29,\n"
)


def test_pvog_csv_komma_und_semikolon() -> None:
    rows = parse_csv(CSV_KOMMA)
    assert rows[0].online_ok is True and rows[0].ozgid is None
    assert rows[0].datenstand_pvog_import == date(2026, 9, 29)
    rows2 = parse_csv("﻿" + CSV_KOMMA.replace(",", ";").replace("landesweit;", "landesweit,"))
    assert rows2[0].leika_key == "99041006017000"


def test_pvog_camelcase_spalten_werden_erkannt() -> None:
    rows = parse_csv("leikaKey;ars;onlineStatus;url\n99041006017000;051170000000;nicht ok;https://a.example\n")
    assert rows[0].online_ok is False


@pytest.mark.parametrize(
    "zeile",
    [
        "123;051170000000;ok;https://a",  # LeiKa zu kurz
        "99041006017000;0511;ok;https://a",  # ARS zu kurz
        "99041006017000;051170000000;kaputt;x",  # unbekannter Status
    ],
)
def test_pvog_ungueltige_zeilen(zeile: str) -> None:
    with pytest.raises(ValidationError):
        parse_csv("leika_key;ars;online_status;url\n" + zeile + "\n")


@respx.mock
def test_datahub_faellt_bei_413_auf_paginierung_zurueck() -> None:
    base = "https://dh.example/api"
    respx.get(f"{base}/public/v1/dash/open-pvog/051170000000/export").respond(413)
    respx.get(f"{base}/public/v1/dash/open-pvog/051170000000").respond(
        json={
            "content": [{"leika_key": "99041006017000", "ars": "051170000000", "url": "", "online_status": "ok"}],
            "page": {"totalPages": 1},
        }
    )
    rows = DatahubClient(base, httpx.Client()).open_pvog("051170000000", include_above=False)
    assert len(rows) == 1


def test_fim_parser_ist_tolerant_aber_verlangt_leika() -> None:
    s = parse_steckbrief(
        {
            "leistungsschluessel": ["99041006017000"],
            "title": "Hund",
            "typisierung": ["3"],
            "ozg": [{"id": 10, "themenfeld": "umwelt"}],
            "sdg": ["0000000", "1030300"],
            "klassifizierung": [{"list_uri": "urn:xoev-de:fim:codeliste:pvlagen", "value": "2100400"}],
        }
    )
    assert s and s.typisierung == ["3"] and s.ozg_themenfeld == "umwelt" and s.sdg_codes == ["1030300"]
    assert s.pv_lagen_codes == ["2100400"]
    assert parse_steckbrief({"title": "ohne Schlüssel"}) is None


@respx.mock
def test_fim_paginierung() -> None:
    route = respx.get("https://fim.example/api/v1/leistung-steckbriefe")
    route.side_effect = [
        httpx.Response(200, json={"items": [{"leistungsschluessel": "99041006017000"}] * 200, "total_count": 201}),
        httpx.Response(200, json={"items": [{"leistungsschluessel": "99041006017001"}], "total_count": 201}),
    ]
    assert len(list(FimClient("https://fim.example", httpx.Client()).steckbriefe())) == 201


@respx.mock
def test_optigov_client_paginiert_und_validiert(query_dir: Path) -> None:
    welt = DemoWelt(date(2026, 9, 30))
    alle = welt.optigov(date(2026, 9, 30))["dienstleistungen"]

    def antwort(request: httpx.Request) -> httpx.Response:
        import json

        v = json.loads(request.content)["variables"]
        seite = alle[v["offset"] : v["offset"] + v["limit"]]
        return httpx.Response(
            200,
            json={
                "data": {
                    "verwaltung": {"dienstleistungen": {"totalCount": len(alle), "edges": [{"node": n} for n in seite]}}
                }
            },
        )

    respx.post("http://guard.example/graphql").mock(side_effect=antwort)
    client = OptigovClient("http://guard.example/graphql", QueryAllowlist(query_dir), httpx.Client(), 1)
    assert len(client.dienstleistungen()) == len(alle)


@respx.mock
def test_optigov_unerwartetes_feld_bricht_ab(query_dir: Path) -> None:
    node = DemoWelt(date(2026, 9, 30)).optigov(date(2026, 9, 30))["onlinedienste"][0] | {"neu": 1}
    respx.post("http://guard.example/graphql").respond(
        json={"data": {"verwaltung": {"onlinedienste": {"totalCount": 1, "edges": [{"node": node}]}}}}
    )
    client = OptigovClient("http://guard.example/graphql", QueryAllowlist(query_dir), httpx.Client(), 1)
    with pytest.raises(ValidationError):
        client.onlinedienste()
