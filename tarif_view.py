#!/usr/bin/env python3
import os, csv, sys
from datetime import datetime, timedelta

# --- Matplotlib Setup (ohne GUI, mit fester Zeitzone) ---
import matplotlib
matplotlib.use("Agg")  # kein GUI / für cron geeignet
# WICHTIG: Standard-Zeitzone für Datumsformatierung auf Europe/Zurich setzen
matplotlib.rcParams["timezone"] = "Europe/Zurich"

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---- Konfiguration ----
CSV_PATH = "/home/pi/Scripts/esit_prices.csv"
PNG_PATH = "/home/pi/Scripts/esit_prices.png"

# Bildgröße (in Inch) und DPI
FIG_SIZE = (16, 14)   # (Breite, Höhe) in Inch
DPI = 200

# Referenzlinie (Rp/kWh)
REFERENCE_VALUE = 27.129

# Schriftgrößen
FONT_SIZE_LABELS = 18       # Achsenbeschriftungen
FONT_SIZE_TICKS  = 16       # Tick-Labels
FONT_SIZE_INFO   = 22       # Text oben rechts (aktueller Preis/Zeit)
# -----------------------

# Zeitzone: Europe/Zurich
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Zurich")
except Exception:
    LOCAL_TZ = None  # Fallback

def read_csv(csv_path):
    """
    CSV -> (times[datetime], values_rp[list[float]]) sortiert.
    Alle Zeitstempel werden konsequent in Europe/Zurich konvertiert.
    """
    times, values = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "start_local" not in r.fieldnames or "price_chf_per_kwh" not in r.fieldnames:
            raise ValueError(f"CSV-Header erwartet: start_local, price_chf_per_kwh (gefunden: {r.fieldnames})")
        for row in r:
            t = datetime.fromisoformat(row["start_local"])

            # Einheitliche TZ-Behandlung:
            # - Wenn kein tzinfo: als lokale (Europe/Zurich) Zeit interpretieren
            # - Wenn tzinfo vorhanden (z.B. UTC): in Europe/Zurich umrechnen
            if LOCAL_TZ:
                if t.tzinfo is None:
                    t = t.replace(tzinfo=LOCAL_TZ)
                else:
                    t = t.astimezone(LOCAL_TZ)

            values.append(float(row["price_chf_per_kwh"]) * 100.0)  # Rp/kWh
            times.append(t)

    pairs = sorted(zip(times, values), key=lambda z: z[0])
    if not pairs:
        return [], []
    times_sorted = [p[0] for p in pairs]
    values_sorted = [p[1] for p in pairs]
    return times_sorted, values_sorted

def round_to_even_2h(dt, direction):
    """Rundet auf gerade 2h-Grenze (00,02,04,...) runter/hoch."""
    if dt is None:
        return None
    base = dt.replace(minute=0, second=0, microsecond=0)
    if base.hour % 2 == 1:
        if direction == "down":
            base -= timedelta(hours=1)
        else:
            base += timedelta(hours=1)
    if direction == "up" and dt > base:
        base += timedelta(hours=2)
    return base

def find_current_slot(times, values):
    """liefert (t_cur, v_cur) des aktuell gültigen Slots"""
    if not times:
        return None, None
    now = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now(times[0].tzinfo)
    for t, v in zip(reversed(times), reversed(values)):
        if t <= now:
            return t, v
    return times[0], values[0]

def render_png(times, values, path):
    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)

    # Hauptlinie (immer schwarz)
    if times:
        ax.plot(times, values, color="black", linewidth=2.0, label="Tarif")

    # Referenzlinie (schwarz gestrichelt)
    if times:
        ax.plot(times, [REFERENCE_VALUE]*len(times),
                color="black", linestyle="--", linewidth=1.2, label="Referenz")

    # Achsen
    ax.set_xlabel("Zeit", fontsize=FONT_SIZE_LABELS)
    ax.set_ylabel("Stromtarif [Rp/kWh]", fontsize=FONT_SIZE_LABELS)
    ax.set_ylim(20, 35)

    # Locator/Formatter: TZ kommt aus rcParams["timezone"] = "Europe/Zurich"
    hour_locator = mdates.HourLocator(byhour=range(0, 24, 2))
    hour_fmt = mdates.DateFormatter("%H:%M")
    ax.xaxis.set_major_locator(hour_locator)
    ax.xaxis.set_major_formatter(hour_fmt)
    ax.tick_params(axis="x", labelsize=FONT_SIZE_TICKS)
    ax.tick_params(axis="y", labelsize=FONT_SIZE_TICKS)

    if times:
        x_min = round_to_even_2h(times[0], "down")
        x_max = round_to_even_2h(times[-1], "up")
        if x_min and x_max and x_min < x_max:
            ax.set_xlim(x_min, x_max)

    ax.grid(True, linestyle="--", alpha=0.25)

    # aktueller Slot + Punkt (Farbe abhängig von Referenz)
    t_cur, v_cur = find_current_slot(times, values)
    if t_cur is not None and v_cur is not None:
        if v_cur > REFERENCE_VALUE:
            point_color = "red"
        elif v_cur < REFERENCE_VALUE:
            point_color = "green"
        else:
            point_color = "black"

        ax.scatter([t_cur], [v_cur], color=point_color, s=100, zorder=3)

        now_disp = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now()
        ax.text(
            0.995, 0.995,
            f"Aktuell: {v_cur:.2f} Rp/kWh\n{now_disp.strftime('%Y-%m-%d %H:%M %Z')}",
            transform=ax.transAxes,
            ha="right", va="top",
            fontsize=FONT_SIZE_INFO,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.7)
        )

    fig.autofmt_xdate()
    plt.tight_layout()

    # atomar speichern
    tmp = path + ".tmp.png"
    fig.savefig(tmp)
    plt.close(fig)
    os.replace(tmp, path)
    print(f"PNG aktualisiert: {path}")

def main():
    # absolute Pfade sind für cron wichtig
    csv_path = os.path.abspath(CSV_PATH)
    png_path = os.path.abspath(PNG_PATH)

    if not os.path.exists(csv_path):
        print(f"[FEHLER] CSV nicht gefunden: {csv_path}", file=sys.stderr)
        sys.exit(1)

    try:
        times, values = read_csv(csv_path)
        if not times:
            print("[HINWEIS] CSV enthält keine Daten – PNG wird nicht erzeugt.", file=sys.stderr)
            sys.exit(2)
        render_png(times, values, png_path)
    except Exception as e:
        print(f"[FEHLER] {e}", file=sys.stderr)
        sys.exit(3)

if __name__ == "__main__":
    main()

