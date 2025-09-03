#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tarif.view – Visualisiert ESIT-Preise aus einer CSV als Linienchart.

- Liest 'esit_prices.csv' mit Spalten:
  start_local,end_local,price_chf_per_kwh
- Multipliziert den Preis mit 100 -> Rp/kWh
- X-Achse: lokale Zeit (start_local), Y-Achse: Rp/kWh
- Zeigt den Plot auf dem angeschlossenen Bildschirm
- Es wird **keine Datei gespeichert**
"""

import os
import sys
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
            # Falls keine TZ: Europe/Zurich annehmen
            if t.tzinfo is None and ZoneInfo:
                try:
                    t = t.replace(tzinfo=ZoneInfo("Europe/Zurich"))
                except Exception:
                    pass
            rp = float(row["price_chf_per_kwh"]) * 100.0  # Rp/kWh
            times.append(t)
            values.append(rp)

    pairs = sorted(zip(times, values), key=lambda x: x[0])
    times, values = [p[0] for p in pairs], [p[1] for p in pairs]
    return times, values


def make_plot(times, values, draw_now=True):
    """Erstellt das Linienchart und zeigt es auf dem Bildschirm."""
    if not times:
        raise RuntimeError("Keine Datenpunkte gefunden.")

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(times, values, linewidth=1.8)

    ax.set_xlabel("Zeit")
    ax.set_ylabel("Energiepreis [Rp/kWh]")

    start_dt = times[0]
    end_dt = times[-1]
    if start_dt.date() == end_dt.date():
        title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')}"
    else:
        title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')} bis {end_dt.strftime('%Y-%m-%d')}"
    ax.set_title(title)

    span_hours = (end_dt - start_dt).total_seconds() / 3600.0
    if span_hours <= 36:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    else:
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M"))

    fig.autofmt_xdate()
    ax.grid(True, which="both", linestyle="--", alpha=0.4)

    if draw_now:
        try:
            now = datetime.now(times[0].tzinfo) if times[0].tzinfo else datetime.now()
            ax.axvline(now, linestyle=":", linewidth=1.2)
        except Exception:
            pass

    plt.tight_layout()
    plt.show()   # <<< nur Anzeige, kein Speichern


def main():
    csv_path = "esit_prices.csv"
    if not os.path.exists(csv_path):
        print(f"CSV nicht gefunden: {csv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        times, values = read_csv(csv_path)
    except Exception as e:
        print(f"Fehler beim Lesen der CSV: {e}", file=sys.stderr)
        sys.exit(2)

    try:
        make_plot(times, values, draw_now=True)
    except Exception as e:
        print(f"Fehler beim Erstellen/Anzeigen des Charts: {e}", file=sys.stderr)
        sys.exit(3)


if __name__ == "__main__":
    main()

