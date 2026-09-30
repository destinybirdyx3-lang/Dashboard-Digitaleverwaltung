-- Entwurf des Datenmodells (PostgreSQL 16). In der Umsetzung als dbt-Modelle / Migrationen.
-- Grundsatz: nur Angebotsdaten (Leistungen, Onlinedienste, Formulare, Organisationseinheiten).
-- Keine personenbezogenen Daten, keine Nutzungs- oder Vorgangsdaten (Anträge, Termine, Statistik).

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS core;
CREATE SCHEMA IF NOT EXISTS mart;

-- ───────────────────────── raw: unveränderte API-Antworten (nur Allowlist-Felder) ─────────
CREATE TABLE raw.api_response (
    id            bigserial PRIMARY KEY,
    quelle        text        NOT NULL CHECK (quelle IN ('optigov', 'fim', 'datahub')),
    endpunkt      text        NOT NULL,          -- z. B. Query-Name oder URL-Pfad
    parameter     jsonb       NOT NULL DEFAULT '{}',
    abgerufen_am  timestamptz NOT NULL DEFAULT now(),
    lauf_id       uuid        NOT NULL,
    inhalt_sha256 text        NOT NULL,
    inhalt        jsonb       NOT NULL
);
CREATE INDEX ON raw.api_response (quelle, endpunkt, abgerufen_am DESC);

CREATE TABLE raw.etl_lauf (
    lauf_id    uuid PRIMARY KEY,
    quelle     text        NOT NULL,
    gestartet  timestamptz NOT NULL,
    beendet    timestamptz,
    status     text        NOT NULL CHECK (status IN ('laeuft', 'ok', 'fehler')),
    datensaetze integer,
    fehler     text
);

-- ───────────────────────── core: bereinigte Entitäten ─────────────────────────────────────
CREATE TABLE core.leistung (                     -- eine Zeile je LeiKa-Schlüssel (FIM + optiGov-Katalog)
    leika_schluessel     char(14) PRIMARY KEY CHECK (leika_schluessel ~ '^\d{14}$'),
    bezeichnung          text NOT NULL,
    leistungstyp         text,                   -- lo / lov / lovd
    typisierung          text[],                 -- FIM-Typisierung
    kommunal_zustaendig  boolean,                -- abgeleitet aus typisierung (Regel versioniert)
    leistungsadressat    text[],                 -- 001 Bürger, 002 Unternehmen, 003 Verwaltung
    ozg_ids              text[],
    ozg_themenfeld       text,
    sdg_codes            text[],
    sdg_relevant         boolean,
    pv_lagen_codes       text[],
    fim_freigabe_status  smallint,
    fim_stammtext_vorhanden boolean,
    fim_geaendert_am     timestamptz,
    aktualisiert_am      timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE core.einrichtung (
    optigov_id        integer PRIMARY KEY,
    name              text NOT NULL,
    kurzbezeichnung   text,
    typ               text,
    uebergeordnet_id  integer REFERENCES core.einrichtung (optigov_id) DEFERRABLE INITIALLY DEFERRED,
    oeffentlich       boolean NOT NULL
);

CREATE TABLE core.dienstleistung (
    optigov_id             integer PRIMARY KEY,
    name                   text    NOT NULL,
    oeffentlich            boolean NOT NULL,
    aktuell_sichtbar       boolean NOT NULL,     -- oeffentlich_anzeigen + sichtbar_von/bis ausgewertet
    selbstauskunft_digital boolean NOT NULL,     -- optiGov "digitalisiert"
    hat_beschreibung       boolean NOT NULL,
    hat_kosten             boolean NOT NULL,
    hat_unterlagen         boolean NOT NULL,
    hat_bearbeitungsdauer  boolean NOT NULL,
    anzahl_formular_downloads integer NOT NULL DEFAULT 0,
    hat_online_termin      boolean NOT NULL,
    anzahl_links_defekt    integer NOT NULL DEFAULT 0,
    erstellt_am            timestamptz NOT NULL,
    bearbeitet_am          timestamptz,
    geloescht_am           timestamptz            -- durch den Voll-Abgleich erkannt
);

CREATE TABLE core.dienstleistung_leika (
    dienstleistung_id integer  REFERENCES core.dienstleistung (optigov_id),
    leika_schluessel  char(14),                  -- bewusst ohne FK: unbekannte Schlüssel sind ein Qualitätsbefund
    herkunft          text NOT NULL CHECK (herkunft IN ('direkt', 'infodienst')),
    PRIMARY KEY (dienstleistung_id, leika_schluessel, herkunft)
);

CREATE TABLE core.dienstleistung_einrichtung (
    dienstleistung_id integer REFERENCES core.dienstleistung (optigov_id),
    einrichtung_id    integer REFERENCES core.einrichtung (optigov_id),
    PRIMARY KEY (dienstleistung_id, einrichtung_id)
);

CREATE TABLE core.onlinedienst (
    optigov_id        integer PRIMARY KEY,
    name              text NOT NULL,
    typ               text,
    url               text,
    url_host          text,                      -- abgeleitet, für die EfA-Heuristik
    eigener_dienst    boolean,                   -- Host gehört zur Stadt
    vertrauensniveau  text,
    zahlungsweise     text,
    formular_id       integer,
    formular_anbieter text
);

CREATE TABLE core.dienstleistung_onlinedienst (
    dienstleistung_id integer REFERENCES core.dienstleistung (optigov_id),
    onlinedienst_id   integer REFERENCES core.onlinedienst (optigov_id),
    PRIMARY KEY (dienstleistung_id, onlinedienst_id)
);

CREATE TABLE core.pvog_eintrag (
    ars                 char(12) NOT NULL,
    leika_schluessel    char(14) NOT NULL,
    url                 text     NOT NULL DEFAULT '',
    sicht               text     NOT NULL CHECK (sicht IN ('eigen', 'inkl_uebergeordnet')),
    ozg_id              integer,
    online_ok           boolean,
    aktiv               boolean,
    flaechendeckung     text,
    begruendung_nicht_beruecksichtigt text,
    datenstand_pvog     date,
    PRIMARY KEY (ars, leika_schluessel, url, sicht)
);

-- ───────────────────────── mart: Kennzahlen und Snapshots ──────────────────────────────────
CREATE TABLE mart.leistung_reifegrad_tag (
    stichtag            date     NOT NULL,
    leika_schluessel    char(14) NOT NULL,
    reifegrad           smallint NOT NULL CHECK (reifegrad BETWEEN 0 AND 4),
    reifegrad_version   text     NOT NULL,
    online_termin       boolean  NOT NULL,
    efa_nachnutzung     boolean,
    im_pvog_gemeldet    boolean  NOT NULL,
    pvog_online_ok      boolean,
    selbstauskunft_digital boolean,
    einrichtung_ids     integer[],
    PRIMARY KEY (stichtag, leika_schluessel)
);

CREATE TABLE mart.kpi_tag (
    stichtag     date    NOT NULL,
    kpi          text    NOT NULL,              -- z. B. 'online_quote', 'sdg_erfuellung'
    dimension    text    NOT NULL DEFAULT 'gesamt',  -- z. B. 'themenfeld:familie_kind', 'einrichtung:123', 'ars:051130000000'
    zaehler      numeric NOT NULL,
    nenner       numeric,
    wert         numeric GENERATED ALWAYS AS (CASE WHEN nenner > 0 THEN zaehler / nenner END) STORED,
    oeffentlich  boolean NOT NULL DEFAULT false,
    PRIMARY KEY (stichtag, kpi, dimension)
);

CREATE TABLE mart.qualitaet_befund (
    stichtag          date    NOT NULL,
    befund            text    NOT NULL,          -- 'ohne_leika', 'leika_unbekannt', 'nicht_gemeldet', 'nicht_verlinkt', 'dienst_defekt', 'widerspruch_selbstauskunft', 'veraltet', 'unvollstaendig'
    dienstleistung_id integer,
    leika_schluessel  char(14),
    einrichtung_ids   integer[],
    details           jsonb   NOT NULL DEFAULT '{}'
);
CREATE INDEX ON mart.qualitaet_befund (stichtag, befund);

-- Erzeugte Exporte (PDF-Kurzbericht, CSV/XLSX, Diagramme) je Stichtag
CREATE TABLE mart.export (
    stichtag          date        NOT NULL,
    art               text        NOT NULL CHECK (art IN ('kurzbericht_pdf', 'steuerungsbericht_pdf', 'leistungen_csv', 'leistungen_xlsx', 'kpi_csv', 'diagramm_svg')),
    sichtbarkeit      text        NOT NULL CHECK (sichtbarkeit IN ('oeffentlich', 'intern')),
    pfad              text        NOT NULL,
    sha256            text        NOT NULL,
    methodik_version  text        NOT NULL,
    erzeugt_am        timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (stichtag, art)
);

-- ───────────────────────── Rechte (Least Privilege) ───────────────────────────────────────
-- CREATE ROLE etl_writer  LOGIN;  -- schreibt raw/core/mart
-- CREATE ROLE api_reader  LOGIN;  -- nur SELECT auf mart
-- GRANT USAGE ON SCHEMA mart TO api_reader;
-- GRANT SELECT ON ALL TABLES IN SCHEMA mart TO api_reader;
