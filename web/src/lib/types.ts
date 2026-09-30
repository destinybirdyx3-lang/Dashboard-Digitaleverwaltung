// Datenverträge mit dem ETL (etl/src/mh_dashboard/export/daten.py)

export interface Anteil {
  zaehler: number;
  nenner: number | null;
  wert: number | null;
}

export interface Quelle {
  quelle: string;
  name: string;
  abgerufen: string;
  datenstand: string;
  datensaetze: number;
}

export interface Gruppe extends Anteil {
  code: string;
  label: string;
}

export interface Uebersicht {
  stichtag: string;
  kommune: string;
  ars: string;
  demo: boolean;
  reifegrad_version: string;
  stufen: Record<string, string>;
  quellen: Quelle[];
  kennzahlen: {
    grundgesamtheit: number | null;
    online_quote: Anteil | null;
    online_quote_inkl_uebergeordnet: Anteil | null;
    angebots_quote: Anteil | null;
    neu_online_30_tage: number | null;
    veraenderung_vorjahr_prozentpunkte: number | null;
    sdg_erfuellung: Anteil | null;
    online_termin_quote: Anteil | null;
  };
  reifegrad_verteilung: (Anteil & { stufe: number; label: string })[];
  themenfelder: Gruppe[];
  adressaten: Gruppe[];
}

export interface Leistung {
  leika: string;
  bezeichnung: string;
  reifegrad: number;
  online: boolean;
  online_inkl_uebergeordnet: boolean;
  url: string | null;
  online_termin: boolean;
  sdg: boolean;
  themenfeld: string;
  adressat: string[];
  grundgesamtheit: boolean;
  angeboten: boolean;
}

export interface Entwicklung {
  stichtag: string;
  reihe: {
    stichtag: string;
    reifegrad: number[];
    online_quote?: number | null;
    online_quote_inkl_uebergeordnet?: number | null;
  }[];
}

export interface Exporte {
  stichtag: string;
  dateien: { art: string; pfad: string; titel: string; groesse: number; sha256: string }[];
  archiv: { monat: string; pfad: string }[];
  lizenz: string;
}

// interne API (etl/src/mh_dashboard/api/app.py)
export interface Steuerung {
  stichtag: string;
  kennzahlen: Record<"online_quote" | "efa_quote" | "leika_zuordnungsquote" | "sdg_erfuellung", Anteil | null>;
  benchmark: (Anteil & { ars: string; name: string; eigene: boolean })[];
  priorisierung: {
    leika: string;
    bezeichnung: string;
    kategorie: string;
    kategorie_label: string;
    rang: number;
    reifegrad: number;
    verfuegbar_unter: string | null;
    einrichtung_ids: number[];
  }[];
  kategorien: Record<string, string>;
}

export interface Einheit {
  id: number;
  name: string;
  typ: string | null;
  uebergeordnet_id: number | null;
  gesamt?: Anteil;
  direkt?: Anteil;
}

export interface InterneLeistung {
  leika: string;
  bezeichnung: string;
  reifegrad: number;
  online: boolean;
  online_inkl_uebergeordnet: boolean;
  url: string | null;
  im_pvog_gemeldet: boolean;
  pvog_online_ok: boolean | null;
  efa: boolean | null;
  selbstauskunft: boolean | null;
  einrichtung_ids: number[];
  grundgesamtheit: boolean;
}

export interface Qualitaet {
  stichtag: string;
  befunde: Record<string, string>;
  anzahl: Record<string, number>;
  eintraege: {
    befund: string;
    befund_label: string;
    dienstleistung_id: number | null;
    leika: string | null;
    einrichtung_ids: number[];
    details: Record<string, unknown>;
    bezeichnung: string;
  }[];
}
