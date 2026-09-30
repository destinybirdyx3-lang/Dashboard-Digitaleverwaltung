import { forwardRef, useState } from "react";
import { fmtProzent, fmtZahl } from "../../lib/format";
import { Tooltip, type TooltipZustand } from "./Tooltip";
import { useBreite } from "./useBreite";

export interface Stufe {
  stufe: number;
  label: string;
  zaehler: number;
}

const HOEHE = 24;
const GAP = 2;

/** 100-%-Balken der Reifegradstufen (ordinale Rampe, 2px Oberflächen-Lücke zwischen Segmenten). */
export const ReifegradBalken = forwardRef<SVGSVGElement, { stufen: Stufe[]; gesamt: number }>(
  function ReifegradBalken({ stufen, gesamt }, svgRef) {
    const [ref, breite] = useBreite<HTMLDivElement>();
    const [tip, setTip] = useState<TooltipZustand | null>(null);
    const [aktiv, setAktiv] = useState<number | null>(null);
    const sichtbar = stufen.filter((s) => s.zaehler > 0);
    const nutzbar = breite - GAP * Math.max(sichtbar.length - 1, 0);
    let x = 0;
    const segmente = sichtbar.map((s) => {
      const w = gesamt ? (s.zaehler / gesamt) * nutzbar : 0;
      const seg = { ...s, x, w };
      x += w + GAP;
      return seg;
    });
    const hoehe = HOEHE + 26;

    const zeige = (s: (typeof segmente)[number]) => {
      setAktiv(s.stufe);
      setTip({
        x: s.x + s.w / 2 - 80, y: HOEHE + 8, titel: `Stufe ${s.stufe} · ${s.label}`,
        zeilen: [{ label: "Leistungen", wert: `${fmtZahl(s.zaehler)} (${fmtProzent(s.zaehler / gesamt)})` }],
      });
    };
    const verberge = () => { setAktiv(null); setTip(null); };

    return (
      <div className="mh-viz" ref={ref}>
        <svg
          ref={svgRef}
          viewBox={`0 0 ${breite} ${hoehe}`}
          role="img"
          aria-label={`Reifegradverteilung: ${stufen.map((s) => `Stufe ${s.stufe} ${s.label} ${fmtZahl(s.zaehler)}`).join(", ")}`}
        >
          {segmente.map((s, i) => {
            const erstes = i === 0;
            const letztes = i === segmente.length - 1;
            const r = 4;
            // abgerundete Enden nur an den Außenkanten des Balkens
            const pfad = `M${s.x + (erstes ? r : 0)},0 H${s.x + s.w - (letztes ? r : 0)} ${letztes ? `Q${s.x + s.w},0 ${s.x + s.w},${r} V${HOEHE - r} Q${s.x + s.w},${HOEHE} ${s.x + s.w - r},${HOEHE}` : `V${HOEHE}`} H${s.x + (erstes ? r : 0)} ${erstes ? `Q${s.x},${HOEHE} ${s.x},${HOEHE - r} V${r} Q${s.x},0 ${s.x + r},0` : `V0`} Z`;
            const passt = s.w > 64;
            return (
              <g key={s.stufe} className="mh-viz__marke" data-aktiv={aktiv === null || aktiv === s.stufe}>
                <path d={pfad} style={{ fill: `var(--viz-stufe-${s.stufe})` }} />
                {passt && (
                  <text
                    x={s.x + s.w / 2} y={HOEHE / 2 + 4} textAnchor="middle"
                    style={{ fill: `var(--viz-stufe-${s.stufe}-text)`, fontSize: 12, fontWeight: 600 }}
                    aria-hidden="true"
                  >
                    {fmtProzent(s.zaehler / gesamt)}
                  </text>
                )}
                <rect
                  className="mh-viz__hit" x={s.x} y={-4} width={Math.max(s.w, 8)} height={HOEHE + 8}
                  tabIndex={0} role="button"
                  aria-label={`Stufe ${s.stufe} ${s.label}: ${fmtZahl(s.zaehler)} Leistungen, ${fmtProzent(s.zaehler / gesamt)}`}
                  onPointerEnter={() => zeige(s)} onPointerLeave={verberge} onFocus={() => zeige(s)} onBlur={verberge}
                  data-nicht-exportieren
                />
              </g>
            );
          })}
          <text x={0} y={hoehe - 4} className="mh-viz__achse">0 %</text>
          <text x={breite} y={hoehe - 4} textAnchor="end" className="mh-viz__achse">100 % = {fmtZahl(gesamt)} Leistungen</text>
        </svg>
        <Tooltip zustand={tip} breite={breite} />
        <ul className="mh-legende" aria-hidden="true">
          {stufen.map((s) => (
            <li key={s.stufe}>
              <span className="mh-swatch" style={{ background: `var(--viz-stufe-${s.stufe})` }} />
              {s.stufe} · {s.label} ({fmtZahl(s.zaehler)})
            </li>
          ))}
        </ul>
      </div>
    );
  },
);
