# optiGov – Allowlist der GraphQL-Abfragen

Nur diese Abfragen darf der ETL-Worker an optiGov senden. Der Egress-Proxy lässt
ausschließlich Abfragen durch, deren SHA-256-Hash in `allowlist.sha256` steht
(siehe `docs/05-sicherheit-datenschutz.md`, Abschnitt 5.3).

| Datei | Zweck | Personenbezug |
|-------|-------|---------------|
| `01_dienstleistungen.graphql` | Dienstleistungen + Verknüpfungen (Delta) | keiner |
| `02_onlinedienste.graphql` | Onlinedienste | keiner |
| `03_formulare.graphql` | Formulare (nur Anbieter des Formularservers) | keiner |
| `04_einrichtungen.graphql` | Organisationsstruktur | keiner |
| `05_leikaschluessel.graphql` | LeiKa-Katalog | keiner |
| `06_nutzung_antraege.graphql` | Anzahl Anträge je Leistung/Zeitraum (`limit: 0`, nur `totalCount`) | aggregiert |
| `07_nutzung_termine.graphql` | Anzahl Termine je Leistung/Zeitraum | aggregiert |
| `08_statistik.graphql` | serverseitige Statistik | aggregiert |
| `09_verwaltung_faehigkeiten.graphql` | BundID/MUK/Module (nur Flags) | keiner |

Hinweise:
- In `01_dienstleistungen.graphql` werden Textfelder wie `kurztext` oder `kosten` nur auf ihr
  Vorhandensein geprüft (Vollständigkeits-KPI). Gespeichert wird im `core` nur ein Boolean.
- Ob `limit: 0` zulässig ist und trotzdem `totalCount` liefert, wird in Phase 1 geprüft.
  Andernfalls gilt `limit: 1` und nur `totalCount` wird ausgewertet (keine `edges` anfordern).
- Für den Voll-Abgleich wird `$seit` auf ein frühes Datum gesetzt (z. B. `1970-01-01`), nicht auf `null`. Wie die API mit `null` in Filtern umgeht, ist nicht dokumentiert.
- Die Abfragen sind gegen das Schema entworfen, aber noch nicht gegen die Live-API getestet.
  Phase 1 validiert sie per Introspection bzw. Testlauf.
- Änderungen an dieser Liste erfordern ein Review (Vier-Augen-Prinzip, CODEOWNERS: ISB/DSB informieren).
