import { useEffect, useRef, useState } from "react";

/** Misst die verfügbare Breite, damit Diagramme im Pixelraster und ohne horizontales Scrollen zeichnen. */
export function useBreite<T extends HTMLElement>(start = 640) {
  const ref = useRef<T>(null);
  const [breite, setBreite] = useState(start);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const beobachter = new ResizeObserver(([eintrag]) => {
      if (eintrag) setBreite(Math.max(280, Math.round(eintrag.contentRect.width)));
    });
    beobachter.observe(el);
    return () => beobachter.disconnect();
  }, []);
  return [ref, breite] as const;
}
