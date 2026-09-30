"""Prüfung von GraphQL-Abfragen an optiGov (Dokument 5, Abschnitt 5.3).

Das optiGov-Schema legt Zugangsdaten, personenbezogene Daten und Nutzungsdaten über denselben
Endpunkt offen. Diese Schicht stellt technisch sicher, dass nur freigegebene Abfragen gesendet und
nur unbedenkliche Antworten angenommen werden:

1. Nur Abfragen, deren SHA-256-Hash in ``allowlist.sha256`` steht (persistierte Abfragen).
2. Nur ``query`` – keine ``mutation``/``subscription``, keine Introspection.
3. Zusätzlich eine Denylist für Feldnamen (Absicherung, falls die Allowlist falsch gepflegt wird).
4. Grenzen für Variablen (z. B. Seitengröße).
5. Antworten werden auf gesperrte Schlüssel durchsucht.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from graphql import (
    DocumentNode,
    FieldNode,
    GraphQLSyntaxError,
    OperationDefinitionNode,
    OperationType,
    parse,
    visit,
)
from graphql.language import Visitor

# Felder, die niemals abgefragt oder angenommen werden – Geheimnisse, Personenbezug, Nutzungsdaten.
DENIED_FIELDS: frozenset[str] = frozenset(
    {
        # Zugangsdaten und Geheimnisse
        "password",
        "passwort",
        "token",
        "zertifikat",
        "generated_secret",
        "api_schluessel",
        "adressomat_token",
        "services_adressomat_token",
        "benutzer",
        "wsdl",
        "ldap_zugang",
        "exchange_server",
        "infodienst",
        "widgets",
        "client",
        "clients",
        "secret",
        "zweiFaktorAuthentifizierungQrCode",
        "zweiFaktorAuthentifizierungWiederherstellungscodes",
        # Personenbezogene Daten (Bürger, Unternehmen, Beschäftigte)
        "buerger",
        "unternehmen",
        "mitarbeiter",
        "erbende_mitarbeiter",
        "leiter",
        "stellvertretende_leiter",
        "account",
        "accounts",
        "rolle",
        "email",
        "benachrichtigung_email",
        "telefon",
        "telefon_mobil",
        "fax",
        "vorname",
        "nachname",
        "geburtsdatum",
        "anschrift",
        "buerger_name",
        "buerger_email",
        "buerger_telefon",
        "notiz",
        "daten",
        "stornierungsnachricht",
        "transaktionsbezeichner",
        "attribute_intern",
        "servicezeiten",
        "zustaendigkeiten",
        "chats",
        "chat",
        "nachrichten",
        "dateien",
        "datei",
        "aktivitaet",
        "aktivitaeten",
        "logs",
        "hash",
        # Nutzungs- und Vorgangsdaten (bewusst ausgeschlossen)
        "statistik",
        "antrag",
        "antraege",
        "antragsanfrage",
        "terminvereinbarung",
        "terminvereinbarungen",
        "terminvereinbarungen_heute",
        "warteschlangenticket",
        "warteschlangentickets",
        "warteschlangentickets_heute",
        "terminmoeglichkeiten",
        # Root-Listen mit Personenbezug
        "alleAccounts",
        "alleAktivitaeten",
        "alleClients",
        "alleMitarbeiter",
        "alleRollen",
        "alleTerminvereinbarungen",
        "alleSchalter",
    }
)

# Schlüssel, die in Antworten nicht vorkommen dürfen (Aliase könnten Feldnamen verschleiern,
# deshalb wird die Antwort zusätzlich geprüft).
DENIED_RESPONSE_KEYS: frozenset[str] = DENIED_FIELDS - {"hash"}

MAX_PAGE_SIZE = 100
MAX_QUERY_BYTES = 20_000


class GuardViolation(Exception):
    """Eine Abfrage oder Antwort verletzt die Sicherheitsregeln."""


def sha256_hex(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AllowedQuery:
    name: str
    text: str
    sha256: str


class QueryAllowlist:
    """Freigegebene Abfragen aus ``integration/optigov/queries``.

    Jede ``*.graphql``-Datei muss mit ihrem Hash in ``allowlist.sha256`` stehen; so wird eine
    unbemerkte Änderung einer Abfrage erkannt (Änderungen laufen über Review, Vier-Augen-Prinzip).
    """

    def __init__(self, query_dir: Path) -> None:
        self.query_dir = query_dir
        hashes = self._read_hashfile(query_dir / "allowlist.sha256")
        self._by_hash: dict[str, AllowedQuery] = {}
        self._by_operation: dict[str, AllowedQuery] = {}
        for path in sorted(query_dir.glob("*.graphql")):
            text = path.read_text(encoding="utf-8")
            digest = sha256_hex(text)
            if hashes.get(path.name) != digest:
                raise GuardViolation(f"Hash von {path.name} stimmt nicht mit allowlist.sha256 überein.")
            document = self._parse(text)
            operation = _single_operation(document)
            if operation.name is None:
                raise GuardViolation(f"{path.name}: Abfrage braucht einen Namen.")
            check_document(document)
            allowed = AllowedQuery(name=operation.name.value, text=text, sha256=digest)
            self._by_hash[digest] = allowed
            self._by_operation[allowed.name] = allowed
        unknown = set(hashes) - {p.name for p in query_dir.glob("*.graphql")}
        if unknown:
            raise GuardViolation(f"allowlist.sha256 nennt fehlende Dateien: {sorted(unknown)}")

    @staticmethod
    def _read_hashfile(path: Path) -> dict[str, str]:
        result: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            digest, _, name = line.strip().partition("  ")
            result[name.strip()] = digest.strip()
        return result

    @staticmethod
    def _parse(text: str) -> DocumentNode:
        try:
            return parse(text)
        except GraphQLSyntaxError as exc:
            raise GuardViolation(f"Ungültiges GraphQL: {exc.message}") from exc

    def get(self, operation_name: str) -> AllowedQuery:
        try:
            return self._by_operation[operation_name]
        except KeyError as exc:
            raise GuardViolation(f"Abfrage '{operation_name}' ist nicht freigegeben.") from exc

    @property
    def operations(self) -> list[str]:
        return sorted(self._by_operation)

    def check_request(self, query: str, operation_name: str | None, variables: Mapping[str, Any] | None) -> None:
        """Prüft eine eingehende Anfrage (im Guard-Proxy)."""
        if len(query.encode("utf-8")) > MAX_QUERY_BYTES:
            raise GuardViolation("Abfrage zu groß.")
        allowed = self._by_hash.get(sha256_hex(query))
        if allowed is None:
            raise GuardViolation("Abfrage ist nicht in der Allowlist.")
        if operation_name not in (None, allowed.name):
            raise GuardViolation("operationName passt nicht zur freigegebenen Abfrage.")
        check_document(self._parse(query))
        check_variables(variables or {})


def _single_operation(document: DocumentNode) -> OperationDefinitionNode:
    operations = [d for d in document.definitions if isinstance(d, OperationDefinitionNode)]
    if len(operations) != 1 or len(document.definitions) != 1:
        raise GuardViolation("Genau eine Operation ohne Fragmente erlaubt.")
    return operations[0]


class _FieldCollector(Visitor):
    def __init__(self) -> None:
        super().__init__()
        self.names: list[str] = []

    def enter_field(self, node: FieldNode, *_args: Any) -> None:
        self.names.append(node.name.value)


def check_document(document: DocumentNode) -> None:
    operation = _single_operation(document)
    if operation.operation is not OperationType.QUERY:
        raise GuardViolation("Nur lesende Abfragen (query) sind erlaubt.")
    collector = _FieldCollector()
    visit(document, collector)
    for name in collector.names:
        if name.startswith("__"):
            raise GuardViolation("Introspection ist nicht erlaubt.")
        if name in DENIED_FIELDS:
            raise GuardViolation(f"Feld '{name}' ist gesperrt.")


def check_variables(variables: Mapping[str, Any]) -> None:
    for key, value in variables.items():
        if isinstance(value, (dict, list)):
            raise GuardViolation(f"Variable '{key}' muss ein einfacher Wert sein.")
        if key == "limit" and (not isinstance(value, int) or not 0 <= value <= MAX_PAGE_SIZE):
            raise GuardViolation(f"limit muss zwischen 0 und {MAX_PAGE_SIZE} liegen.")
        if key == "offset" and (not isinstance(value, int) or value < 0):
            raise GuardViolation("offset muss >= 0 sein.")
        if isinstance(value, str) and len(value) > 64:
            raise GuardViolation(f"Variable '{key}' ist zu lang.")


def check_response(payload: Any, _path: Iterable[str] = ()) -> None:
    """Durchsucht eine Antwort rekursiv nach gesperrten Schlüsseln."""
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            if key in DENIED_RESPONSE_KEYS:
                raise GuardViolation(f"Antwort enthält gesperrten Schlüssel '{key}'.")
            check_response(value)
    elif isinstance(payload, list):
        for item in payload:
            check_response(item)
