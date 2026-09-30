# optiGov – Allowlist der GraphQL-Abfragen

Nur diese Abfragen darf der ETL-Worker an optiGov senden. Der Egress-Proxy lässt
ausschließlich Abfragen durch, deren SHA-256-Hash in `allowlist.sha256` steht
(siehe `docs/05-sicherheit-datenschutz.md`, Abschnitt 5.3).

| Datei | Zweck | Personenbezug |
|-------|-------|---------------|
| `01_dienstleistungen.graphql` | Dienstleistungen + Verknüpfungen (Delta) | keiner |
| `02_onlinedienste.graphql` | Onlinedienste | keiner |
| `03_formulare.graphql` | Formulare (nur Anbieter des Formularservers) | keiner |
| `04_einrichtungen.graphql` | Organisationseinheiten | keiner |
| `05_leikaschluessel.graphql` | LeiKa-Katalog | keiner |
| `06_verwaltung_faehigkeiten.graphql` | BundID/MUK/Module (nur Flags) | keiner |

**Bewusst nicht enthalten:** Abfragen auf `statistik`, `antraege`, `terminvereinbarungen`,
`warteschlangentickets`, `chats`, `buerger`, `mitarbeiter`, `accounts`, `aktivitaeten` und `logs`.
Das Dashboard wertet ausschließlich das **Angebot** aus (Leistungen, Onlinedienste, Formulare,
Organisationseinheiten), keine Nutzungs- oder Vorgangsdaten und nichts Personenbezogenes.

Hinweise:
- In `01_dienstleistungen.graphql` werden Textfelder wie `kurztext` oder `kosten` nur auf ihr
  Vorhandensein geprüft (Vollständigkeits-KPI). Gespeichert wird im `core` nur ein Boolean.
- Für den Voll-Abgleich wird `$seit` auf ein frühes Datum gesetzt (z. B. `1970-01-01`), nicht auf `null`. Wie die API mit `null` in Filtern umgeht, ist nicht dokumentiert.
- Die Abfragen sind gegen das Schema entworfen, aber noch nicht gegen die Live-API getestet.
  Phase 1 validiert sie per Introspection bzw. Testlauf.
- Änderungen an dieser Liste erfordern ein Review (Vier-Augen-Prinzip, CODEOWNERS: ISB/DSB informieren).
