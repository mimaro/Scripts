
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#lokal starte mit
#python3 /home/pi/Scripts/tarif_view.py --csv /home/pi/Scripts/esit_prices.csv --interval 60

"""
tarif.view – Live-Update aus 'esit_prices.csv' als Linienchart (Rp/kWh).
- Liest start_local, end_local, price_chf_per_kwh
- Rechnet Preis * 100 -> Rp/kWh
- X-Achse: Europe/Zurich (DST korrekt), Y: 0..40
- Kein Speichern, nur Anzeige
- Aktualisiert sich periodisch; bei unveränderter CSV nur 'Jetzt'-Linie bewegen
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

# === Globale, wiederverwendete Objekte ===
LOCAL_TZ = ZoneInfo("Europe/Zurich") if ZoneInfo else None
FMT_SHORT = mdates.DateFormatter("%H:%M", tz=LOCAL_TZ)                # ≤ 36h
FMT_LONG  = mdates.DateFormatter("%Y-%m-%d\n%H:%M", tz=LOCAL_TZ)      # > 36h


def read_csv(csv_path):
    """
    Liest CSV -> (x_num, y_rp, start_dt, end_dt)
    - x_num: Matplotlib-Zeitachsenwerte (mdates.date2num)
    - y_rp : Preise in Rp/kWh (float)
    - start_dt, end_dt: erste/letzte Zeit (datetime, tz-aware/naiv wie CSV; ggf. LOCAL_TZ angenommen)
    """
    times, values = [], []

    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            t = datetime.fromisoformat(row["start_local"])
            if t.tzinfo is None and LOCAL_TZ:
                t = t.replace(tzinfo=LOCAL_TZ)
            rp = float(row["price_chf_per_kwh"]) * 100.0
            times.append(t)
            values.append(rp)

    if not times:
        return [], [], None, None

    # Sortierung (falls nötig) und Umwandlung für schnellere set_data
    pairs = sorted(zip(times, values), key=lambda z: z[0])
    times_sorted = [p[0] for p in pairs]
    values_sorted = [p[1] for p in pairs]
    x_num = mdates.date2num(times_sorted)
    return x_num, values_sorted, times_sorted[0], times_sorted[-1]


def setup_axes(ax, x_first, x_last):
    """Einmaliges Achsen-Setup (Labels, Limits, Formatter, Grid)."""
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Energiepreis [Rp/kWh]")
    ax.set_ylim(0, 40)

    # Formatter je nach Spannweite
    span_hours = (x_last - x_first) * 24  # numdays -> hours
    ax.xaxis.set_major_formatter(FMT_SHORT if span_hours <= 36 else FMT_LONG)

    ax.grid(True, which="both", linestyle="--", alpha=0.4)


def update_title(ax, first_dt, last_dt):
    """Titel inkl. 'Stand: ... TZ' setzen – ohne teure String-Neuberechnung jedes Mal."""
    if first_dt is None or last_dt is None:
        base = "ESIT-Preise – keine Daten"
    else:
        if first_dt.date() == last_dt.date():
            base = f"ESIT-Preise – {first_dt.strftime('%Y-%m-%d')}"
        else:
            base = f"ESIT-Preise – {first_dt.strftime('%Y-%m-%d')} bis {last_dt.strftime('%Y-%m-%d')}"
    now = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now()
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
        x_num, y_rp, first_dt, last_dt = read_csv(csv_path)
    except Exception as e:
        print(f"Fehler beim Lesen der CSV: {e}", file=sys.stderr)
        sys.exit(2)

    fig, ax = plt.subplots(figsize=(10, 5))

    # Initiale Linie(n)
    if len(x_num) > 0:
        line, = ax.plot(x_num, y_rp, linewidth=1.8)
        setup_axes(ax, x_num[0], x_num[-1])
        ax.set_xlim(x_num[0], x_num[-1])
    else:
        line, = ax.plot([], [], linewidth=1.8)

    # Now-Linie optional
    now_line = None
    if not args.no_now_line:
        now = mdates.date2num(datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now())
        now_line = ax.axvline(now, linestyle=":", linewidth=1.2)

    update_title(ax, first_dt, last_dt)
    fig.autofmt_xdate()
    plt.tight_layout()
    plt.show(block=False)

    try:
        last_mtime = os.path.getmtime(csv_path)
    except FileNotFoundError:
        last_mtime = 0

    try:
        while True:
            time.sleep(args.interval)

            # 1) CSV geändert?
            try:
                mtime = os.path.getmtime(csv_path)
            except FileNotFoundError:
                mtime = last_mtime  # keine Änderung melden

            if mtime != last_mtime:
                # Neu einlesen und Linie aktualisieren
                try:
                    x_new, y_new, fdt, ldt = read_csv(csv_path)
                except Exception:
                    # CSV gerade im Schreibvorgang? nächster Tick…
                    continue

                last_mtime = mtime

                if x_new:
                    line.set_data(x_new, y_new)
                    # Achsen-Aktualisierung minimal halten: nur X neu skalieren, Y bleibt 0..40
                    ax.set_xlim(x_new[0], x_new[-1])
                    setup_axes(ax, x_new[0], x_new[-1])  # Formatter ggf. umschalten
                    update_title(ax, fdt, ldt)

                # Now-Linie mitziehen
                if now_line is not None:
                    now = mdates.date2num(datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now())
                    now_line.set_xdata([now, now])

                fig.canvas.draw_idle()
                plt.pause(0.01)
                continue

            # 2) Keine CSV-Änderung → nur Now-Linie & Zeitstempel im Titel nachführen
            something_changed = False
            if now_line is not None:
                now = mdates.date2num(datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now())
                now_line.set_xdata([now, now])
                something_changed = True

            # Titel alle Intervalle aktualisieren (Stand: …)
            update_title(ax, first_dt, last_dt)
            if something_changed:
                fig.canvas.draw_idle()
                plt.pause(0.01)

    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
