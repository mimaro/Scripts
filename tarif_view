#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tarif.view – Visualisiert ESIT-Preise aus einer CSV als Linienchart.

- Liest 'esit_prices.csv' mit Spalten:
  start_local,end_local,price_chf_per_kwh
- Multipliziert den Preis mit 100 -> Rp/kWh
- X-Achse: lokale Zeit (start_local), Y-Achse: Rp/kWh
- Speichert als PNG und zeigt optional das Fenster an

Abhängigkeiten:
  pip3 install matplotlib

Beispiel:
  python3 tarif.view --csv esit_prices.csv --out esit_prices.png --show
"""

import os
import sys
import argparse

# Headless-Support (z. B. Raspberry Pi ohne Display)
if not os.environ.get("DISPLAY"):
    import matplotlib
    matplotlib.use("Agg")  # vor pyplot!

import csv
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


def read_csv(csv_path):
    """Liest CSV und liefert (times, rp_per_kwh)."""
    times = []
    values = []

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Zeit aus 'start_local' parsen (ISO-8601)
            t = datetime.fromisoformat(row["start_local"])
            # Falls ohne TZ in CSV, versuche Europe/Zurich anzunehmen
            if t.tzinfo is None and ZoneInfo:
                try:
                    t = t.replace(tzinfo=ZoneInfo("Europe/Zurich"))
                except Exception:
                    pass
            # Preis in CHF/kWh -> Rp/kWh
            rp = float(row["price_chf_per_kwh"]) * 100.0
            times.append(t)
            values.append(rp)

    # Sortieren nach Zeit (nur zur Sicherheit)
    pairs = sorted(zip(times, values), key=lambda x: x[0])
    times, values = [p[0] for p in pairs], [p[1] for p in pairs]
    return times, values


def make_plot(times, values, out_path, show=False, draw_now=True):
    """Erstellt das Linienchart und speichert PNG."""
    if not times:
        raise RuntimeError("Keine Datenpunkte gefunden.")

    fig, ax = plt.subplots(figsize=(10, 5))

    ax.plot(times, values, linewidth=1.8)  # keine Farbe explizit setzen

    # Achsenbeschriftungen
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Energiepreis [Rp/kWh]")
    # Titel mit Datumsspanne
    start_dt = times[0]
    end_dt = times[-1]
    if start_dt.date() == end_dt.date():
        title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')}"
    else:
        title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')} bis {end_dt.strftime('%Y-%m-%d')}"
    ax.set_title(title)

    # X-Achse formatieren
    # Wenn Zeitspanne <= 36h: Stunden-Minuten anzeigen
    span_hours = (end_dt - start_dt).total_seconds() / 3600.0
    if span_hours <= 36:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())

    fig.autofmt_xdate()
    ax.grid(True, which="both", linestyle="--", alpha=0.4)

    # Optionale "Jetzt"-Linie
    if draw_now:
        try:
            if times[0].tzinfo:
                now = datetime.now(times[0].tzinfo)
            else:
                now = datetime.now()
            ax.axvline(now, linestyle=":", linewidth=1.2)  # keine Farbe setzen
        except Exception:
            pass

    # Layout & speichern
    plt.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"Chart gespeichert: {os.path.abspath(out_path)}")

    if show:
        # Nur anzeigen, wenn ein Display verfügbar ist
        try:
            plt.show()
        except Exception:
            pass
    plt.close(fig)


def parse_args():
    p = argparse.ArgumentParser(description="Visualisiert ESIT-Preise aus CSV als Linienchart")
    p.add_argument("--csv", default="esit_prices.csv", help="Pfad zur CSV-Datei")
    p.add_argument("--out", default="esit_prices.png", help="Pfad zur Ausgabedatei (PNG)")
    p.add_argument("--show", action="store_true", help="Chart nach dem Speichern anzeigen (falls Display vorhanden)")
    p.add_argument("--no-now-line", action="store_true", help="Keine vertikale Linie für 'Jetzt' zeichnen")
    return p.parse_args()


def main():
    args = parse_args()

    if not os.path.exists(args.csv):
        print(f"CSV nicht gefunden: {args.csv}", file=sys.stderr)
        sys.exit(1)

    try:
        times, values = read_csv(args.csv)
    except Exception as e:
        print(f"Fehler beim Lesen der CSV: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        make_plot(times, values, args.out, show=args.show, draw_now=not args.no_now_line)
    except Exception as e:
        print(f"Fehler beim Erstellen des Charts: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()
