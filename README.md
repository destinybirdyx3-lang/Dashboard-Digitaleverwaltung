# Digitalisierungs-Dashboard der Stadt Mülheim an der Ruhr

Ein tagesaktuelles Dashboard, das zeigt, wie weit die Verwaltungsleistungen der Stadt
Mülheim an der Ruhr digitalisiert sind. Grundlage ist der **Leistungskatalog (LeiKa)**.
Er wird mit den Daten aus dem eigenen **Serviceportal (optiGov)**, dem **FIM-Portal**
und dem **Dashboard Digitale Verwaltung (Open-PVOG / Data Hub)** verknüpft.

> Status: **Planungsphase.** In diesem Repository liegt die vollständige Projektplanung.
> Mit der Umsetzung beginnt Phase 1 (siehe Projektplan).

## Dokumente

| # | Dokument | Inhalt |
|---|----------|--------|
| 1 | [Projektplan](docs/01-projektplan.md) | Ziele, Zielgruppen, Umfang, Phasen, Rollen, Risiken |
| 2 | [Analyse der Schnittstellen](docs/02-datenquellen-analyse.md) | Welche Daten jede Schnittstelle liefert, was wir abrufen und was ausdrücklich nicht |
| 3 | [Datenmodell & Kennzahlen](docs/03-datenmodell-und-kennzahlen.md) | Verknüpfung über den LeiKa-Schlüssel, Reifegradmodell, KPI-Katalog |
| 4 | [Architektur](docs/04-architektur.md) | Systemaufbau, Technologie, tägliche Aktualisierung, Betrieb |
| 5 | [Sicherheit & Datenschutz](docs/05-sicherheit-datenschutz.md) | BSI IT-Grundschutz, DSGVO, BITV 2.0, Mitbestimmung |
| 6 | [UX & Design](docs/06-ux-design.md) | Seitenstruktur, Visualisierungen, Export (einseitige PDF-Übersicht, CSV/XLSX), Barrierefreiheit, Designsystem |
| 7 | [Offene Fragen & Entscheidungen](docs/07-offene-fragen.md) | Was vor dem Start geklärt werden muss |

## Technische Entwürfe

- `integration/optigov/queries/`: Freigabeliste (Allowlist) der erlaubten GraphQL-Abfragen an optiGov: nur Angebotsdaten (Leistungen, Onlinedienste, Formulare, Organisationseinheiten), keine Nutzungsdaten, nichts Personenbezogenes
- `integration/datahub/README.md`: Abruf der Open-PVOG-Daten für Mülheim (ARS `051170000000`)
- `integration/fim/README.md`: Abruf der Leistungssteckbriefe aus dem FIM-Portal
- `db/schema.sql`: Entwurf des Datenmodells (Staging, Core, Mart)
