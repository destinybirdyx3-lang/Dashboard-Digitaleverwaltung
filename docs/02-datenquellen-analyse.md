# 2 · Analyse der Schnittstellen

Grundlage sind das optiGov-GraphQL-Schema, die OpenAPI-Spezifikation des FIM-Portals (v0.24.0)
und die OpenAPI-Spezifikation des Data Hub (`api.ozg-umsetzung.de`). Aus der Planungsumgebung
waren die Endpunkte nicht erreichbar. Die Analyse stützt sich deshalb auf die Schemas. Die
tatsächlichen Wertebereiche (Status-Codes, Enum-Werte, Füllgrad) prüft Phase 1.

## 2.1 Überblick: Wer liefert was?

| Frage | optiGov (eigenes Portal) | FIM-Portal | Data Hub / Open-PVOG |
|-------|:-:|:-:|:-:|
| Welche Leistungen bietet Mülheim an? | ✅ führend | – | ✅ (gemeldet) |
| Ist die Leistung online beantragbar? | ✅ Onlinedienst, Formular, `digitalisiert` | – | ✅ `url`, `online_status` |
| Funktioniert der Onlinedienst? | ⚠️ nur `Link.erreichbar` | – | ✅ `online_status` |
| Wer ist zuständig (Bund, Land, Kommune)? | ⚠️ `Leikaschluessel.typ` | ✅ `typisierung` | – |
| OZG-Zuordnung (OZG-ID, Themenfeld) | – | ✅ `ozg[]` | ✅ `ozgid`, `ozg_bezeichnung` |
| EU-SDG-relevant? | ✅ `sdg_code` | ✅ `sdg`, `sdg_relevant` | – |
| Flächendeckung / EfA | – | – | ✅ `art_flaechendeckung` |
| Wie stark wird genutzt? | ✅ Anträge, Termine, `statistik` | – | – |
| Gibt es FIM-Stammtexte, Prozesse, Datenschemata? | – | ✅ | – |
| Vergleich mit anderen Kommunen | – | – | ✅ `open-ars` + `open-pvog/{ars}` |

**Kernaussage:** Nur zusammen ergeben die drei Quellen ein vollständiges Bild.
- **optiGov** sagt, was Mülheim *anbietet* und wie es *genutzt* wird.
- **FIM** liefert, was die Leistung *ist*: Zuständigkeitstyp, OZG-Zuordnung, Standardisierung.
- **Open-PVOG** zeigt, was *bundesweit sichtbar* ist, ob es *funktioniert* und wie *flächendeckend* es ist.

Der gemeinsame Schlüssel ist der **14-stellige LeiKa-Leistungsschlüssel**. Für den PVOG-Abruf
kommt der **ARS** hinzu.

## 2.2 optiGov-Serviceportal (GraphQL)

### 2.2.1 Relevante Typen und Felder

**`Dienstleistung`** ist der zentrale Typ: eine Leistung, wie Mülheim sie anbietet.

| Feld | Nutzen im Dashboard |
|------|---------------------|
| `id`, `leistungsname`, `leistungsbezeichnung` | Anzeige |
| `digitalisiert: Boolean!` | Selbstauskunft „digital". **Nicht im `DienstleistungFilterInput` enthalten**, lässt sich also nur clientseitig auswerten. |
| `exportfaehig: Boolean!` | Hinweis auf die PVOG-Meldung (XZuFi-Export). **Klären, was genau das bedeutet.** |
| `oeffentlich_anzeigen`, `in_listen_anzeigen`, `sichtbar_von_*`/`sichtbar_bis_*` | Grundgesamtheit: nur aktive, öffentliche Leistungen zählen |
| `erstellt`, `bearbeitet` | Aktualität der Pflege, Delta-Abruf |
| `leikaschluessel { schluessel … }` | **Join-Schlüssel** (n:m) |
| `onlinedienste { typ vertrauensniveau zahlungsweise url formular{…} }` | Online-Beantragung, Vertrauensniveau, E-Payment |
| `formulare { benoetigte_vertrauensstufe formularserver{anbieter} }` | Online-Formular, Anbieter |
| `formulare_downloads`, `formulare_links`, `dokumente` | Reifegrad 2 (Formular zum Herunterladen) |
| `terminvorlagen { id }` | Online-Terminbuchung möglich |
| `einrichtungen { id name uebergeordnete_einrichtung{…} }` | Zuordnung zum Fachbereich / Amt |
| `themenfelder { name }` | Kommunale Themen-Navigation |
| `links { erreichbar }` | Linkqualität |
| `kosten`, `kostenpunkte`, `bearbeitungsdauer`, `fristen` | Vollständigkeit der Beschreibung (Qualitäts-KPI) |
| `infodienst_dienstleistung { leikaschluessel aktualisiert }` | Zweiter Weg zum LeiKa-Schlüssel, Aktualität des Infodienstes (Landesredaktion) |

**`Leikaschluessel`** liegt in optiGov als Katalog vor (`alleLeikaschluessel`, wird über
`aktualisiereLeikaschluessel` gepflegt): `schluessel`, `leistungsgruppierung`, `verrichtung`,
`typ`, `leistungstyp`, `sdg_code`, `sdg_informationsbereich`, `status_code`,
`portalverbund_lagen(_codes)`, `dienstleistungen { id }`.
→ Daraus ergibt sich eine mögliche **Grundgesamtheit**: alle LeiKa-Leistungen, deren Vollzug kommunal ist.

**`Onlinedienst`**: `typ`, `vertrauensniveau`, `zahlungsweise`, `url`, `formular`, `dienstleistungen`.
→ Kerninformation für „online verfügbar". Die Domain der `url` zeigt, ob es ein eigener Dienst,
ein EfA-Dienst oder ein Landesdienst ist.

**`Antrag`**: `id`, `status`, `erstellt`, `bearbeitet`, `formular{id}`, `dienstleistung{id}`.
→ **Nutzung:** Online-Anträge pro Leistung und Monat, Statusverteilung, grobe Durchlaufzeit.
`buerger`, `notiz`, `chats` und `dateien` werden **nie** abgefragt.

**`Terminvereinbarung`**: `termin`, `status`, `erstellt`, `storniert`, `schalter{einrichtung{id}}`, `terminvorlagen{dienstleistung{id}}`.
→ Online-Terminbuchungen pro Leistung und Einrichtung. `buerger_*`, `daten`, `notiz` werden **nie** abgefragt.

**`statistik(verwaltung, datensatz, filter)`** liefert fertig aggregierte Zeitreihen
(`serien{name bezeichner werte einheit}`), filterbar nach Datum, Dienstleistungen, Formularen
und Einrichtungen.
→ **Bevorzugter Weg für Nutzungszahlen**, weil die Aggregation serverseitig passiert und keine
Einzeldatensätze fließen. **Die zulässigen Werte für `datensatz` sind nicht dokumentiert. Bei
optiGov erfragen.**

**`Verwaltung.modulkonfiguration`** (`buergerservice`, `meet`, `warteschlange`, `dms_d3`, `muk`)
und das Vorhandensein von `bund_id` / `muk` (nur als Boolean)
→ Querschnittsfähigkeiten: BundID, MUK (Unternehmenskonto), Videoberatung, DMS-Anbindung
für die Ende-zu-Ende-Verarbeitung.

**`Einrichtung`**: Hierarchie über `uebergeordnete_einrichtung` → Aggregation nach Dezernat, Amt, Fachbereich.

### 2.2.2 Kritisch: Was **nicht** abgerufen werden darf

Das Schema legt Geheimnisse und personenbezogene Daten über dieselbe API offen. Die Integration
muss das technisch ausschließen, nicht nur per Konvention.

| Kategorie | Felder / Typen |
|-----------|----------------|
| **Zugangsdaten und Geheimnisse** | `LDAPZugang.password`, `ExchangeServer.passwort`, `DmsD3.passwort`/`api_schluessel`, `FormularServer.passwort`/`benutzer`, `Infodienst.token`, `Verwaltung.adressomat_token`, `Widget.services_adressomat_token`, `Client.generated_secret`, `BundID.zertifikat`, `Muk.zertifikat`, `zweiFaktor*`-Queries |
| **Personenbezogene Daten Bürger/Unternehmen** | `Buerger` (komplett), `Unternehmen`, `Antrag.buerger`, `Antrag.notiz`, `Antrag.transaktionsbezeichner`, `Chat`, `Nachricht`, `Datei`, `Terminvereinbarung.buerger_*`/`daten`/`notiz`/`stornierungsnachricht`, `Warteschlangenticket.daten`, `Antragsanfrage` |
| **Personenbezogene Daten Beschäftigte** | `Mitarbeiter` (Namen, Kontakt), `Account`, `Aktivitaet` (Protokoll mit Account-Bezug), `Antrag.mitarbeiter`, `Zustaendigkeit.mitarbeiter`, `logs` |
| **Alle Mutations** | `erstelle*`, `bearbeite*`, `loesche*`, `buche*`, `aktualisiere*` usw. |

→ Umsetzung in Abschnitt 5.3: eigene Rolle, Allowlist mit persistierten Abfragen und ein
Egress-Proxy, der Mutationen und gesperrte Felder blockiert. Die erlaubten Abfragen stehen in
`integration/optigov/queries/`.

### 2.2.3 Technische Hinweise
- Paginierung über `limit`/`offset` mit `totalCount`. Seitengröße 100, Abfragen flach halten,
  keine tief verschachtelten n:m-Kaskaden in einer Abfrage.
- Delta-Abruf über `filter: { bearbeitet: { gte: "<letzter Lauf>" } }`. Löschungen erkennt nur
  ein vollständiger Abgleich (wöchentlich oder täglich, je nach Datenmenge).
- `DateTime` ist ein Skalar ohne dokumentierte Zeitzone. In Phase 1 prüfen und dann in UTC speichern.

## 2.3 FIM-Portal (REST, `fimportal.de`)

Öffentlich, ohne Authentifizierung, IP-basiertes Rate-Limit (bei 429 mit Backoff wiederholen).

| Endpunkt | Nutzen |
|----------|--------|
| `GET /api/v1/leistung-steckbriefe?leistungsschluessel=…` bzw. Liste mit `updated_since` | **Stammdaten je LeiKa-Schlüssel**: `typisierung` (Regelungs- und Vollzugskompetenz), `leistungsadressat` (Bürger, Unternehmen, Verwaltung), `ozg[]` (OZG-ID, Themenfeld), `sdg`, `freigabe_status`, PV-Lagen in `klassifizierung` |
| `GET /api/v1/leistung-stammtexte?leistungsschluessel=…&source=pvog` | Liegt für den Schlüssel ein Stammtext bzw. PVOG-Text vor? `redaktion_id` zeigt, welche Redaktion (z. B. NRW) ihn pflegt. |
| `GET /api/v1/leistung-steckbriefe?ozg_themenfeld=…` | Gruppierung nach den 14 OZG-Themenfeldern |
| `GET /api/v0/processes?fts_query=…` | Ausbau: Gibt es einen FIM-Prozess? Hinweis auf Standardisierung und Ende-zu-Ende-Fähigkeit |
| `GET /api/v1/schemas?…` | Ausbau: Gibt es ein FIM-Datenschema (Stammdatenschema) zur Leistung? |
| `POST /tools/check-leistung` | Optional: Qualitätsbericht zu den eigenen XZuFi-Leistungsbeschreibungen |

**Wichtig:** Die `typisierung` (Codeliste `urn:de:fim:leika:typisierung`) legt fest, welche
Leistungen überhaupt in kommunaler Verantwortung liegen. Ohne sie würde Mülheim an Leistungen
gemessen, für die Bund oder Land zuständig sind. Welche Typen als „kommunal vollzogen" gelten,
wird in Phase 1 mit der aktuellen Codeliste festgelegt und dokumentiert.

Abrufstrategie: einmalig alle Steckbriefe laden (paginiert, `limit=200`), danach täglich nur
Änderungen über `updated_since`.

## 2.4 Dashboard Digitale Verwaltung / Data Hub (REST, `api.ozg-umsetzung.de`)

| Endpunkt | Nutzen |
|----------|--------|
| `GET /public/v1/dash/open-pvog/051170000000?includeAbove=true&includeBelow=false` | Alle für Mülheim im PVOG verfügbaren Leistungen samt Onlinedienst, auch solche, die Kreis, Land oder Bund anbieten (`includeAbove`) |
| `GET /public/v1/dash/open-pvog/051170000000/export?filetype=csv` | **Vollständiger Export als Stream.** Für den täglichen Lauf effizienter als paginieren. |
| `GET /public/v1/dash/open-ars` | Liste der Gebietskörperschaften für den Benchmark |

Wichtige Felder in `OpenPvogDto`: `leika_key`, `ozgid`, `ozg_bezeichnung`, `url`,
`online_status` (`ok` oder `nicht ok`), `aktiv`, `art_flaechendeckung`,
`begruendung_nicht_beruecksichtigt`, `datenstand_pvog_import`. Das Feld `export_datum` ist
deprecated und wird **nicht** genutzt.

Was daraus folgt:
- **Außensicht:** Was im PVOG steht, finden Bürgerinnen und Bürger auch über andere Portale
  (Bund, NRW). Taucht eine Leistung zwar in optiGov als online auf, im PVOG aber nicht, fehlt
  die Meldung. Das ist ein Qualitätsbefund.
- **Funktion:** `online_status = nicht ok` ist ein Warnsignal und landet in der Qualitätssicht.
- **Unterscheidung `includeAbove=true` gegen `false`:** Trennt „Mülheim selbst" von „für
  Mülheimer verfügbar (Land, Bund, EfA)". Beide Zahlen zeigen, getrennt ausgewiesen.
- **Benchmark:** Dieselbe Abfrage für Vergleichskommunen (z. B. Essen `051130000000`,
  Duisburg `051120000000`, Oberhausen `051190000000`). Die ARS vorher über `open-ars`
  verifizieren.

## 2.5 Sinnvolle Zusammenhänge (Empfehlung)

1. **Soll gegen Ist:** Grundgesamtheit (kommunal vollzogene LeiKa-Leistungen laut FIM-Typisierung)
   gegen das, was Mülheim in optiGov beschreibt, gegen das, was online ist. Diese drei Werte
   bilden den **„Digitalisierungstrichter"**.
2. **Selbstauskunft gegen Außensicht:** optiGov (`digitalisiert`, Onlinedienst) gegen PVOG
   (`url`, `online_status`). Abweichungen sind Qualitätsbefunde.
3. **Angebot gegen Nachfrage:** Online-Verfügbarkeit gegen Nutzung (Anträge, Termine,
   `statistik`). Daraus entsteht die **Priorisierungsmatrix**: stark nachgefragte Leistungen
   ohne Onlinedienst zuerst digitalisieren.
4. **Eigenentwicklung gegen EfA:** Aus der Domain der Onlinedienst-URL und `art_flaechendeckung`
   ablesen, wie viel Mülheim nachnutzt und wie viel es selbst baut.
5. **Kanalverschiebung:** Online-Anträge und Online-Termine im Verhältnis zu Vor-Ort-Terminen
   und Wartemarken im Zeitverlauf.
6. **Standardisierungsgrad:** Existieren für eine Leistung FIM-Stammtext, -Prozess und
   -Datenschema? Das zeigt, wie gut sie auf Ende-zu-Ende vorbereitet ist.
