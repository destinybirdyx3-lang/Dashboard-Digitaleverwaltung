# 1 · Projektplan

## 1.1 Ausgangslage und Ziel

Die Stadt Mülheim an der Ruhr (ARS `051170000000`, NRW) bietet ihre Verwaltungsleistungen
über ein optiGov-Serviceportal an. Wie weit diese Leistungen digitalisiert sind, lässt sich
heute nur mit Aufwand aus mehreren Quellen zusammensuchen: dem eigenen Portal, dem FIM-Portal
des Bundes und dem Dashboard Digitale Verwaltung (Open-PVOG).

**Ziel:** Ein tagesaktuelles Dashboard beantwortet transparent und belastbar die Frage
*„Wie digital ist die Verwaltung der Stadt Mülheim an der Ruhr – heute, im Zeitverlauf und
im Vergleich?"*

Messbare Projektziele:

| Ziel | Messgröße |
|------|-----------|
| Transparenz für alle | Öffentliche Version, barrierefrei nach BITV 2.0 / WCAG 2.2 AA |
| Tagesaktualität | Alle Quellen werden täglich bis 06:00 Uhr aktualisiert. Der Datenstand ist pro Quelle sichtbar. |
| Steuerungswirkung | Die Fachbereiche sehen ihre Lücken, z. B. „häufig nachgefragt, aber nicht online" |
| Datenqualität | Fehlende LeiKa-Zuordnungen, defekte Links und Abweichungen zum PVOG werden sichtbar und sinken messbar |
| Rechtssicherheit | Freigaben von ISB und DSB liegen vor. Der Personalrat ist beteiligt. Keine personenbezogenen Daten im Dashboard. |

## 1.2 Zielgruppen und Sichten

| Zielgruppe | Sicht | Zugang |
|------------|-------|--------|
| Bürgerinnen, Bürger, Unternehmen, Presse, Politik | **Öffentliche Sicht**: Gesamtstand, Themenfelder, Leistungssuche mit Link zum Onlinedienst, Trend, Open-Data-Download | anonym, ohne Cookies |
| Verwaltungsvorstand, Digitalisierungsteam | **Steuerungssicht**: Priorisierungsmatrix, Nutzungszahlen, Benchmark, Zielerreichung | intern, SSO |
| Fachbereiche / Ämter | **Fachbereichssicht**: eigene Leistungen, Lücken, Datenqualitäts-Aufgaben | intern, SSO, gefiltert nach Organisationseinheit |
| Portalredaktion | **Qualitätssicht**: fehlende LeiKa-Zuordnung, tote Links, Abweichungen zum PVOG, veraltete Texte | intern, SSO |

Die öffentliche Sicht enthält **nur aggregierte, nicht personenbezogene Daten**. Kleine
Fallzahlen werden unterdrückt (siehe Dokument 5).

## 1.3 Umfang

**Im Umfang**
- Tägliche Übernahme (ETL) aus optiGov (GraphQL), FIM-Portal (REST) und Data Hub / Open-PVOG (REST)
- Verknüpfung über den 14-stelligen LeiKa-Schlüssel
- Ein eigenes Reifegradmodell auf Leistungsebene (Stufe 0 bis 4)
- Historisierung als täglicher Snapshot, damit Trends sichtbar werden
- Öffentliches Frontend, internes Frontend und Open-Data-Export (CSV/JSON)
- Betriebs-, Sicherheits- und Datenschutzkonzept

**Nicht im Umfang (vorerst)**
- Schreibende Zugriffe auf optiGov (das Dashboard liest nur)
- Auswertungen auf Ebene einzelner Mitarbeitender (mitbestimmungspflichtig, fachlich nicht nötig)
- Anbindung von Fachverfahren. Möglicher Ausbau in Phase 4.

## 1.4 Phasen und Meilensteine

```
Phase 0  Klärung & Zugänge        ██░░░░░░░░░░░░░░░░░░   3 Wochen
Phase 1  Daten-Spike & Prototyp   ░░██████░░░░░░░░░░░░   6 Wochen
Phase 2  Internes Dashboard (MVP) ░░░░░░░██████░░░░░░░   6 Wochen
Phase 3  Öffentliches Dashboard   ░░░░░░░░░░░░█████░░░   5 Wochen
Phase 4  Ausbau & Regelbetrieb    ░░░░░░░░░░░░░░░░████→  laufend
```

### Phase 0: Klärung und Zugänge (ca. 3 Wochen)
- Offene Fragen aus [Dokument 7](07-offene-fragen.md) klären. Die wichtigsten betreffen optiGov:
  gibt es einen reinen Lesezugang, welche Werte hat `statistik.datensatz`, welche Status gibt es?
- Einen technischen optiGov-Client mit eigener, minimaler Rolle einrichten (Abschnitt 5.3)
- Schutzbedarfsfeststellung und Datenschutz-Schwellwertanalyse durchführen, Eintrag im VVT anlegen
- Personalrat informieren und eine Dienstvereinbarung vorbereiten, falls nötig
- Hosting festlegen (kommunales Rechenzentrum oder IT-Dienstleister)

**Meilenstein M0:** Zugänge vorhanden, Rahmen mit ISB, DSB und Personalrat abgestimmt.

### Phase 1: Daten-Spike und Prototyp (ca. 6 Wochen)
- Rohdaten aller drei Quellen einmal vollständig laden und das Profiling im Datenmodell ablegen
- Die Abdeckung des Join-Schlüssels messen: Wie viele Mülheimer Dienstleistungen haben einen
  LeiKa-Schlüssel? Wie viele davon kennt das FIM-Portal, wie viele das PVOG?
- Das Reifegradmodell an echten Daten kalibrieren und mit den Fachbereichen abstimmen
- Einen einfachen Prototyp mit 5 bis 8 Kern-Kennzahlen bauen

**Meilenstein M1:** Kennzahlenkatalog ist abgenommen und die Datenqualität bekannt.

### Phase 2: Internes Dashboard / MVP (ca. 6 Wochen)
- Produktive ETL-Strecke mit täglichem Lauf, Monitoring und Alarmierung
- Datenmodell mit Staging, Core, Mart und Snapshots, dazu automatische Datentests
- Internes Frontend mit SSO, Steuerungs-, Fachbereichs- und Qualitätssicht
- Sicherheitsprüfung: Penetrationstest nach OWASP ASVS L2, Abgleich mit dem IT-Grundschutz-Check

**Meilenstein M2:** Das interne Dashboard ist produktiv. Die Fachbereiche pflegen ihre Daten nach.

### Phase 3: Öffentliches Dashboard (ca. 5 Wochen)
- Öffentliches Frontend als statische Seite mit aggregierten Snapshots
- BITV-Test (z. B. BIK BITV-Test), Erklärung zur Barrierefreiheit, Datenschutzerklärung, Impressum
- Open-Data-Export mit Metadaten nach DCAT-AP.de, Veröffentlichung auf Open.NRW
- Kommunikation: Pressemitteilung, Einbindung ins Serviceportal

**Meilenstein M3:** Go-Live der öffentlichen Seite.

### Phase 4: Ausbau und Regelbetrieb
- Benchmark mit Vergleichskommunen (Essen, Duisburg, Oberhausen und weitere) über `open-ars`
- Zielwerte und Prognose, z. B. „Wann erreichen wir 80 % Online-Verfügbarkeit?"
- FIM-Prozesse und -Datenschemata als Reifegradmerkmal (Ende-zu-Ende-Fähigkeit)
- Eventuell Nutzungsdaten aus Fachverfahren
- Quartalsweise Review der Kennzahlen mit dem Verwaltungsvorstand

## 1.5 Rollen

| Rolle | Aufgabe |
|-------|---------|
| Product Owner (Digitalisierung / CDO-Büro) | Ziele, Priorisierung, Abnahme |
| Fachadministration optiGov | Zugang, Rollen, Fachwissen zum Datenmodell |
| Portalredaktion | Datenqualität, LeiKa-Zuordnung |
| Informationssicherheitsbeauftragte/r (ISB) | Schutzbedarf, Grundschutz-Check, Freigabe |
| Datenschutzbeauftragte/r (DSB) | Schwellwertanalyse, VVT, Freigabe |
| Personalrat | Beteiligung nach LPVG NRW |
| Entwicklung (1–2 Personen) | ETL, Datenmodell, Frontend, Betrieb (DevOps) |
| UX / Barrierefreiheit (anteilig) | Nutzertests, BITV |
| IT-Betrieb / Rechenzentrum | Hosting, Backup, SSO, Netz |

## 1.6 Risiken

| Risiko | W | A | Gegenmaßnahme |
|--------|---|---|---------------|
| Die optiGov-API gibt mit dem technischen Konto Geheimnisse oder personenbezogene Daten heraus (Passwörter, Tokens, Bürgerdaten liegen im Schema) | hoch | hoch | Eigene minimale Rolle, Allowlist der Abfragen, Proxy blockiert Mutationen und verbotene Felder (Abschnitt 5.3) |
| Viele Dienstleistungen haben keinen LeiKa-Schlüssel, der Join ist lückenhaft | hoch | hoch | Die Zuordnungsquote selbst zur KPI machen, Redaktions-Workflow für die Nachpflege |
| Das Feld `digitalisiert` in optiGov ist uneinheitlich gepflegt | mittel | hoch | Reifegrad aus mehreren Merkmalen ableiten, nicht aus einem einzelnen Flag. Plausibilitätscheck gegen das PVOG. |
| Open-PVOG ändert sich (z. B. ist `export_datum` bereits deprecated) | mittel | mittel | Validierung gegen das Schema, Vertragstests, Datenstand anzeigen |
| Die öffentlichen Zahlen werden als „Ranking" missverstanden | mittel | mittel | Methodik offen erklären, Kontext zu den Zuständigkeiten (Bund, Land, Kommune) geben |
| Mitbestimmung verzögert den Start | mittel | mittel | Personalrat früh einbinden, keine Auswertung nach Mitarbeitenden |
| Rate-Limits der Bundes-APIs | niedrig | niedrig | Nächtlicher Delta-Abruf, Backoff, Caching |

W = Wahrscheinlichkeit, A = Auswirkung
