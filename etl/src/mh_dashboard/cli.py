"""Kommandozeile: ``mh-dashboard <befehl>``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date

from . import db, pipeline
from .config import get_settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="mh-dashboard", description="Digitalisierungs-Dashboard Mülheim an der Ruhr")
    sub = parser.add_subparsers(dest="befehl", required=True)
    sub.add_parser("migrate", help="Datenbankschema anlegen/aktualisieren")
    fetch = sub.add_parser("fetch", help="Quellen abrufen")
    fetch.add_argument("quelle", choices=["optigov", "fim", "datahub", "alle"])
    tr = sub.add_parser("transform", help="Kennzahlen für einen Stichtag berechnen")
    tr.add_argument("--stichtag", type=date.fromisoformat, default=date.today())
    ex = sub.add_parser("export", help="Veröffentlichungspaket (JSON, PDF, CSV/XLSX) erzeugen")
    ex.add_argument("--stichtag", type=date.fromisoformat)
    sub.add_parser("run", help="Täglicher Gesamtlauf: abrufen, transformieren, veröffentlichen")
    demo = sub.add_parser("demo", help="Demodaten laden und veröffentlichen (nur Entwicklung/Test)")
    demo.add_argument("--ohne-historie", action="store_true")
    demo.add_argument("--heute", type=date.fromisoformat, default=date.today())
    sub.add_parser("purge-raw", help="Rohdaten älter als 30 Tage löschen")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    for noisy in ("fontTools", "weasyprint", "httpx"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    settings = get_settings()
    with db.connect(settings.database_url) as conn:
        if args.befehl == "migrate":
            result: object = {"angewendet": db.migrate(conn)}
        elif args.befehl == "fetch":
            jobs = {"optigov": pipeline.fetch_optigov, "fim": pipeline.fetch_fim, "datahub": pipeline.fetch_datahub}
            names = list(jobs) if args.quelle == "alle" else [args.quelle]
            result = {n: jobs[n](conn, settings) for n in names}
        elif args.befehl == "transform":
            result = pipeline.transform(conn, settings, args.stichtag)
        elif args.befehl == "export":
            result = pipeline.export(conn, settings, args.stichtag)
        elif args.befehl == "run":
            db.migrate(conn)
            result = pipeline.run_all(conn, settings)
        elif args.befehl == "demo":
            if settings.env == "prod":
                parser.error("Demodaten sind in Produktion nicht erlaubt.")
            db.migrate(conn)
            result = pipeline.load_demo(conn, settings, args.heute, not args.ohne_historie)
        else:
            result = {"geloescht": db.purge_raw(conn)}
    json.dump(result, sys.stdout, ensure_ascii=False, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
