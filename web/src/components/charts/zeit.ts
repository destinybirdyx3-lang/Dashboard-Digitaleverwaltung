export interface ZeitSkala {
  x: (t: number) => number;
  ticks: { t: number; label: string }[];
}

const MONAT = new Intl.DateTimeFormat("de-DE", { month: "short", year: "2-digit" });

/** Lineare Zeitachse mit Monats-Ticks (höchstens ~6 Beschriftungen). */
export function zeitSkala(tage: number[], x0: number, x1: number): ZeitSkala {
  const min = Math.min(...tage);
  const max = Math.max(...tage);
  const spanne = Math.max(max - min, 1);
  const x = (t: number) => x0 + ((t - min) / spanne) * (x1 - x0);
  const ticks: { t: number; label: string }[] = [];
  const start = new Date(min);
  const cursor = new Date(start.getFullYear(), start.getMonth() + 1, 1);
  const monate: Date[] = [];
  while (cursor.getTime() <= max) {
    monate.push(new Date(cursor));
    cursor.setMonth(cursor.getMonth() + 1);
  }
  const schritt = Math.max(1, Math.ceil(monate.length / 6));
  monate.forEach((m, i) => {
    if (i % schritt === 0) ticks.push({ t: m.getTime(), label: MONAT.format(m) });
  });
  return { x, ticks };
}

/** Index des Datenpunkts, der der Pointer-Position am nächsten liegt (Fadenkreuz rastet ein). */
export function naechster(xs: number[], px: number): number {
  let best = 0;
  let abstand = Infinity;
  xs.forEach((x, i) => {
    const d = Math.abs(x - px);
    if (d < abstand) { abstand = d; best = i; }
  });
  return best;
}
