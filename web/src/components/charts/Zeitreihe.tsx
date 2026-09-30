import { forwardRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { fmtDatum, fmtProzent } from "../../lib/format";
import { Tooltip, type TooltipZustand } from "./Tooltip";
import { useBreite } from "./useBreite";
import { naechster, zeitSkala } from "./zeit";

export interface Serie {
  id: string;
  label: string;
  farbe: string;
  werte: (number | null)[];
}

const H = 260;
const OBEN = 12;
const UNTEN = 28;
const LINKS = 44;
const RECHTS_LABEL = 150;

/** Linien 0–100 % über die Zeit: 2px-Linien, Endpunkt-Label, Fadenkreuz mit Tooltip über alle Serien. */
export const Zeitreihe = forwardRef<SVGSVGElement, { tage: string[]; serien: Serie[] }>(function Zeitreihe(
  { tage, serien },
  svgRef,
) {
  const [ref, breite] = useBreite<HTMLDivElement>();
  const [index, setIndex] = useState<number | null>(null);
  const schmal = breite < 520;
  const rechts = breite - (schmal ? 12 : RECHTS_LABEL);
  const zeiten = tage.map((t) => new Date(t).getTime());
  const skala = zeitSkala(zeiten, LINKS, rechts);
  const y = (v: number) => OBEN + (1 - v) * (H - OBEN - UNTEN);
  const xs = zeiten.map(skala.x);

  const pfad = (werte: (number | null)[]) =>
    werte.reduce((acc, v, i) => (v == null ? acc : `${acc}${acc === "" || werte[i - 1] == null ? "M" : "L"}${xs[i]},${y(v)}`), "");

  const tip: TooltipZustand | null =
    index === null
      ? null
      : {
          x: (xs[index] ?? 0) - 80,
          y: 0,
          titel: fmtDatum(tage[index]),
          zeilen: serien.map((s) => ({ farbe: s.farbe, label: s.label, wert: fmtProzent(s.werte[index], true) })),
        };

  const bewegen = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.ownerSVGElement?.getBoundingClientRect();
    if (!box) return;
    const px = ((e.clientX - box.left) / box.width) * breite;
    setIndex(naechster(xs, px));
  };
  const tasten = (e: KeyboardEvent<SVGRectElement>) => {
    const aktuell = index ?? tage.length - 1;
    if (e.key === "ArrowLeft") { setIndex(Math.max(0, aktuell - 1)); e.preventDefault(); }
    if (e.key === "ArrowRight") { setIndex(Math.min(tage.length - 1, aktuell + 1)); e.preventDefault(); }
    if (e.key === "Home") { setIndex(0); e.preventDefault(); }
    if (e.key === "End") { setIndex(tage.length - 1); e.preventDefault(); }
  };
  const letzter = tage.length - 1;

  return (
    <div className="mh-viz" ref={ref}>
      <svg ref={svgRef} viewBox={`0 0 ${breite} ${H}`} role="img"
        aria-label={`Verlauf von ${fmtDatum(tage[0])} bis ${fmtDatum(tage[letzter])}: ${serien
          .map((s) => `${s.label} von ${fmtProzent(s.werte[0])} auf ${fmtProzent(s.werte[letzter])}`)
          .join("; ")}`}>
        {[0, 0.25, 0.5, 0.75, 1].map((t) => (
          <g key={t}>
            <line className={t === 0 ? "mh-viz__basis" : "mh-viz__grid"} x1={LINKS} x2={rechts} y1={y(t)} y2={y(t)} />
            <text className="mh-viz__achse" x={LINKS - 8} y={y(t) + 4} textAnchor="end">{fmtProzent(t)}</text>
          </g>
        ))}
        {skala.ticks.map((tick) => (
          <text key={tick.t} className="mh-viz__achse" x={skala.x(tick.t)} y={H - 8} textAnchor="middle">{tick.label}</text>
        ))}
        {serien.map((s) => (
          <path key={s.id} d={pfad(s.werte)} fill="none" style={{ stroke: s.farbe }} stroke={s.farbe}
            strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" />
        ))}
        {serien.map((s) => {
          const v = s.werte[letzter];
          if (v == null) return null;
          return (
            <g key={`${s.id}-ende`}>
              <circle cx={xs[letzter]} cy={y(v)} r={4} style={{ fill: s.farbe, stroke: "var(--viz-surface)" }} strokeWidth={2} />
              {!schmal && (
                <text x={(xs[letzter] ?? 0) + 10} y={y(v) + 4} style={{ fill: "var(--viz-ink)", fontSize: 13 }}>
                  {fmtProzent(v)} {s.label}
                </text>
              )}
            </g>
          );
        })}
        {index !== null && (
          <g data-nicht-exportieren>
            <line x1={xs[index]} x2={xs[index]} y1={OBEN} y2={H - UNTEN} className="mh-viz__basis" />
            {serien.map((s) => {
              const v = s.werte[index];
              return v == null ? null : (
                <circle key={s.id} cx={xs[index]} cy={y(v)} r={4} style={{ fill: s.farbe, stroke: "var(--viz-surface)" }} strokeWidth={2} />
              );
            })}
          </g>
        )}
        <rect className="mh-viz__hit" x={LINKS} y={OBEN} width={Math.max(rechts - LINKS, 1)} height={H - OBEN - UNTEN}
          tabIndex={0} role="slider" aria-label="Zeitpunkt wählen (Pfeiltasten)" aria-valuemin={0} aria-valuemax={letzter}
          aria-valuenow={index ?? letzter} aria-valuetext={tip ? `${tip.titel}: ${tip.zeilen.map((z) => `${z.label} ${z.wert}`).join(", ")}` : undefined}
          onPointerMove={bewegen} onPointerLeave={() => setIndex(null)} onFocus={() => setIndex(letzter)}
          onBlur={() => setIndex(null)} onKeyDown={tasten} data-nicht-exportieren />
      </svg>
      <Tooltip zustand={tip} breite={breite} />
    </div>
  );
});
