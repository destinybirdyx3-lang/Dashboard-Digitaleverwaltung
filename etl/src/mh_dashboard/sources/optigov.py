"""Abruf der Angebotsdaten aus dem optiGov-Serviceportal – ausschließlich über den Guard-Proxy.

Es werden nur die freigegebenen Abfragen aus ``integration/optigov/queries`` gesendet. Antworten werden
mit Pydantic-Modellen (``extra="forbid"``) validiert: Unerwartete Felder führen zum Abbruch.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime
from typing import Any, Generic, TypeVar

import httpx
from pydantic import BaseModel, ConfigDict, Field

from .graphql_guard import QueryAllowlist, check_response
from .http import request

PAGE_SIZE = 100
FULL_SYNC_SINCE = "1970-01-01 00:00:00"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


N = TypeVar("N", bound=BaseModel)


class Edge(Strict, Generic[N]):
    node: N


class Connection(Strict, Generic[N]):
    totalCount: int | None = None  # noqa: N815 – Name aus dem GraphQL-Schema
    edges: list[Edge[N]] = Field(default_factory=list)

    @property
    def nodes(self) -> list[N]:
        return [edge.node for edge in self.edges]


class Count(Strict):
    totalCount: int  # noqa: N815


class IdNode(Strict):
    id: int


class LeikaRef(Strict):
    schluessel: str


class ThemenfeldRef(Strict):
    id: int
    name: str


class TerminvorlageRef(Strict):
    id: int
    intern: bool


class LinkRef(Strict):
    id: int
    erreichbar: bool | None = None


class InfodienstRef(Strict):
    leikaschluessel: str | None = None
    aktualisiert: datetime | None = None


class DienstleistungNode(Strict):
    id: int
    externe_id: int | None = None
    leistungsname: str
    leistungsbezeichnung: str
    digitalisiert: bool
    oeffentlich_anzeigen: bool
    in_listen_anzeigen: bool
    sichtbar_von_tag: int | None = None
    sichtbar_von_monat: int | None = None
    sichtbar_von_jahr: int | None = None
    sichtbar_bis_tag: int | None = None
    sichtbar_bis_monat: int | None = None
    sichtbar_bis_jahr: int | None = None
    erstellt: datetime
    bearbeitet: datetime | None = None
    hat_kurztext: str | None = None
    kosten: str | None = None
    bearbeitungsdauer: str | None = None
    unterlagen: str | None = None
    leikaschluessel: Connection[LeikaRef]
    infodienst_dienstleistung: InfodienstRef | None = None
    onlinedienste: Connection[IdNode]
    formulare: Connection[IdNode]
    formulare_downloads: Count
    formulare_links: Count
    dokumente: Count
    terminvorlagen: Connection[TerminvorlageRef]
    einrichtungen: Connection[IdNode]
    themenfelder: Connection[ThemenfeldRef]
    kostenpunkte: Count
    links: Connection[LinkRef]


class FormularRef(Strict):
    id: int


class OnlinedienstNode(Strict):
    id: int
    externe_id: int | None = None
    name: str
    typ: str
    url: str | None = None
    vertrauensniveau: str
    zahlungsweise: str
    erstellt: datetime
    bearbeitet: datetime | None = None
    formular: FormularRef | None = None
    dienstleistungen: Connection[IdNode]


class FormularServerRef(Strict):
    anbieter: str


class FormularNode(Strict):
    id: int
    titel: str
    url: str
    benoetigte_vertrauensstufe: str
    erstellt: datetime
    bearbeitet: datetime | None = None
    formularserver: FormularServerRef
    dienstleistungen: Connection[IdNode]


class EinrichtungstypRef(Strict):
    id: int
    name: str


class EinrichtungNode(Strict):
    id: int
    name: str
    kurzbezeichnung: str | None = None
    oeffentlich_anzeigen: bool
    einrichtungstyp: EinrichtungstypRef | None = None
    uebergeordnete_einrichtung: IdNode | None = None


class LeikaschluesselNode(Strict):
    id: int
    schluessel: str
    bezeichnung: str
    bezeichnung2: str
    leistungsgruppierung: str | None = None
    verrichtung: str | None = None
    typ: str | None = None
    leistungstyp: str | None = None
    sdg_code: str | None = None
    sdg_informationsbereich: str | None = None
    status_code: int | None = None
    status_bezeichnung: str | None = None
    portalverbund_lagen_codes: str | None = None
    bearbeitet: datetime | None = None
    dienstleistungen: Connection[IdNode]


class BundIdRef(Strict):
    id: int
    umgebung: str
    ablaufdatum: datetime


class MukRef(Strict):
    id: int
    umgebung: str


class Modulkonfiguration(Strict):
    buergerservice: bool
    meet: bool
    meet_formulare: bool
    warteschlange: bool
    dms_d3: bool
    muk: bool


class GebietRef(Strict):
    name: str
    schluessel: str


class VerwaltungFaehigkeiten(Strict):
    id: int
    name: str
    bundesland: str
    bund_id: BundIdRef | None = None
    muk: MukRef | None = None
    modulkonfiguration: Modulkonfiguration | None = None
    gebiete: Connection[GebietRef]


class OptigovError(RuntimeError):
    pass


class OptigovClient:
    """Sendet freigegebene Abfragen an den Guard-Proxy und paginiert."""

    def __init__(self, guard_url: str, allowlist: QueryAllowlist, http: httpx.Client, verwaltung_id: int) -> None:
        self.guard_url = guard_url
        self.allowlist = allowlist
        self.http = http
        self.verwaltung_id = verwaltung_id
        self.raw_pages: list[tuple[str, dict[str, Any], dict[str, Any]]] = []

    def execute(self, operation: str, variables: dict[str, Any]) -> dict[str, Any]:
        query = self.allowlist.get(operation)
        # lokale Prüfung vor dem Senden – derselbe Code wie im Proxy
        self.allowlist.check_request(query.text, query.name, variables)
        response = request(
            self.http,
            "POST",
            self.guard_url,
            json={"query": query.text, "operationName": query.name, "variables": variables},
        )
        payload = response.json()
        if payload.get("errors"):
            raise OptigovError(f"{operation}: {payload['errors']}")
        data = payload.get("data")
        if not isinstance(data, dict):
            raise OptigovError(f"{operation}: Antwort ohne data.")
        check_response(data)
        self.raw_pages.append((operation, variables, data))
        return data

    def _paginate(self, operation: str, path: tuple[str, ...], extra: dict[str, Any]) -> Iterator[dict[str, Any]]:
        offset = 0
        while True:
            variables = {**extra, "limit": PAGE_SIZE, "offset": offset}
            data: Any = self.execute(operation, variables)
            for key in path:
                if data is None:
                    raise OptigovError(f"{operation}: Pfad {'.'.join(path)} fehlt (Verwaltung unbekannt?).")
                data = data[key]
            edges = data["edges"]
            for edge in edges:
                yield edge["node"]
            offset += len(edges)
            if not edges or offset >= data["totalCount"]:
                return

    def dienstleistungen(self, seit: str = FULL_SYNC_SINCE) -> list[DienstleistungNode]:
        nodes = self._paginate(
            "Dienstleistungen",
            ("verwaltung", "dienstleistungen"),
            {"verwaltung": self.verwaltung_id, "seit": seit},
        )
        return [DienstleistungNode.model_validate(n) for n in nodes]

    def onlinedienste(self) -> list[OnlinedienstNode]:
        nodes = self._paginate("Onlinedienste", ("verwaltung", "onlinedienste"), {"verwaltung": self.verwaltung_id})
        return [OnlinedienstNode.model_validate(n) for n in nodes]

    def formulare(self) -> list[FormularNode]:
        nodes = self._paginate("Formulare", ("verwaltung", "formulare"), {"verwaltung": self.verwaltung_id})
        return [FormularNode.model_validate(n) for n in nodes]

    def einrichtungen(self) -> list[EinrichtungNode]:
        nodes = self._paginate("Einrichtungen", ("verwaltung", "einrichtungen"), {"verwaltung": self.verwaltung_id})
        return [EinrichtungNode.model_validate(n) for n in nodes]

    def leikaschluessel(self) -> list[LeikaschluesselNode]:
        nodes = self._paginate("Leikaschluessel", ("alleLeikaschluessel",), {})
        return [LeikaschluesselNode.model_validate(n) for n in nodes]

    def faehigkeiten(self) -> VerwaltungFaehigkeiten:
        data = self.execute("VerwaltungFaehigkeiten", {"verwaltung": self.verwaltung_id})
        if data.get("verwaltung") is None:
            raise OptigovError(f"Verwaltung {self.verwaltung_id} nicht gefunden.")
        return VerwaltungFaehigkeiten.model_validate(data["verwaltung"])
