import { forwardRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { fmtDatum, fmtZahl, STUFEN } from "../../lib/format";
import { Tooltip, type TooltipZustand } from "./Tooltip";
import { useBreite } from "./useBreite";
import { naechster, zeitSkala } from "./zeit";

const H = 280;
const OBEN = 12;
const UNTEN = 28;
const LINKS = 48;

/** Gestapelte Flächen der Reifegradstufen über die Zeit (ordinale Rampe, Stufe 4 unten). */
export const StufenFlaeche = forwardRef<SVGSVGElement, { tage: string[]; werte: number[][] }>(function StufenFlaeche(
  { tage, werte },
  svgRef,
) {
  const [ref, breite] = useBreite<HTMLDivElement>();
  const [index, setIndex] = useState<number | null>(null);
  const rechts = breite - 12;
  const zeiten = tage.map((t) => new Date(t).getTime());
  const skala = zeitSkala(zeiten, LINKS, rechts);
  const xs = zeiten.map(skala.x);
  const maxSumme = Math.max(1, ...werte.map((w) => w.reduce((a, b) => a + b, 0)));
  const oben = Math.ceil(maxSumme / 25) * 25;
  const y = (v: number) => OBEN + (1 - v / oben) * (H - OBEN - UNTEN);
  const reihenfolge = [4, 3, 2, 1, 0]; // „digital“ unten, damit Wachstum am Boden sichtbar wird

  const flaechen = reihenfolge.map((stufe, ri) => {
    const unter = werte.map((w) => reihenfolge.slice(0, ri).reduce((a, s) => a + (w[s] ?? 0), 0));
    const ueber = werte.map((w, i) => (unter[i] ?? 0) + (w[stufe] ?? 0));
    const d = `M${xs.map((x, i) => `${x},${y(ueber[i] ?? 0)}`).join("L")}L${[...xs].reverse().map((x, i) => `${x},${y(unter[unter.length - 1 - i] ?? 0)}`).join("L")}Z`;
    return { stufe, d };
  });

  const tip: TooltipZustand | null =
    index === null ? null : {
      x: (xs[index] ?? 0) - 80, y: 0, titel: fmtDatum(tage[index]),
      zeilen: [...reihenfolge].reverse().map((s) => ({
        farbe: `var(--viz-stufe-${s})`, form: "flaeche" as const, label: `${s} · ${STUFEN[s]}`, wert: fmtZahl(werte[index]?.[s] ?? 0),
      })),
    };

  const bewegen = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (box) setIndex(naechster(xs, ((e.clientX - box.left) / box.width) * breite));
  };
  const tasten = (e: KeyboardEvent<SVGRectElement>) => {
    const a = index ?? tage.length - 1;
    if (e.key === "ArrowLeft") { setIndex(Math.max(0, a - 1)); e.preventDefault(); }
    if (e.key === "ArrowRight") { setIndex(Math.min(tage.length - 1, a + 1)); e.preventDefault(); }
  };

  return (
    <div className="mh-viz" ref={ref}>
      <svg ref={svgRef} viewBox={`0 0 ${breite} ${H}`} role="img"
        aria-label={`Reifegradverteilung von ${fmtDatum(tage[0])} bis ${fmtDatum(tage[tage.length - 1])}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line className={t === 0 ? "mh-viz__basis" : "mh-viz__grid"} x1={LINKS} x2={rechts} y1={y(t * oben)} y2={y(t * oben)} />
            <text className="mh-viz__achse" x={LINKS - 8} y={y(t * oben) + 4} textAnchor="end">{fmtZahl(t * oben)}</text>
          </g>
        ))}
        {skala.ticks.map((tick) => (
          <text key={tick.t} className="mh-viz__achse" x={skala.x(tick.t)} y={H - 8} textAnchor="middle">{tick.label}</text>
        ))}
        {flaechen.map((f) => (
          <path key={f.stufe} d={f.d} style={{ fill: `var(--viz-stufe-${f.stufe})`, stroke: "var(--viz-surface)" }} strokeWidth={2}
            strokeLinejoin="round" />
        ))}
        {index !== null && <line data-nicht-exportieren x1={xs[index]} x2={xs[index]} y1={OBEN} y2={H - UNTEN}
          style={{ stroke: "var(--viz-ink)" }} strokeWidth={1} />}
        <rect className="mh-viz__hit" x={LINKS} y={OBEN} width={Math.max(rechts - LINKS, 1)} height={H - OBEN - UNTEN} tabIndex={0}
          role="slider" aria-label="Zeitpunkt wählen (Pfeiltasten)" aria-valuemin={0} aria-valuemax={tage.length - 1}
          aria-valuenow={index ?? tage.length - 1}
          aria-valuetext={tip ? `${tip.titel}: ${tip.zeilen.map((z) => `${z.label} ${z.wert}`).join(", ")}` : undefined}
          onPointerMove={bewegen} onPointerLeave={() => setIndex(null)} onFocus={() => setIndex(tage.length - 1)}
          onBlur={() => setIndex(null)} onKeyDown={tasten} data-nicht-exportieren />
      </svg>
      <Tooltip zustand={tip} breite={breite} />
      <ul className="mh-legende" aria-hidden="true">
        {[0, 1, 2, 3, 4].map((s) => (
          <li key={s}><span className="mh-swatch" style={{ background: `var(--viz-stufe-${s})` }} />{s} · {STUFEN[s]}</li>
        ))}
      </ul>
    </div>
  );
});
