import { useEffect, useState } from "react";

export class LadeFehler extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

export async function ladeJson<T>(pfad: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(pfad, { signal, credentials: "same-origin", headers: { Accept: "application/json" } });
  if (!response.ok) throw new LadeFehler(response.status, `${pfad}: HTTP ${response.status}`);
  return (await response.json()) as T;
}

export type Ladezustand<T> = { status: "laedt" } | { status: "fehler"; fehler: LadeFehler | Error } | { status: "ok"; daten: T };

export function useDaten<T>(pfad: string | null): Ladezustand<T> {
  const [zustand, setZustand] = useState<Ladezustand<T>>({ status: "laedt" });
  useEffect(() => {
    if (!pfad) return;
    const controller = new AbortController();
    setZustand({ status: "laedt" });
    ladeJson<T>(pfad, controller.signal)
      .then((daten) => setZustand({ status: "ok", daten }))
      .catch((fehler: Error) => {
        if (fehler.name !== "AbortError") setZustand({ status: "fehler", fehler });
      });
    return () => controller.abort();
  }, [pfad]);
  return zustand;
}
