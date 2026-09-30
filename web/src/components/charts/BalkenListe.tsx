import { forwardRef, useState } from "react";
import { fmtProzent, fmtZahl } from "../../lib/format";
import { Tooltip, type TooltipZustand } from "./Tooltip";
import { useBreite } from "./useBreite";

export interface BalkenEintrag {
  id: string;
  label: string;
  zaehler: number;
  nenner: number;
  hervorheben?: boolean;
}

const ZEILE = 34;
const BALKEN = 16;

/** Horizontale Balken (Anteile 0–100 %), eine Serie; optional ein hervorgehobener Eintrag, Rest zurückgenommen. */
export const BalkenListe = forwardRef<SVGSVGElement, { eintraege: BalkenEintrag[]; einheit?: string; betonung?: boolean }>(
  function BalkenListe({ eintraege, einheit = "Leistungen", betonung = false }, svgRef) {
    const [ref, breite] = useBreite<HTMLDivElement>();
    const [tip, setTip] = useState<TooltipZustand | null>(null);
    const [aktiv, setAktiv] = useState<string | null>(null);
    const schmal = breite < 560;
    const labelBreite = schmal ? 0 : Math.min(260, Math.round(breite * 0.34));
    const wertBreite = 52;
    const plotX = labelBreite;
    const plotBreite = breite - labelBreite - wertBreite;
    const zeilenhoehe = schmal ? ZEILE + 18 : ZEILE;
    const hoehe = eintraege.length * zeilenhoehe + 22;

    return (
      <div className="mh-viz" ref={ref}>
        <svg ref={svgRef} viewBox={`0 0 ${breite} ${hoehe}`} role="img"
          aria-label={eintraege.map((e) => `${e.label}: ${fmtProzent(e.nenner ? e.zaehler / e.nenner : 0)}`).join(", ")}>
          {[0, 0.5, 1].map((t) => (
            <g key={t}>
              <line className="mh-viz__grid" x1={plotX + t * plotBreite} x2={plotX + t * plotBreite} y1={0} y2={hoehe - 20} />
              <text className="mh-viz__achse" x={plotX + t * plotBreite} y={hoehe - 4}
                textAnchor={t === 0 ? "start" : t === 1 ? "end" : "middle"}>{fmtProzent(t)}</text>
            </g>
          ))}
          {eintraege.map((e, i) => {
            const quote = e.nenner ? e.zaehler / e.nenner : 0;
            const y0 = i * zeilenhoehe + (schmal ? 18 : 0);
            const yb = y0 + (ZEILE - BALKEN) / 2;
            const w = Math.max(quote * plotBreite, quote > 0 ? 4 : 0);
            const farbe = betonung && !e.hervorheben ? "var(--viz-neben)" : "var(--viz-serie-1)";
            const r = Math.min(4, w / 2);
            const zeige = () => {
              setAktiv(e.id);
              setTip({ x: plotX + w - 80, y: yb + BALKEN + 4, titel: e.label,
                zeilen: [{ label: "online", wert: `${fmtProzent(quote)} · ${fmtZahl(e.zaehler)} von ${fmtZahl(e.nenner)} ${einheit}` }] });
            };
            const verberge = () => { setAktiv(null); setTip(null); };
            return (
              <g key={e.id} className="mh-viz__marke" data-aktiv={aktiv === null || aktiv === e.id}>
                <text x={schmal ? 0 : labelBreite - 12} y={schmal ? y0 - 4 : yb + BALKEN / 2 + 4}
                  textAnchor={schmal ? "start" : "end"}
                  style={{ fill: "var(--viz-ink)", fontSize: 14, fontWeight: e.hervorheben ? 600 : 400 }}>
                  {e.label.length > 38 && !schmal ? `${e.label.slice(0, 36)}…` : e.label}
                </text>
                {w > 0 && (
                  <path fill={farbe} style={{ fill: farbe }}
                    d={`M${plotX},${yb} H${plotX + w - r} Q${plotX + w},${yb} ${plotX + w},${yb + r} V${yb + BALKEN - r} Q${plotX + w},${yb + BALKEN} ${plotX + w - r},${yb + BALKEN} H${plotX} Z`} />
                )}
                <text className="mh-viz__wert" x={plotX + plotBreite + 8} y={yb + BALKEN / 2 + 4}>{fmtProzent(quote)}</text>
                <rect className="mh-viz__hit" x={0} y={y0 - (schmal ? 18 : 0)} width={breite} height={zeilenhoehe} tabIndex={0}
                  role="button" aria-label={`${e.label}: ${fmtProzent(quote)}, ${fmtZahl(e.zaehler)} von ${fmtZahl(e.nenner)} ${einheit}`}
                  onPointerEnter={zeige} onPointerLeave={verberge} onFocus={zeige} onBlur={verberge} data-nicht-exportieren />
              </g>
            );
          })}
          <line className="mh-viz__basis" x1={plotX} x2={plotX} y1={0} y2={hoehe - 20} />
        </svg>
        <Tooltip zustand={tip} breite={breite} />
      </div>
    );
  },
);
