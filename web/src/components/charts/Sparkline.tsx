/** Mini-Verlauf für Kennzahl-Kacheln (dekorativ; Werte stehen auf der Seite „Entwicklung“). */
export function Sparkline({ werte }: { werte: number[] }) {
  if (werte.length < 2) return null;
  const b = 160;
  const h = 32;
  const min = Math.min(...werte);
  const max = Math.max(...werte);
  const spanne = max - min || 1;
  const punkte = werte.map((v, i) => [(i / (werte.length - 1)) * (b - 6) + 3, h - 4 - ((v - min) / spanne) * (h - 8)] as const);
  const letzter = punkte[punkte.length - 1]!;
  return (
    <svg className="mh-kachel__sparkline" viewBox={`0 0 ${b} ${h}`} width={b} height={h} aria-hidden="true" focusable="false">
      <path d={`M${punkte.map((p) => p.join(",")).join("L")}`} fill="none" style={{ stroke: "var(--viz-neben)" }} strokeWidth={2}
        strokeLinejoin="round" strokeLinecap="round" />
      <circle cx={letzter[0]} cy={letzter[1]} r={4} style={{ fill: "var(--viz-serie-1)", stroke: "var(--viz-surface)" }} strokeWidth={2} />
    </svg>
  );
}
