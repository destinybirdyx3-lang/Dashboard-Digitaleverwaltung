# 3 · Datenmodell und Kennzahlen

## 3.1 Verknüpfung

```
                     ┌──────────────────────────────┐
                     │  LeiKa-Schlüssel (14-stellig) │  ← zentraler Join-Schlüssel
                     └──────────────┬───────────────┘
        ┌───────────────────────────┼────────────────────────────┐
        │                           │                            │
┌───────▼────────┐        ┌─────────▼─────────┐        ┌─────────▼──────────┐
│ FIM-Portal      │        │ optiGov            │        │ Open-PVOG (Data Hub)│
│ Steckbrief      │        │ Leikaschluessel ⇄  │        │ je LeiKa × ARS      │
│ typisierung     │        │ Dienstleistung     │        │ url, online_status  │
│ ozg[], sdg      │        │  ├ Onlinedienst    │        │ flaechendeckung     │
│ adressat        │        │  ├ Formular        │        │ aktiv, ozgid        │
│ stammtext?      │        │  ├ Terminvorlage   │        └─────────────────────┘
└─────────────────┘        │  └ Einrichtung ─► Amt/FB
                           └────────────────────┘
```

Die Beziehungen sind **n:m**. Eine Mülheimer Dienstleistung kann mehrere LeiKa-Schlüssel
tragen, und ein LeiKa-Schlüssel kann auf mehrere Dienstleistungen verteilt sein. Die
Auswertungseinheit ist deshalb die **Leistung = LeiKa-Schlüssel**. Die Dienstleistungen
werden je Schlüssel aggregiert (Regel: der beste Reifegrad zählt).

Fehlt einer Dienstleistung der LeiKa-Schlüssel, wird sie trotzdem erfasst: als „nicht
zugeordnet" und damit als Qualitätsbefund.

## 3.2 Grundgesamtheit

| Menge | Definition |
|-------|-----------|
| **G** Soll-Katalog | LeiKa-Leistungen mit kommunalem Vollzug laut FIM-`typisierung`, relevant für eine kreisfreie Stadt in NRW. Die genaue Typenliste wird in Phase 1 festgelegt. |
| **A** Angeboten | Schlüssel aus G, denen mindestens eine öffentliche, aktuell sichtbare optiGov-Dienstleistung zugeordnet ist |
| **O** Online | Schlüssel aus A mit mindestens einem Onlinedienst oder Online-Formular (Stufe 3 oder höher) |
| **P** im PVOG gemeldet | Schlüssel mit einem Eintrag in `open-pvog/051170000000` und gesetzter `url` |

Weil Mülheim eine kreisfreie Stadt ist, übernimmt sie auch Kreisaufgaben. Der Soll-Katalog ist
deshalb größer als der einer kreisangehörigen Gemeinde. Das ist beim Vergleich mit anderen
Kommunen zu beachten.

## 3.3 Reifegradmodell pro Leistung

Das Modell lehnt sich an das OZG-Reifegradmodell an. Jede Stufe wird **aus Daten abgeleitet**,
nicht bloß behauptet:

| Stufe | Bezeichnung | Regel (Ableitung) |
|:-:|---|---|
| 0 | Nicht beschrieben | Schlüssel aus G ohne öffentliche optiGov-Dienstleistung |
| 1 | Information | Dienstleistung ist öffentlich und beschrieben (Kurztext oder Volltext vorhanden) |
| 2 | Formular | zusätzlich `formulare_downloads`, `formulare_links` oder `dokumente` vorhanden |
| 3 | Online-Antrag | zusätzlich ein `onlinedienst` mit URL, ein `formular` auf einem Formularserver **oder** laut PVOG eine `url` mit `online_status = ok` |
| 4 | Ende-zu-Ende (indikativ) | Stufe 3 **und** Online-Identifizierung (Vertrauensniveau/BundID) **und** Online-Zahlung, falls Kosten anfallen (`zahlungsweise`) **und** digitale Weiterverarbeitung (DMS-d.3/CMIS-Konfiguration am Formular), soweit technisch ermittelbar |

Ergänzende Kennzeichen, die nicht in die Stufe einfließen:
- **Online-Termin** (Terminvorlage vorhanden)
- **EfA / nachgenutzt**: Die URL-Domain gehört nicht zu Mülheim, oder `art_flaechendeckung` ist landes- oder bundesweit.
- **Selbstauskunft `digitalisiert`**: wird *angezeigt* und gegen die abgeleitete Stufe geprüft.
- **SDG-relevant**: Nach der EU-Verordnung 2018/1724 besteht Online-Pflicht.

Das Modell ist versioniert (`reifegrad_version`). Ändern sich die Regeln, bleiben alte
Snapshots vergleichbar, oder sie werden nachberechnet.

## 3.4 KPI-Katalog

### Öffentliche Kennzahlen

| KPI | Formel | Quelle |
|-----|--------|--------|
| **Online-Quote** | \|O\| / \|G\| | FIM, optiGov, PVOG |
| **Online-Quote (Mülheim + Land/Bund)** | Leistungen, die für Mülheimer online verfügbar sind (`includeAbove=true`), / \|G\| | PVOG |
| **Verteilung Reifegrad** | Anzahl je Stufe 0–4 | abgeleitet |
| **Online-Quote je OZG-Themenfeld** | wie oben, gruppiert nach `ozg.themenfeld` | FIM |
| **Online-Quote je Adressat** | Bürger / Unternehmen | FIM |
| **SDG-Erfüllung** | SDG-relevante Leistungen mit Stufe ≥ 3 / alle SDG-relevanten | FIM, optiGov |
| **Neu online** | Leistungen, die in den letzten 30 Tagen Stufe 3 erreicht haben, mit Link | Snapshots |
| **Trend** | Online-Quote pro Tag, Woche, Monat | Snapshots |
| **Online-Terminbuchung** | Anteil der Leistungen mit online buchbarem Termin (Terminvorlage vorhanden, also Konfiguration, keine Buchungsdaten) | optiGov |

### Interne Steuerungskennzahlen

| KPI | Formel / Beschreibung |
|-----|-----------------------|
| **Priorisierungsliste** | Ohne Nutzungsdaten, nach klaren Regeln: (1) SDG-Pflicht, aber Stufe < 3; (2) Quick Win: im PVOG gibt es für Mülheim einen Onlinedienst von Land, Bund oder EfA, im Portal ist aber keiner verlinkt; (3) kommunal zuständig und Stufe ≤ 1. Später optional eine fachliche Gewichtung durch die Fachbereiche. |
| **EfA-Quote** | nachgenutzte Onlinedienste / alle Onlinedienste |
| **Benchmark** | Online-Quote Mülheim gegen Vergleichskommunen (PVOG-Sicht, gleiche Methodik) |
| **Online-Quote je Organisationseinheit (intern)** | je Dezernat, Amt oder Fachbereich über die `Einrichtung`-Hierarchie |

### Qualitätskennzahlen (Portalredaktion)

| KPI | Befund |
|-----|--------|
| **LeiKa-Zuordnungsquote** | Öffentliche Dienstleistungen mit mindestens einem LeiKa-Schlüssel / alle |
| **Unbekannte Schlüssel** | LeiKa-Schlüssel in optiGov, die das FIM-Portal nicht kennt (veraltet oder falsch) |
| **Nicht gemeldet** | Stufe ≥ 3 in optiGov, aber keine URL im PVOG |
| **Nicht verlinkt** | URL im PVOG für Mülheim, aber kein Onlinedienst in optiGov |
| **Defekte Onlinedienste** | PVOG `online_status = nicht ok` oder `Link.erreichbar = false` |
| **Widerspruch Selbstauskunft** | `digitalisiert = true`, abgeleitete Stufe < 3 (oder umgekehrt) |
| **Veraltete Beschreibung** | `bearbeitet` älter als 12 Monate |
| **Unvollständige Beschreibung** | Kosten, Unterlagen, Bearbeitungsdauer oder Zuständigkeit fehlen |

Bewusst **nicht** im Katalog: Antrags-, Termin- und Nutzungszahlen sowie Durchlaufzeiten.
Das Dashboard misst das digitale **Angebot**, nicht dessen Nutzung (siehe Abschnitt 2.2.2).

## 3.5 Schichten der Datenhaltung

| Schicht | Inhalt | Aufbewahrung |
|---------|--------|--------------|
| `raw` | Unveränderte API-Antworten als JSONB mit Abrufzeit und Hash. **Nur Felder aus der Allowlist.** | 30 Tage |
| `core` | Bereinigte Entitäten: `leistung`, `dienstleistung`, `onlinedienst`, `einrichtung`, `pvog_eintrag`, `fim_steckbrief`, Brückentabellen | aktueller Stand plus SCD2-Historie |
| `mart` | `leistung_reifegrad_tag` (Snapshot je Tag und Leistung), `kpi_tag`, `qualitaet_befund`, `export` | unbegrenzt (nur aggregiert, keine personenbezogenen Daten) |
| `public` | Aus `mart` erzeugte JSON- und CSV-Snapshots für die öffentliche Seite und Open Data | versioniert |

Den Schemaentwurf enthält [`db/schema.sql`](../db/schema.sql).
