import type { ReactNode } from "react";

export interface TooltipZeile {
  farbe?: string;
  form?: "linie" | "flaeche";
  label: string;
  wert: string;
}

export interface TooltipZustand {
  x: number;
  y: number;
  titel: string;
  zeilen: TooltipZeile[];
}

/** Tooltip ergänzt nur – alle Werte sind auch in der Tabellenansicht erreichbar. */
export function Tooltip({ zustand, breite }: { zustand: TooltipZustand | null; breite: number }): ReactNode {
  if (!zustand) return null;
  const links = Math.min(Math.max(zustand.x + 12, 0), breite - 200);
  return (
    <div className="mh-tooltip" style={{ left: links, top: Math.max(zustand.y - 12, 0) }} role="presentation">
      <div className="mh-tooltip__titel">{zustand.titel}</div>
      {zustand.zeilen.map((z) => (
        <div className="mh-tooltip__zeile" key={z.label}>
          <strong>{z.wert}</strong>
          <span className="mh-tooltip__key">
            {z.farbe && (
              <span
                className={z.form === "flaeche" ? "mh-swatch" : "mh-linekey"}
                style={{ background: z.farbe }}
                aria-hidden="true"
              />
            )}
            {z.label}
          </span>
        </div>
      ))}
    </div>
  );
}
