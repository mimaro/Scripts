#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
tarif_view.py – zeigt /home/pi/Scripts/esit_prices.csv als Live-Linienchart (Rp/kWh)
Start: python3 tarif_view.py
Aktualisierung: alle 60s
"""

import os, sys, csv, time
from datetime import datetime
import matplotlib
matplotlib.use("TkAgg")  # GUI-Backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV_PATH = "/home/pi/Scripts/esit_prices.csv"
INTERVAL_SECONDS = 60
FULLSCREEN = False  # bei Bedarf True

# Zeitzone/Formatter
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Zurich")
except Exception:
    LOCAL_TZ = None
FMT_SHORT = mdates.DateFormatter("%H:%M", tz=LOCAL_TZ)
FMT_LONG  = mdates.DateFormatter("%Y-%m-%d\n%H:%M", tz=LOCAL_TZ)

def info(msg): print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def read_csv(csv_path):
    """liest CSV -> (x_num, y_rp, first_dt, last_dt); überspringt fehlerhafte Zeilen"""
    times, values, bad = [], [], 0
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "start_local" not in r.fieldnames or "price_chf_per_kwh" not in r.fieldnames:
            raise KeyError(f"CSV-Header erwartet: start_local, price_chf_per_kwh (gefunden: {r.fieldnames})")
        for row in r:
            try:
                t = datetime.fromisoformat(row["start_local"])
                if t.tzinfo is None and LOCAL_TZ: t = t.replace(tzinfo=LOCAL_TZ)
                rp = float(row["price_chf_per_kwh"]) * 100.0
                times.append(t); values.append(rp)
            except Exception:
                bad += 1
    if bad: info(f"{bad} CSV-Zeile(n) übersprungen (Parsefehler).")
    if not times: return [], [], None, None
    pairs = sorted(zip(times, values), key=lambda z: z[0])
    times_sorted = [p[0] for p in pairs]; values_sorted = [p[1] for p in pairs]
    x_num = list(mdates.date2num(times_sorted))
    return x_num, values_sorted, times_sorted[0], times_sorted[-1]


def setup_axes(ax, x_first, x_last):
    ax.set_xlabel("Zeit"); ax.set_ylabel("Energiepreis [Rp/kWh]"); ax.set_ylim(0, 40)
    span_hours = (x_last - x_first) * 24 if x_first is not None and x_last is not None else 0
    ax.xaxis.set_major_formatter(FMT_SHORT if span_hours <= 36 else FMT_LONG)
    ax.grid(True, which="both", linestyle="--", alpha=0.4)

def update_title(ax, first_dt, last_dt, extra=""):
    if first_dt is None or last_dt is None:
        base = "ESIT-Preise – keine Daten"
    elif first_dt.date() == last_dt.date():
        base = f"ESIT-Preise – {first_dt.strftime('%Y-%m-%d')}"
    else:
        base = f"ESIT-Preise – {first_dt.strftime('%Y-%m-%d')} bis {last_dt.strftime('%Y-%m-%d')}"
    now = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now()
    ax.set_title(f"{base} – Stand: {now.strftime('%Y-%m-%d %H:%M %Z')}{extra}")

def overlay_text(ax, text):
    return ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center",
                   bbox=dict(boxstyle="round", fc="w", ec="r"), fontsize=10, zorder=10)

def main():
    if not os.environ.get("DISPLAY"):
        info("WARNUNG: DISPLAY ist leer. Falls per SSH gestartet, setze DISPLAY=:0 und XAUTHORITY.")
    if not os.path.exists(CSV_PATH):
        print(f"[FEHLER] CSV nicht gefunden: {CSV_PATH}", file=sys.stderr); sys.exit(1)

    try:
        x_num, y_rp, first_dt, last_dt = read_csv(CSV_PATH)
    except Exception as e:
        print(f"[FEHLER] CSV-Problem: {e}", file=sys.stderr); sys.exit(2)

    fig, ax = plt.subplots(figsize=(10, 5))
    warn = None

    if x_num:
        (line,) = ax.plot(x_num, y_rp, linewidth=1.8)
        setup_axes(ax, x_num[0], x_num[-1])
        ax.set_xlim(x_num[0], x_num[-1])
    else:
        (line,) = ax.plot([], [], linewidth=1.8)
        warn = overlay_text(ax, "Keine Daten in CSV")

    now_line = ax.axvline(mdates.date2num(datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now()),
                          linestyle=":", linewidth=1.2)

    update_title(ax, first_dt, last_dt)
    fig.autofmt_xdate(); plt.tight_layout(); plt.show(block=False)

    if FULLSCREEN:
        try: plt.get_current_fig_manager().full_screen_toggle()
        except Exception: pass

    try: last_mtime = os.path.getmtime(CSV_PATH)
    except FileNotFoundError: last_mtime = 0

    info(f"Starte Live-Update: Datei={CSV_PATH}, Intervall={INTERVAL_SECONDS}s")
    try:
        while True:
            time.sleep(INTERVAL_SECONDS)

            try: mtime = os.path.getmtime(CSV_PATH)
            except FileNotFoundError: mtime = last_mtime

            if mtime != last_mtime:
                try:
                    x_new, y_new, fdt, ldt = read_csv(CSV_PATH)
                except Exception as e:
                    info(f"CSV noch im Schreibvorgang? {e}"); continue
                last_mtime = mtime
                if x_new:
                    line.set_data(x_new, y_new)
                    ax.set_xlim(x_new[0], x_new[-1])
                    setup_axes(ax, x_new[0], x_new[-1])
                    update_title(ax, fdt, ldt)
                    if warn: warn.remove(); warn = None
                else:
                    if warn: warn.set_text("Keine Daten in CSV")
                    else: warn = overlay_text(ax, "Keine Daten in CSV")

            # Now-Linie + Titelzeit aktualisieren
            now = mdates.date2num(datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now())
            now_line.set_xdata([now, now])
            if not x_num: update_title(ax, first_dt, last_dt)  # bei leerem Datensatz Zeit nachführen

            fig.canvas.draw_idle(); plt.pause(0.01)

    except KeyboardInterrupt:
        info("Beendet (Strg+C)")

if __name__ == "__main__":
    main()


