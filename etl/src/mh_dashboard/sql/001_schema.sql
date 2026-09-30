-- Datenmodell des Digitalisierungs-Dashboards (PostgreSQL 16).
-- Grundsatz: nur Angebotsdaten (Leistungen, Onlinedienste, Formulare, Organisationseinheiten).
-- Keine personenbezogenen Daten, keine Nutzungs- oder Vorgangsdaten (Anträge, Termine, Statistik).

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

-- ───────────── raw: unveränderte API-Antworten (nur Allowlist-Felder), 30 Tage Aufbewahrung ─────────────
CREATE TABLE IF NOT EXISTS raw.etl_lauf (
    lauf_id      uuid PRIMARY KEY,
    quelle       text        NOT NULL CHECK (quelle IN ('optigov', 'fim', 'datahub', 'demo', 'transform', 'export')),
    gestartet    timestamptz NOT NULL DEFAULT now(),
    beendet      timestamptz,
    status       text        NOT NULL DEFAULT 'laeuft' CHECK (status IN ('laeuft', 'ok', 'fehler')),
    datensaetze  integer,
    fehler       text
);

CREATE TABLE IF NOT EXISTS raw.api_response (
    id             bigserial PRIMARY KEY,
    lauf_id        uuid        NOT NULL REFERENCES raw.etl_lauf (lauf_id) ON DELETE CASCADE,
    quelle         text        NOT NULL,
    endpunkt       text        NOT NULL,
    parameter      jsonb       NOT NULL DEFAULT '{}',
    abgerufen_am   timestamptz NOT NULL DEFAULT now(),
    inhalt_sha256  text        NOT NULL,
    inhalt         jsonb       NOT NULL
);
CREATE INDEX IF NOT EXISTS api_response_quelle_idx ON raw.api_response (quelle, abgerufen_am DESC);

-- Datenstand je Quelle (für die Anzeige „Datenstand“ und Fehlertoleranz)
CREATE TABLE IF NOT EXISTS raw.quelle_stand (
    quelle          text PRIMARY KEY,
    stand           timestamptz NOT NULL,
    datenstand_extern date,
    datensaetze     integer NOT NULL,
    demo            boolean NOT NULL DEFAULT false
);

-- ───────────── core: aktueller, bereinigter Stand (Historie liegt in den mart-Snapshots) ─────────────
CREATE TABLE IF NOT EXISTS core.leistung (
    leika_schluessel      char(14) PRIMARY KEY CHECK (leika_schluessel ~ '^\d{14}$'),
    bezeichnung           text    NOT NULL,
    leistungstyp          text,
    typisierung           text[]  NOT NULL DEFAULT '{}',
    leistungsadressat     text[]  NOT NULL DEFAULT '{}',
    ozg_ids               text[]  NOT NULL DEFAULT '{}',
    ozg_themenfeld        text,
    ozg_themenfeld_label  text,
    sdg_codes             text[]  NOT NULL DEFAULT '{}',
    pv_lagen_codes        text[]  NOT NULL DEFAULT '{}',
    fim_freigabe_status   smallint,
    fim_geaendert_am      timestamptz,
    in_fim                boolean NOT NULL DEFAULT false,
    in_optigov_katalog    boolean NOT NULL DEFAULT false
);

CREATE TABLE IF NOT EXISTS core.einrichtung (
    optigov_id        integer PRIMARY KEY,
    name              text    NOT NULL,
    kurzbezeichnung   text,
    typ               text,
    uebergeordnet_id  integer,
    oeffentlich       boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS core.dienstleistung (
    optigov_id                integer PRIMARY KEY,
    name                      text    NOT NULL,
    oeffentlich               boolean NOT NULL,
    aktuell_sichtbar          boolean NOT NULL,
    selbstauskunft_digital    boolean NOT NULL,
    hat_beschreibung          boolean NOT NULL,
    hat_kosten                boolean NOT NULL,
    hat_unterlagen            boolean NOT NULL,
    hat_bearbeitungsdauer     boolean NOT NULL,
    anzahl_formular_downloads integer NOT NULL DEFAULT 0,
    hat_online_termin         boolean NOT NULL,
    anzahl_links              integer NOT NULL DEFAULT 0,
    anzahl_links_defekt       integer NOT NULL DEFAULT 0,
    themenfelder              text[]  NOT NULL DEFAULT '{}',
    infodienst_aktualisiert   timestamptz,
    erstellt_am               timestamptz NOT NULL,
    bearbeitet_am             timestamptz
);

CREATE TABLE IF NOT EXISTS core.dienstleistung_leika (
    dienstleistung_id integer  NOT NULL REFERENCES core.dienstleistung (optigov_id) ON DELETE CASCADE,
    leika_schluessel  char(14) NOT NULL,   -- bewusst ohne FK: unbekannte Schlüssel sind ein Qualitätsbefund
    herkunft          text     NOT NULL CHECK (herkunft IN ('direkt', 'infodienst')),
    PRIMARY KEY (dienstleistung_id, leika_schluessel, herkunft)
);

CREATE TABLE IF NOT EXISTS core.dienstleistung_einrichtung (
    dienstleistung_id integer NOT NULL REFERENCES core.dienstleistung (optigov_id) ON DELETE CASCADE,
    einrichtung_id    integer NOT NULL,
    PRIMARY KEY (dienstleistung_id, einrichtung_id)
);

CREATE TABLE IF NOT EXISTS core.onlinedienst (
    optigov_id        integer PRIMARY KEY,
    name              text NOT NULL,
    typ               text,
    url               text,
    url_host          text,
    eigener_dienst    boolean,
    vertrauensniveau  text,
    zahlungsweise     text,
    formular_id       integer
);

CREATE TABLE IF NOT EXISTS core.dienstleistung_onlinedienst (
    dienstleistung_id integer NOT NULL REFERENCES core.dienstleistung (optigov_id) ON DELETE CASCADE,
    onlinedienst_id   integer NOT NULL,
    PRIMARY KEY (dienstleistung_id, onlinedienst_id)
);

CREATE TABLE IF NOT EXISTS core.formular (
    optigov_id                 integer PRIMARY KEY,
    titel                      text NOT NULL,
    url                        text,
    benoetigte_vertrauensstufe text,
    anbieter                   text
);

CREATE TABLE IF NOT EXISTS core.dienstleistung_formular (
    dienstleistung_id integer NOT NULL REFERENCES core.dienstleistung (optigov_id) ON DELETE CASCADE,
    formular_id       integer NOT NULL,
    PRIMARY KEY (dienstleistung_id, formular_id)
);

CREATE TABLE IF NOT EXISTS core.pvog_eintrag (
    id                  bigserial PRIMARY KEY,
    ars                 char(12) NOT NULL,
    sicht               text     NOT NULL CHECK (sicht IN ('eigen', 'inkl_uebergeordnet')),
    leika_schluessel    char(14) NOT NULL,
    ars_name            text,
    leika_name          text,
    url                 text     NOT NULL DEFAULT '',
    url_host            text,
    ozg_id              integer,
    online_ok           boolean,
    aktiv               boolean,
    flaechendeckung     text,
    begruendung_nicht_beruecksichtigt text,
    datenstand_pvog     date
);
CREATE INDEX IF NOT EXISTS pvog_eintrag_idx ON core.pvog_eintrag (ars, sicht, leika_schluessel);

CREATE TABLE IF NOT EXISTS core.verwaltung_faehigkeit (
    id              boolean PRIMARY KEY DEFAULT true CHECK (id),
    bund_id         boolean NOT NULL,
    muk             boolean NOT NULL,
    dms_d3          boolean NOT NULL,
    meet            boolean NOT NULL,
    buergerservice  boolean NOT NULL
);

-- ───────────── mart: Kennzahlen und tägliche Snapshots (nur aggregiert, kein Personenbezug) ─────────────
CREATE TABLE IF NOT EXISTS mart.leistung_reifegrad_tag (
    stichtag                   date     NOT NULL,
    leika_schluessel           char(14) NOT NULL,
    bezeichnung                text     NOT NULL,
    reifegrad                  smallint NOT NULL CHECK (reifegrad BETWEEN 0 AND 4),
    reifegrad_version          text     NOT NULL,
    in_grundgesamtheit         boolean  NOT NULL,
    angeboten                  boolean  NOT NULL,
    online_eigen               boolean  NOT NULL,
    online_inkl_uebergeordnet  boolean  NOT NULL,
    online_url                 text,
    online_termin              boolean  NOT NULL,
    efa_nachnutzung            boolean,
    im_pvog_gemeldet           boolean  NOT NULL,
    pvog_online_ok             boolean,
    selbstauskunft_digital     boolean,
    sdg_relevant               boolean  NOT NULL,
    ozg_themenfeld             text,
    ozg_themenfeld_label       text,
    leistungsadressat          text[]   NOT NULL DEFAULT '{}',
    einrichtung_ids            integer[] NOT NULL DEFAULT '{}',
    dienstleistung_ids         integer[] NOT NULL DEFAULT '{}',
    PRIMARY KEY (stichtag, leika_schluessel)
);

CREATE TABLE IF NOT EXISTS mart.kpi_tag (
    stichtag     date    NOT NULL,
    kpi          text    NOT NULL,
    dimension    text    NOT NULL DEFAULT 'gesamt',
    zaehler      numeric NOT NULL,
    nenner       numeric,
    wert         numeric GENERATED ALWAYS AS (CASE WHEN nenner > 0 THEN zaehler / nenner END) STORED,
    oeffentlich  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (stichtag, kpi, dimension)
);

CREATE TABLE IF NOT EXISTS mart.qualitaet_befund (
    stichtag          date    NOT NULL,
    befund            text    NOT NULL CHECK (befund IN (
                          'ohne_leika', 'leika_unbekannt', 'nicht_gemeldet', 'nicht_verlinkt', 'dienst_defekt',
                          'link_defekt', 'widerspruch_selbstauskunft', 'veraltet', 'unvollstaendig')),
    dienstleistung_id integer,
    leika_schluessel  char(14),
    einrichtung_ids   integer[] NOT NULL DEFAULT '{}',
    details           jsonb   NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS qualitaet_befund_idx ON mart.qualitaet_befund (stichtag, befund);

CREATE TABLE IF NOT EXISTS mart.priorisierung (
    stichtag          date     NOT NULL,
    leika_schluessel  char(14) NOT NULL,
    kategorie         text     NOT NULL CHECK (kategorie IN ('sdg_pflicht', 'quick_win', 'kommunale_luecke')),
    rang              smallint NOT NULL,
    details           jsonb    NOT NULL DEFAULT '{}',
    PRIMARY KEY (stichtag, leika_schluessel)
);

CREATE TABLE IF NOT EXISTS mart.export (
    stichtag          date        NOT NULL,
    art               text        NOT NULL CHECK (art IN (
                          'uebersicht_pdf', 'leistungen_csv', 'leistungen_xlsx', 'kpi_csv', 'snapshot_json')),
    sichtbarkeit      text        NOT NULL CHECK (sichtbarkeit IN ('oeffentlich', 'intern')),
    pfad              text        NOT NULL,
    sha256            text        NOT NULL,
    methodik_version  text        NOT NULL,
    erzeugt_am        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stichtag, art)
);

-- ───────────── Rechte (Least Privilege) – Rollen werden vom Betrieb angelegt ─────────────
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'mh_api_reader') THEN
        GRANT USAGE ON SCHEMA mart, core TO mh_api_reader;
        GRANT SELECT ON ALL TABLES IN SCHEMA mart TO mh_api_reader;
        GRANT SELECT ON core.einrichtung, core.pvog_eintrag TO mh_api_reader;
    END IF;
END $$;
