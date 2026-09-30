const zahl = new Intl.NumberFormat("de-DE");
const prozent = new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 0 });
const prozentGenau = new Intl.NumberFormat("de-DE", { style: "percent", maximumFractionDigits: 1 });
const datum = new Intl.DateTimeFormat("de-DE", { day: "2-digit", month: "2-digit", year: "numeric" });
const monat = new Intl.DateTimeFormat("de-DE", { month: "short", year: "2-digit" });

export const fmtZahl = (v: number | null | undefined) => (v == null ? "–" : zahl.format(v));
export const fmtProzent = (v: number | null | undefined, genau = false) =>
  v == null ? "–" : (genau ? prozentGenau : prozent).format(v);
export const fmtDatum = (iso: string | null | undefined) => (iso ? datum.format(new Date(iso)) : "–");
export const fmtMonat = (iso: string) => monat.format(new Date(iso));
export const fmtPunkte = (v: number | null | undefined) =>
  v == null ? "–" : `${v > 0 ? "+" : v < 0 ? "−" : "±"}${zahl.format(Math.abs(v))}`;

export const THEMENFELDER: Record<string, string> = {
  arbeit_ruhestand: "Arbeit & Ruhestand",
  bauen_wohnen: "Bauen & Wohnen",
  bildung: "Bildung",
  ein_auswanderung: "Ein- & Auswanderung",
  engagement_hobby: "Engagement & Hobby",
  familie_kind: "Familie & Kind",
  forschung_foerderung: "Forschung & Förderung",
  gesundheit: "Gesundheit",
  mobilitaet_reisen: "Mobilität & Reisen",
  querschnittsleistungen: "Querschnittsleistungen",
  recht_ordnung: "Recht & Ordnung",
  steuern_zoll: "Steuern & Zoll",
  umwelt: "Umwelt",
  unternehmensfuehrung_entwicklung: "Unternehmensführung & -entwicklung",
  ohne: "Ohne Themenfeld-Zuordnung",
};

export const ADRESSATEN: Record<string, string> = {
  "001": "Bürgerinnen und Bürger",
  "002": "Unternehmen",
  "003": "Verwaltung",
};

export const STUFEN: Record<number, string> = {
  0: "Nicht beschrieben",
  1: "Information",
  2: "Formular",
  3: "Online-Antrag",
  4: "Ende-zu-Ende",
};

export const STUFEN_ERKLAERUNG: Record<number, string> = {
  0: "Die Leistung ist im Serviceportal nicht beschrieben und nicht online verfügbar.",
  1: "Die Leistung ist im Serviceportal beschrieben.",
  2: "Zusätzlich gibt es ein Formular zum Herunterladen.",
  3: "Die Leistung kann online beantragt werden.",
  4: "Online-Antrag mit Online-Ausweis, Online-Bezahlung und digitaler Weiterverarbeitung (indikativ).",
};
