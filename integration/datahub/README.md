# Data Hub / Dashboard Digitale Verwaltung (Open-PVOG)

Basis-URL: `https://api.ozg-umsetzung.de/api` – öffentlich, keine Authentifizierung.

## Mülheim an der Ruhr
- ARS (12-stellig): `051170000000` (AGS 05117000). In Phase 1 über `/public/v1/dash/open-ars` verifizieren.

## Tägliche Abrufe

```bash
# 1) Nur Mülheim selbst (ohne Kreis/Land/Bund)
curl -sSf "https://api.ozg-umsetzung.de/api/public/v1/dash/open-pvog/051170000000/export?filetype=csv&includeAbove=false&includeBelow=true" -o pvog_muelheim_eigen.csv

# 2) Alles, was für Mülheimer verfügbar ist (inkl. Land/Bund/EfA)
curl -sSf "https://api.ozg-umsetzung.de/api/public/v1/dash/open-pvog/051170000000/export?filetype=csv&includeAbove=true&includeBelow=true" -o pvog_muelheim_gesamt.csv

# 3) Benchmark (Beispiel-ARS, vorab verifizieren)
for ars in 051130000000 051120000000 051190000000; do
  curl -sSf "https://api.ozg-umsetzung.de/api/public/v1/dash/open-pvog/${ars}/export?filetype=csv&includeAbove=false" -o "pvog_${ars}.csv"
done
```

Wenn der Export an seine Grenze stößt (HTTP 413), wird paginiert über
`/public/v1/dash/open-pvog/{ars}?page=N&size=100` geladen.

## Verwendete Felder
`leika_key`, `leika_name`, `leika_bezeichnung`, `ars`, `ozgid`, `ozg_bezeichnung`, `url`,
`online_status`, `aktiv`, `art_flaechendeckung`, `begruendung_nicht_beruecksichtigt`,
`datenstand_pvog_import`. **Nicht** verwendet wird `export_datum` (deprecated).

## Validierung
- `leika_key` besteht aus 14 Ziffern, `ars` aus 12.
- `online_status` ∈ {`ok`, `nicht ok`}, `aktiv` ∈ {`ja`, `nein`, null}.
- Weicht die Zeilenzahl um mehr als 20 % vom Vortag ab, gibt es einen Alarm und die Veröffentlichung wird angehalten.
