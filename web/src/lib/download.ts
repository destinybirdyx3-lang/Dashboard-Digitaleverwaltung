// Export einzelner Diagramme und Tabellen (clientseitig, ohne Serveraufruf).

function speichern(blob: Blob, dateiname: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = dateiname;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function csvWert(v: unknown): string {
  let text = v == null ? "" : String(v);
  if (/^[=+\-@\t\r]/.test(text)) text = `'${text}`; // Schutz vor Formel-Injection
  return /[";\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function csvHerunterladen(dateiname: string, kopf: string[], zeilen: unknown[][]) {
  const text = [kopf, ...zeilen].map((z) => z.map(csvWert).join(";")).join("\r\n");
  speichern(new Blob(["﻿" + text], { type: "text/csv;charset=utf-8" }), dateiname);
}

const STIL_EIGENSCHAFTEN = ["fill", "stroke", "stroke-width", "opacity", "fill-opacity", "font-family", "font-size",
  "font-weight", "text-anchor", "dominant-baseline", "stroke-linecap", "stroke-linejoin"];

/** Kopie des SVG mit eingebetteten berechneten Farben (CSS-Variablen gelten außerhalb der Seite nicht). */
function eigenstaendig(svg: SVGSVGElement, titel: string, quelle: string): SVGSVGElement {
  const kopie = svg.cloneNode(true) as SVGSVGElement;
  const original = [svg, ...svg.querySelectorAll("*")];
  const ziel = [kopie, ...kopie.querySelectorAll("*")];
  original.forEach((el, i) => {
    const stil = getComputedStyle(el);
    const t = ziel[i] as SVGElement;
    for (const eigenschaft of STIL_EIGENSCHAFTEN) t.style.setProperty(eigenschaft, stil.getPropertyValue(eigenschaft));
  });
  kopie.querySelectorAll("[data-nicht-exportieren]").forEach((el) => el.remove());
  const { width, height } = svg.viewBox.baseVal;
  const kopfhoehe = 44;
  kopie.setAttribute("viewBox", `0 ${-kopfhoehe} ${width} ${height + kopfhoehe + 22}`);
  kopie.setAttribute("width", String(width));
  kopie.setAttribute("height", String(height + kopfhoehe + 22));
  kopie.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const ns = "http://www.w3.org/2000/svg";
  const hintergrund = document.createElementNS(ns, "rect");
  Object.entries({ x: 0, y: -kopfhoehe, width, height: height + kopfhoehe + 22, fill: "#ffffff" })
    .forEach(([k, v]) => hintergrund.setAttribute(k, String(v)));
  kopie.insertBefore(hintergrund, kopie.firstChild);
  const kopf = document.createElementNS(ns, "text");
  kopf.setAttribute("x", "0"); kopf.setAttribute("y", String(-kopfhoehe + 20));
  kopf.setAttribute("style", "font: 600 16px 'Fira Sans', sans-serif; fill: #131525");
  kopf.textContent = titel;
  const fuss = document.createElementNS(ns, "text");
  fuss.setAttribute("x", "0"); fuss.setAttribute("y", String(height + 16));
  fuss.setAttribute("style", "font: 11px 'Fira Sans', sans-serif; fill: #52514e");
  fuss.textContent = quelle;
  kopie.append(kopf, fuss);
  return kopie;
}

export function svgHerunterladen(svg: SVGSVGElement, dateiname: string, titel: string, quelle: string) {
  const text = new XMLSerializer().serializeToString(eigenstaendig(svg, titel, quelle));
  speichern(new Blob([text], { type: "image/svg+xml" }), `${dateiname}.svg`);
}

export async function pngHerunterladen(svg: SVGSVGElement, dateiname: string, titel: string, quelle: string) {
  const kopie = eigenstaendig(svg, titel, quelle);
  const breite = Number(kopie.getAttribute("width"));
  const hoehe = Number(kopie.getAttribute("height"));
  const url = URL.createObjectURL(new Blob([new XMLSerializer().serializeToString(kopie)], { type: "image/svg+xml" }));
  try {
    const bild = new Image();
    bild.src = url;
    await bild.decode();
    const canvas = document.createElement("canvas");
    const skala = 2;
    canvas.width = breite * skala;
    canvas.height = hoehe * skala;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.scale(skala, skala);
    ctx.drawImage(bild, 0, 0, breite, hoehe);
    const blob = await new Promise<Blob | null>((r) => canvas.toBlob(r, "image/png"));
    if (blob) speichern(blob, `${dateiname}.png`);
  } finally {
    URL.revokeObjectURL(url);
  }
}
