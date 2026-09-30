# 6 · UX und Design

## 6.1 Leitlinien
1. **Eine Kernaussage pro Ansicht.** Oben steht die Antwort, darunter die Details (Progressive Disclosure).
2. **Ehrlich und erklärt.** Jede Zahl hat einen Info-Hinweis zu Definition, Quelle und Datenstand. Eine Methodikseite erklärt das Reifegradmodell und die Zuständigkeiten (Bund, Land, Kommune).
3. **Nützlich für Bürgerinnen und Bürger.** Das Dashboard ist auch ein Wegweiser: Leistung suchen, Reifegrad sehen, direkt zum Onlinedienst springen.
4. **Mobile first.** Die öffentliche Seite wird überwiegend auf dem Smartphone aufgerufen.
5. **Konsistent mit der Verwaltung.** KERN UX-Standard plus städtisches Corporate Design, Hell- und Dunkelmodus.

## 6.2 Seitenstruktur – öffentlich

| Seite | Inhalte |
|-------|--------|
| **Überblick** | 3–4 Kennzahl-Kacheln (Online-Quote, Anzahl Online-Leistungen, neu online in den letzten 30 Tagen, Veränderung zum Vorjahr), Digitalisierungstrichter G → A → O, Trendlinie |
| **Themen** | Online-Quote je OZG-Themenfeld (horizontale Balken, sortiert) und je Lebenslage |
| **Leistungen finden** | Suche und Filter (Thema, Reifegrad, Adressat), Liste mit Reifegrad-Badge und „Jetzt online erledigen"-Link |
| **Entwicklung** | Zeitverlauf der Reifegradverteilung (gestapelte Fläche), Meilensteine |
| **Methodik & Open Data** | Definitionen, Quellen, Datenstand, CSV/JSON-Download, API-Hinweis, Lizenz (Datenlizenz Deutschland – Namensnennung 2.0) |
| **Bericht & Export** | Kurzbericht als PDF zum Herunterladen, Archiv der Monatsberichte, Datenexport (CSV/XLSX) |

## 6.3 Seitenstruktur – intern (zusätzlich)

| Seite | Inhalte |
|-------|--------|
| **Steuerung** | Priorisierungsliste (SDG-Pflicht, Quick Wins, kommunale Lücken), Ziel-Ist-Vergleich, Benchmark mit Vergleichskommunen, interner Steuerungsbericht als PDF |
| **Organisationseinheiten** | Online-Quote je Dezernat, Amt oder Fachbereich, Drill-down auf die Leistungsliste |
| **Datenqualität** | Aufgabenliste der Befunde (Abschnitt 3.4) mit Filter nach Fachbereich, Export als Arbeitsliste |

## 6.4 Visualisierungsregeln
- Kennzahl-Kacheln: großer Wert, Einheit, Vergleichswert, Sparkline, Datenstand.
- Reifegrad-Farbskala mit fünf Stufen, sequentiell, farbenblindtauglich geprüft, immer beschriftet.
- Keine 3D-Diagramme, keine Tachometer. Balken statt Torten bei mehr als drei Kategorien.
- Anteile immer mit Grundgesamtheit anzeigen („142 von 575").
- Leere oder unvollständige Daten sichtbar kennzeichnen statt sie wegzulassen.

## 6.5 Export in der Oberfläche
- Jede Seite hat oben rechts einen Button **„Exportieren"** mit den Optionen: Kurzbericht (PDF),
  diese Ansicht (CSV), Druckansicht.
- Jedes Diagramm hat ein Menü: als Bild speichern (SVG/PNG), Daten als CSV, Tabelle anzeigen.
- Der PDF-Kurzbericht folgt demselben Aufbau wie die Überblicksseite. Wer die Seite kennt,
  findet sich im Bericht sofort zurecht.
- Exporte sind barrierefrei: PDF/UA mit Tags und Alternativtexten, CSV mit Kopfzeile.

## 6.6 Nutzerforschung
- In Phase 1 kurze Interviews mit 5–8 Personen: Verwaltungsvorstand, zwei Fachbereiche,
  Redaktion, Bürgerinnen und Bürger (z. B. über den Bürgerservice).
- In Phase 3 ein Usability-Test des Klick-Prototyps, eingeschlossen Menschen, die mit
  Screenreader arbeiten.
