# 4 · Architektur

## 4.1 Überblick

```
 Quellen                    Integrationszone (intern)                        Auslieferung
┌──────────────┐   HTTPS   ┌──────────────────────────────────────────┐
│ optiGov      │◄──────────┤ Egress-Proxy (GraphQL-Allowlist,          │
│ GraphQL      │  OAuth2   │ blockiert Mutationen / gesperrte Felder)  │
└──────────────┘  Client   └──────────────▲───────────────────────────┘
┌──────────────┐                          │
│ FIM-Portal   │◄──────┐   ┌──────────────┴──────────┐   ┌──────────────┐
└──────────────┘       ├───┤ ETL-Worker (Python)     ├──►│ PostgreSQL   │
┌──────────────┐       │   │ täglich 02:00 + Delta   │   │ raw/core/mart│
│ Data Hub     │◄──────┘   └─────────────────────────┘   └──────┬───────┘
│ Open-PVOG    │                                                │ dbt-Transformationen + Tests
└──────────────┘                                                ▼
                           ┌─────────────────────────┐   ┌──────────────────────┐
                           │ Interne API (read-only) │◄──┤ mart                 │
                           │ FastAPI, OIDC (SSO)     │   └──────┬───────────────┘
                           └───────────┬─────────────┘          │ Snapshot-Export (JSON/CSV)
                                       ▼                        ▼
                           ┌─────────────────────────┐   ┌──────────────────────────┐
                           │ Internes Dashboard      │   │ Öffentliches Dashboard   │
                           │ (Intranet, SSO)         │   │ statische Seite + JSON   │
                           └─────────────────────────┘   │ (DMZ, keine DB, kein API)│
                                                         └──────────────────────────┘
```

**Grundidee:** Die öffentliche Seite ist **rein statisch** und bekommt nur aggregierte
Snapshots. Aus dem Internet führt kein Weg zur Datenbank oder zu optiGov. Das verkleinert die
Angriffsfläche drastisch, erfüllt die DSGVO nach dem Prinzip Privacy by Design und sorgt für
hohe Verfügbarkeit.

## 4.2 Technologiewahl

| Baustein | Empfehlung | Begründung |
|----------|-----------|-----------|
| ETL | **Python 3.12**, `httpx`, `pydantic` v2, `tenacity` (Retry/Backoff) | verbreitet, typisierte Validierung jeder API-Antwort |
| Transformation | **dbt-core** auf PostgreSQL | SQL-Modelle versioniert, dokumentiert und getestet (Datentests: not null, unique, Beziehungen, erlaubte Werte) |
| Datenbank | **PostgreSQL 16** | Open Source, JSONB für `raw`, stabil, BSI-Baustein APP.4.3 |
| Orchestrierung | Kubernetes-CronJob **oder** systemd-Timer; bei Wachstum Dagster | bewusst einfach |
| Interne API | **FastAPI**, nur GET, OIDC über das städtische IdP (z. B. Keycloak / ADFS) | schlank, OpenAPI-Doku inklusive |
| Frontend | **TypeScript + React (Vite)** oder **SvelteKit**, statischer Build | eine Codebasis, zwei Build-Ziele (intern / öffentlich) |
| Designsystem | **KERN UX-Standard** (Open-Source-Designsystem für die deutsche Verwaltung) plus städtisches CI | barrierearm, behördentypisch, keine Lizenzkosten |
| Diagramme | **Apache ECharts** (ARIA-Unterstützung, SVG-Renderer) oder Observable Plot; zu jedem Diagramm eine Datentabelle | Barrierefreiheit |
| Hosting | Kommunales Rechenzentrum bzw. IT-Dienstleister, Container (Podman/K8s), **Standort Deutschland** | DSGVO, Souveränität, keine US-Cloud |
| Code und CI | GitLab (on-prem) bzw. openCoDE, eventuell Veröffentlichung als Open Source | Nachnutzung durch andere Kommunen („Public Money, Public Code") |

## 4.3 Tägliche Aktualisierung

| Zeit | Job | Art |
|------|-----|-----|
| 02:00 | Data Hub: CSV-Export für `051170000000` (+ `includeAbove`) sowie Vergleichs-ARS | Voll |
| 02:15 | FIM: Steckbriefe mit `updated_since=<letzter Lauf>` | Delta (Voll am Sonntag) |
| 02:30 | optiGov: Stammdaten (Dienstleistung, Onlinedienst, Formular, Einrichtung, LeiKa) | Delta über `bearbeitet`, Voll-Abgleich am Sonntag |
| 03:00 | optiGov: Nutzung des Vortags (`statistik` bzw. Zählabfragen mit `totalCount`) | inkrementell |
| 03:30 | dbt run + dbt test | Abbruch bei fehlgeschlagenen Tests. Veröffentlicht wird dann nicht, der Vortag bleibt stehen. |
| 04:00 | Snapshot-Export → öffentliche Seite, Open Data | atomarer Austausch |

- **Datenstand-Anzeige:** Jede Kachel zeigt die Aktualität ihrer Quelle, z. B. „PVOG-Stand 29.09.2026".
- **Fehlertoleranz:** Fällt eine Quelle aus, bleiben ihre Daten vom Vortag erhalten und werden gekennzeichnet.
- **Monitoring:** Job-Status, Laufzeit und Anzahl der Datensätze gehen an Prometheus und Grafana. Alarm bei Fehlern oder Sprüngen um mehr als 20 %.

## 4.4 Umgebungen und Deployment
- Umgebungen DEV / TEST / PROD. TEST nutzt eine optiGov-Test-Verwaltung, falls vorhanden.
- CI-Pipeline: Lint, Typecheck, Unit-Tests, dbt-Tests gegen Fixtures, SAST (Semgrep),
  Abhängigkeitsprüfung (OSV/Trivy), Container-Scan, SBOM (CycloneDX), signierte Images (cosign)
- Infrastruktur als Code, Konfiguration über Umgebungsvariablen, Geheimnisse im Vault
  (HashiCorp Vault / OpenBao) oder in K8s-Secrets mit Verschlüsselung

## 4.5 Repository-Struktur (Zielbild)

```
etl/            Python-Paket: Clients (optigov, fim, datahub), Loader, CLI
dbt/            Modelle staging/core/mart, Tests, Doku
api/            FastAPI (intern)
web/            Frontend (Build-Ziele: internal, public)
integration/    Allowlist-Queries, API-Notizen
db/             Schema / Migrationen
deploy/         Container, Helm/Compose, Proxy-Konfiguration
docs/           Planung, Betriebshandbuch, Methodik
```
