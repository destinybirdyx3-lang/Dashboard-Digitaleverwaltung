# FIM-Portal

Basis-URL: `https://fimportal.de` (API alternativ auch unter `schema.fim.fitko.net`).
Öffentlich, IP-basiertes Rate-Limit (bei HTTP 429 exponentieller Backoff).

## Abrufe

| Zweck | Aufruf |
|-------|--------|
| Initial alle Steckbriefe | `GET /api/v1/leistung-steckbriefe?limit=200&offset=N&order_by=leistungsschluessel_asc` |
| Täglich Änderungen | `GET /api/v1/leistung-steckbriefe?updated_since=<ISO-8601>&limit=200` |
| Einzelner Schlüssel | `GET /api/v1/leistung-steckbriefe/{leistungsschluessel}` |
| Stammtext/PVOG-Text vorhanden? | `GET /api/v1/leistung-stammtexte?leistungsschluessel=…&source=pvog` |
| Ausbau: Prozesse | `GET /api/v0/processes?fts_query=<leistungsschluessel>` |

## Verwendete Felder (Steckbrief)
Leistungsschlüssel, Titel / Leistungsbezeichnung, `leistungstyp`, `typisierung`, `leistungsadressat`,
`freigabe_status`, `ozg[]` (`id`, `themenfeld`, `themenfeld_label`), SDG-Codes,
`klassifizierung` (PV-Lagen, `urn:xoev-de:fim:codeliste:pvlagen`), `geaendert_datum_zeit`.

Hinweis: Die Antwort der Steckbrief-Endpunkte ist in der OpenAPI-Spezifikation nicht
typisiert (`schema: {}`). Die genaue Feldstruktur wird in Phase 1 aus echten Antworten
abgeleitet und als `pydantic`-Modell festgehalten.
