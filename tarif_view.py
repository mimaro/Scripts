#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tarif.view – Live-Update aus 'esit_prices.csv' als Linienchart (Rp/kWh).
- Liest start_local, end_local, price_chf_per_kwh
- Rechnet Preis * 100 -> Rp/kWh
- X-Achse: lokale Zeit Europe/Zurich (Sommer-/Winterzeit korrekt)
- Y-Achse: fix 0..40
- Keine Datei speichern, nur anzeigen
- Aktualisiert die Daten im gleichen Fenster in festem Intervall

Startbeispiel (auf HDMI-Desktop):
  DISPLAY=:0 XAUTHORITY=/home/pi/.Xauthority /usr/bin/python3 /home/pi/Scripts/tarif_view.py --interval 60
"""

import matplotlib
matplotlib.use("TkAgg")  # GUI-Backend

import os
import sys
import csv
import time
import argparse
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

import matplotlib.pyplot as plt
import matplotlib.dates as mdates


CSV_PATH_DEFAULT = "esit_prices.csv"


def read_csv(csv_path):
    """Liest CSV und liefert (times, rp_per_kwh). Zeiten tz-aware in Europe/Zurich, sortiert."""
    times, values = [], []
    local_tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None

    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = datetime.fromisoformat(row["start_local"])
            # Falls keine TZ im CSV: Europe/Zurich annehmen
            if t.tzinfo is None and local_tz:
                t = t.replace(tzinfo=local_tz)
            rp = float(row["price_chf_per_kwh"]) * 100.0  # CHF/kWh -> Rp/kWh
            times.append(t)
            values.append(rp)

    pairs = sorted(zip(times, values), key=lambda x: x[0])
    times, values = [p[0] for p in pairs], [p[1] for p in pairs]
    return times, values


def build_axes(ax, times, values):
    """Initiale Achsen-/Format-Setups (ohne Farben)."""
    tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None

    # Achsentitel
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Energiepreis [Rp/kWh]")

    # Y-Achse fix
    ax.set_ylim(0, 40)

    # Titel
    if not times:
        ax.set_title("ESIT-Preise – keine Daten")
    else:
        start_dt, end_dt = times[0], times[-1]
        if start_dt.date() == end_dt.date():
            title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')}"
        else:
            title = f"ESIT-Preise – {start_dt.strftime('%Y-%m-%d')} bis {end_dt.strftime('%Y-%m-%d')}"
        ax.set_title(title)

    # X-Achsen-Formatter mit TZ
    if times:
        span_hours = (times[-1] - times[0]).total_seconds() / 3600.0
        if span_hours <= 36:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M", tz=tz))
        else:
            ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d\n%H:%M", tz=tz))

    ax.grid(True, which="both", linestyle="--", alpha=0.4)


def update_title_with_stamp(ax, times):
    """Ergänzt den Titel um 'Stand: HH:MM TZ'."""
    tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None
    now = datetime.now(tz) if tz else datetime.now()
    base = ax.get_title()
    ax.set_title(f"{base}  –  Stand: {now.strftime('%Y-%m-%d %H:%M %Z')}")


def main():
    ap = argparse.ArgumentParser(description="Live-Plot ESIT CSV (Rp/kWh) mit Aktualisierung")
    ap.add_argument("--csv", default=CSV_PATH_DEFAULT, help="Pfad zur CSV-Datei")
    ap.add_argument("--interval", type=int, default=60, help="Aktualisierungsintervall in Sekunden (Default: 60)")
    ap.add_argument("--no-now-line", action="store_true", help="Keine vertikale Linie für 'Jetzt' zeichnen")
    args = ap.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"CSV nicht gefunden: {csv_path}", file=sys.stderr)
        sys.exit(1)

    # Erstes Einlesen
    try:
        times, values = read_csv(csv_path)
    except Exception as e:
        print(f"Fehler beim Lesen der CSV: {e}", file=sys.stderr)
        sys.exit(2)

    # Plot vorbereiten
    fig, ax = plt.subplots(figsize=(10, 5))
    line, = ax.plot(times, values, linewidth=1.8)  # Linie-Handle merken
    build_axes(ax, times, values)

    # optionale 'Jetzt'-Linie
    now_line = None
    if not args.no-now-line:
        try:
            tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None
            now = datetime.now(tz) if tz else datetime.now()
            now_line = ax.axvline(now, linestyle=":", linewidth=1.2)
        except Exception:
            pass

    update_title_with_stamp(ax, times)
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show(block=False)  # Fenster anzeigen, aber nicht blockieren

    last_mtime = os.path.getmtime(csv_path)

    try:
        while True:
            time.sleep(args.interval)

            try:
                mtime = os.path.getmtime(csv_path)
            except FileNotFoundError:
                # CSV fehlt temporär -> überspringen
                continue

            if mtime == last_mtime:
                # keine Änderung -> nur Now-Linie aktualisieren
                if now_line is not None:
                    tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None
                    now = datetime.now(tz) if tz else datetime.now()
                    now_line.set_xdata([now, now])
                fig.canvas.draw_idle()
                plt.pause(0.01)
                continue

            # CSV hat sich geändert -> neu laden
            try:
                new_times, new_values = read_csv(csv_path)
            except Exception as e:
                # Beim Lesen schiefgegangen -> nächster Versuch später
                continue

            last_mtime = mtime

            # Daten in vorhandener Linie aktualisieren
            line.set_xdata(new_times)
            line.set_ydata(new_values)

            # X-Achse neu formatieren und Limits anpassen (Y bleibt 0..40 fix)
            ax.relim()
            ax.autoscale_view(scalex=True, scaley=False)
            build_axes(ax, new_times, new_values)
            update_title_with_stamp(ax, new_times)

            # Now-Linie nachführen
            if now_line is not None:
                tz = ZoneInfo("Europe/Zurich") if ZoneInfo else None
                now = datetime.now(tz) if tz else datetime.now()
                now_line.set_xdata([now, now])

            fig.canvas.draw_idle()
            plt.pause(0.01)

    except KeyboardInterrupt:
        # sauberes Beenden mit Ctrl+C
        pass


if __name__ == "__main__":
    main()
