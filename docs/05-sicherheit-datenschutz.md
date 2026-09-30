# 5 · Sicherheit, Datenschutz, Barrierefreiheit, Mitbestimmung

## 5.1 Schutzbedarf (Vorschlag, mit ISB abstimmen)

| Objekt | Vertraulichkeit | Integrität | Verfügbarkeit |
|--------|:-:|:-:|:-:|
| Öffentliche Snapshots | normal | **hoch** (falsche Zahlen schaden dem Ansehen) | normal |
| Interne Mart-Daten | normal | hoch | normal |
| Zugangsdaten des optiGov-Clients | **hoch** (Zugriff auf ein Portal mit Bürgerdaten) | hoch | normal |
| ETL-System | hoch (Vertraulichkeit wird vom Client-Zugang geerbt) | hoch | normal |

## 5.2 BSI IT-Grundschutz: relevante Bausteine

| Baustein | Umsetzung im Projekt |
|----------|---------------------|
| CON.2 Datenschutz | Datenminimierung per Allowlist, kein Abruf personenbezogener Daten |
| CON.3 Datensicherungskonzept | tägliches DB-Backup, Wiederherstellung wird getestet |
| CON.8 Software-Entwicklung / CON.10 Webanwendungen | Secure SDLC, Code-Review, SAST, Abhängigkeitsprüfung, OWASP ASVS Level 2 |
| APP.3.1 Webanwendungen und -services | Eingabevalidierung, nur GET, Security-Header, OIDC |
| APP.3.2 Webserver | gehärtete Konfiguration, TLS nach **BSI TR-02102-2** (TLS 1.2/1.3, sichere Cipher Suites), HSTS |
| APP.4.3 Relationale Datenbanken | eigene DB-Rollen: ETL darf schreiben, API nur auf `mart` lesen. Verschlüsselung at rest, kein öffentlicher Port |
| SYS.1.6 Containerisierung | minimale Images (distroless), non-root, read-only Dateisystem, signierte Images |
| OPS.1.1.3 Patch- und Änderungsmanagement | Renovate/Dependabot, monatliche Patch-Fenster, CVE-Monitoring |
| OPS.1.1.5 Protokollierung | zentrale Logs **ohne** personenbezogene Inhalte, Zugriffsprotokoll der internen API |
| ORP.4 Identitäts- und Berechtigungsmanagement | SSO, Rollen `viewer`, `fachbereich`, `redaktion`, `admin`, Least Privilege |
| NET.1.1 Netzarchitektur | öffentliche Seite in der DMZ ohne Rückverbindung, ETL im internen Segment, Egress nur zu den drei APIs |
| DER.2.1 Behandlung von Sicherheitsvorfällen | Einbindung in den städtischen Prozess, Kontakt über `security.txt` |

Abschlussprüfung vor dem Go-Live: IT-Grundschutz-Check, externer Penetrationstest der
öffentlichen und der internen Seite, Freigabe durch den ISB.

## 5.3 Sichere Anbindung von optiGov (zentrale Maßnahme)

Das GraphQL-Schema enthält in denselben Endpunkten Passwörter, Tokens und Bürgerdaten, dazu
Mutationen. Deshalb gilt ein mehrstufiger Schutz:

1. **Eigener technischer Client** (`Client` + `Rolle`) nur für das Dashboard. Die `Rolle` bekommt
   ausschließlich die Rechte `dienstleistung`, `einrichtung`, `formular` und – falls für
   Zählwerte nötig – `antrag`/`terminvereinbarung`. **Nicht** vergeben werden `root`,
   `administration`, `verwaltung`, `buerger`, `account`, `rolle`, `mitarbeiter` und `chat`.
   Mit optiGov klären, ob Rollen zwischen Lesen und Schreiben unterscheiden (siehe Dokument 7).
   Andernfalls greifen die Maßnahmen 2 und 3.
2. **Persistierte Abfragen / Allowlist:** Der ETL-Code sendet ausschließlich die Abfragen aus
   `integration/optigov/queries/`. Ihr Hash wird in CI geprüft. Freie Abfragen sind im Code
   nicht vorgesehen.
3. **Egress-Proxy mit GraphQL-Prüfung** (z. B. ein kleiner Envoy- oder Python-Filter):
   - lehnt `mutation` und `subscription` ab
   - lehnt Abfragen ab, deren Hash nicht auf der Allowlist steht
   - Denylist für Felder als zusätzliche Sicherung (`passwort`, `password`, `token`,
     `zertifikat`, `generated_secret`, `buerger`, `buerger_*`, `email`, `notiz`, `daten`,
     `mitarbeiter` …)
4. **Antwortvalidierung:** `pydantic`-Modelle mit `extra="forbid"`. Tauchen unerwartete Felder
   auf, bricht der Lauf ab und es gibt einen Alarm.
5. **Geheimnisverwaltung:** Die Client-Zugangsdaten liegen im Vault und werden regelmäßig
   rotiert, mindestens jährlich und sofort bei Personalwechsel.

## 5.4 DSGVO

| Thema | Umsetzung |
|-------|-----------|
| **Datenminimierung (Art. 5 Abs. 1 lit. c, Art. 25)** | Es werden keine personenbezogenen Daten abgerufen. Nutzungsdaten fließen nur als Zählwerte (`totalCount`, `statistik`). |
| **Kleinzahlen-Schutz** | Öffentlich werden Zellen mit weniger als 5 Fällen (Leistung × Monat) als „< 5" ausgewiesen, damit keine Rückschlüsse auf Einzelpersonen möglich sind, z. B. bei seltenen Anträgen. |
| **VVT (Art. 30)** | Eintrag für das Verfahren „Digitalisierungs-Dashboard", auch wenn nur aggregiert gearbeitet wird. Der ETL-Client *könnte* technisch auf personenbezogene Daten zugreifen. |
| **Schwellwertanalyse / DSFA (Art. 35)** | Schwellwertanalyse dokumentieren. Voraussichtlich ist keine DSFA nötig, weil nur aggregiert wird. |
| **Öffentliche Seite** | keine Cookies, kein Tracking, keine Einbindung Dritter (Schriften, Skripte und Karten selbst gehostet). Damit ist **kein Consent-Banner** nötig. Optional Matomo im cookielosen Modus, selbst gehostet, IP anonymisiert. |
| **Server-Logs** | IP-Adressen gekürzt oder nach maximal 7 Tagen gelöscht |
| **Auftragsverarbeitung** | AV-Vertrag mit dem Hoster, falls extern. Der optiGov-Vertrag deckt den Zweck „Statistik" ab (prüfen). |
| **Pflichtseiten** | Impressum, Datenschutzerklärung, Erklärung zur Barrierefreiheit mit Feedback-Möglichkeit |

## 5.5 Barrierefreiheit (BITV 2.0 / WCAG 2.2 AA / EN 301 549)
- Jede Visualisierung hat eine gleichwertige **Tabellenansicht** und eine kurze Textzusammenfassung.
- Farbe transportiert nie allein Bedeutung. Muster, Beschriftungen und Icons kommen hinzu. Kontrast mindestens 4,5:1.
- Vollständig per Tastatur bedienbar, sichtbarer Fokus, Skip-Links, korrekte Landmarken und Überschriftenhierarchie.
- Unterstützt Zoom auf 400 % und Reflow ohne horizontales Scrollen, respektiert „reduzierte Bewegung".
- Erklärungen in Leichter Sprache, Seite in Deutscher Gebärdensprache (BITV-Pflicht für öffentliche Stellen).
- Automatisierte Tests (axe-core in CI) plus manueller BITV-Test vor dem Go-Live.

## 5.6 Mitbestimmung (LPVG NRW)
Eignet sich eine technische Einrichtung zur Verhaltens- oder Leistungskontrolle der
Beschäftigten, ist sie mitbestimmungspflichtig. Auswertungen je Fachbereich, etwa zu
Durchlaufzeiten oder Online-Quoten, können das berühren. Deshalb gilt:
- **Keine** Auswertung nach Mitarbeitenden. `Antrag.mitarbeiter`, `Aktivitaet` und
  `Zustaendigkeit.mitarbeiter` werden nicht abgerufen.
- Durchlaufzeiten nur auf Ebene der Leistung und erst ab Mindestfallzahlen.
- Den Personalrat in Phase 0 informieren, die Kennzahlen offenlegen, bei Bedarf eine
  Dienstvereinbarung schließen.
