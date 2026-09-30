# 7 · Offene Fragen und Entscheidungen

## An optiGov / Fachadministration
1. Gibt es einen **reinen Lesezugang** (Rolle ohne Schreibrechte)? Unterscheiden die Rechte in `Rolle` (z. B. `dienstleistung: true`) zwischen Lesen und Schreiben?
2. Welche Werte für `statistik(datensatz: …)` gibt es, und welche Serien liefern sie?
3. Welche Werte haben `Antrag.status`, `Terminvereinbarung.status`, `Onlinedienst.typ`, `vertrauensniveau` und `zahlungsweise`?
4. Was genau bedeuten `Dienstleistung.digitalisiert` und `exportfaehig`, und wer pflegt sie?
5. Wie authentifiziert sich ein technischer Client (OAuth2 Client Credentials?), und gibt es Rate-Limits?
6. Enthält `alleLeikaschluessel` den vollständigen LeiKa-Katalog oder nur zugeordnete Schlüssel?
7. Ist `Gebiet.schluessel` der ARS? Dann ließe sich die Verwaltung eindeutig darüber identifizieren.
8. Gibt es eine Test- oder Staging-Verwaltung für die Entwicklung?

## An den Data Hub / das Dashboard Digitale Verwaltung
9. Wie aktuell ist `datenstand_pvog_import` (Aktualisierungstakt)?
10. Welche Rate-Limits und Nutzungsbedingungen gelten (Quellenangabe auf der öffentlichen Seite)?

## Intern zu entscheiden
11. **Definition des Soll-Katalogs:** Welche LeiKa-Typisierungen gelten für Mülheim als „kommunal zuständig"? (Vorschlag in Phase 1)
12. **Reifegrad-Regeln** fachlich abnehmen, vor allem Stufe 4.
13. **Vergleichskommunen** für den Benchmark (Vorschlag: Ruhrgebietsstädte ähnlicher Größe plus NRW-Durchschnitt)
14. **Hosting** (eigenes Rechenzentrum oder IT-Dienstleister) und **SSO-Anbieter**
15. **Veröffentlichung als Open Source** (openCoDE)? Das würde die Nachnutzung durch andere Kommunen erleichtern.
16. **Zielwerte** für die Steuerungssicht, z. B. „80 % Online-Quote bis Ende 2027"
17. **Freigabeprozess** für die öffentliche Seite: Wer gibt Änderungen an Methodik und Texten frei?
