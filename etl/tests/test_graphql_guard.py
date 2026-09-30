from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from mh_dashboard.sources.graphql_guard import (
    GuardViolation,
    QueryAllowlist,
    check_response,
    check_variables,
    sha256_hex,
)


def test_allowlist_laedt_alle_freigegebenen_abfragen(query_dir: Path) -> None:
    allowlist = QueryAllowlist(query_dir)
    assert allowlist.operations == sorted(
        [
            "Dienstleistungen",
            "Einrichtungen",
            "Formulare",
            "Leikaschluessel",
            "Onlinedienste",
            "VerwaltungFaehigkeiten",
        ]
    )


def test_freigegebene_abfrage_wird_akzeptiert(query_dir: Path) -> None:
    allowlist = QueryAllowlist(query_dir)
    q = allowlist.get("Onlinedienste")
    allowlist.check_request(q.text, "Onlinedienste", {"verwaltung": 1, "limit": 100, "offset": 0})


@pytest.mark.parametrize(
    "query",
    [
        "mutation X { loescheDienstleistung(id: 1) }",
        "query X { buerger(id: 1) { name email } }",
        'query X { statistik(verwaltung: 1, datensatz: "antraege") { serien { name } } }',
        "query X { verwaltung(id: 1) { antraege { totalCount } } }",
        "query X { __schema { types { name } } }",
        "query X { dienstleistung(id: 1) { id } }",
    ],
)
def test_nicht_freigegebene_abfragen_werden_abgelehnt(query_dir: Path, query: str) -> None:
    with pytest.raises(GuardViolation):
        QueryAllowlist(query_dir).check_request(query, None, {})


def test_manipulierte_abfrage_wird_beim_laden_erkannt(query_dir: Path, tmp_path: Path) -> None:
    kopie = tmp_path / "queries"
    shutil.copytree(query_dir, kopie)
    datei = kopie / "02_onlinedienste.graphql"
    datei.write_text(datei.read_text().replace("zahlungsweise", "zahlungsweise\n          formular { id }"))
    with pytest.raises(GuardViolation, match="Hash"):
        QueryAllowlist(kopie)


def test_gesperrtes_feld_faellt_auch_mit_gueltigem_hash_auf(query_dir: Path, tmp_path: Path) -> None:
    kopie = tmp_path / "queries"
    kopie.mkdir()
    text = "query Boese($verwaltung: Int!) { verwaltung(id: $verwaltung) { ldap_zugang { password } } }\n"
    (kopie / "boese.graphql").write_text(text)
    (kopie / "allowlist.sha256").write_text(f"{sha256_hex(text)}  boese.graphql\n")
    with pytest.raises(GuardViolation, match="gesperrt"):
        QueryAllowlist(kopie)


def test_alias_kann_gesperrtes_feld_nicht_verstecken(query_dir: Path, tmp_path: Path) -> None:
    kopie = tmp_path / "queries"
    kopie.mkdir()
    text = "query Tarnung { verwaltung(id: 1) { harmlos: adressomat_token } }\n"
    (kopie / "t.graphql").write_text(text)
    (kopie / "allowlist.sha256").write_text(f"{sha256_hex(text)}  t.graphql\n")
    with pytest.raises(GuardViolation):
        QueryAllowlist(kopie)


@pytest.mark.parametrize(
    "variables", [{"limit": 1000}, {"limit": -1}, {"offset": -5}, {"x": {"a": 1}}, {"seit": "x" * 100}]
)
def test_variablen_grenzen(variables: dict) -> None:
    with pytest.raises(GuardViolation):
        check_variables(variables)


def test_antwort_mit_gesperrtem_schluessel_wird_verworfen() -> None:
    check_response({"data": {"verwaltung": {"onlinedienste": {"edges": [{"node": {"id": 1}}]}}}})
    with pytest.raises(GuardViolation):
        check_response({"verwaltung": {"edges": [{"node": {"buerger_email": "a@b.de"}}]}})
