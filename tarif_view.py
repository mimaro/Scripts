#!/usr/bin/env python3
import os, csv, time
from datetime import datetime, timedelta
import matplotlib
matplotlib.use("Agg")  # kein GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# ---- Konfiguration ----
CSV_PATH = "/home/pi/Scripts/esit_prices.csv"
PNG_PATH = "/home/pi/Scripts/esit_prices.png"
INTERVAL_SECONDS = 60

# Bildgröße (in Inch) und DPI anpassbar
FIG_SIZE = (12, 6)   # (Breite, Höhe) in Inch
DPI = 100
# -----------------------

# Zeitzone: Europe/Zurich für Achsen & "aktueller" Slot
try:
    from zoneinfo import ZoneInfo
    LOCAL_TZ = ZoneInfo("Europe/Zurich")
except Exception:
    LOCAL_TZ = None  # Fallback, wenn ZoneInfo fehlt

def read_csv(csv_path):
    """CSV -> (times[datetime], values_rp[list[float]]), sortiert nach Zeit"""
    times, values = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            t = datetime.fromisoformat(row["start_local"])
            # falls CSV naive Zeiten hat, auf LOCAL_TZ setzen (besser: CSV bereits mit Offset schreiben)
            if t.tzinfo is None and LOCAL_TZ:
                t = t.replace(tzinfo=LOCAL_TZ)
            values.append(float(row["price_chf_per_kwh"]) * 100.0)  # Rp/kWh
            times.append(t)
    # sortieren
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
    # zu nächster gerader Stunde
    if base.hour % 2 == 1:
        if direction == "down":
            base -= timedelta(hours=1)
        else:  # up
            base += timedelta(hours=1)
    if direction == "up" and dt > base:
        base += timedelta(hours=2)
    return base

def find_current_tariff(times, values):
    """Wählt den aktuell gültigen Slot-Wert (letzter Start <= now)."""
    if not times:
        return None
    now = datetime.now(LOCAL_TZ) if LOCAL_TZ else datetime.now(times[0].tzinfo)
    # lineare Suche von hinten (Listen sind kurz), sonst bisect
    for t, v in zip(reversed(times), reversed(values)):
        if t <= now:
            return v
    # falls alle in der Zukunft liegen: nimm den frühesten
    return values[0]

def render_png(times, values, path):
    # Matplotlib-Objekte
    fig, ax = plt.subplots(figsize=FIG_SIZE, dpi=DPI)

    # Plot
    ax.plot(times, values, linewidth=1.0)

    # Achsenlabels
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Preis [Rp/kWh]")

    # Y-Achse fest 20..35
    ax.set_ylim(20, 35)

    # X-Achse: 2h-Ticks auf geraden Stunden, Labels HH:MM in Europe/Zurich
    hour_locator = mdates.HourLocator(byhour=range(0, 24, 2), tz=LOCAL_TZ)
    hour_fmt = mdates.DateFormatter("%H:%M", tz=LOCAL_TZ)
    ax.xaxis.set_major_locator(hour_locator)
    ax.xaxis.set_major_formatter(hour_fmt)

    # X-Limits auf 2h-Raster runden (min..max der Daten)
    x_min = round_to_even_2h(times[0], "down")
    x_max = round_to_even_2h(times[-1], "up")
    if x_min and x_max and x_min < x_max:
        ax.set_xlim(x_min, x_max)

    # Grid
    ax.grid(True, linestyle="--", alpha=0.25)

    # Aktuellen Energietarif (Rp/kWh) ermitteln und oben rechts einblenden
    current_tariff = find_current_tariff(times, values)
    if current_tariff is not None:
        ax.text(
            0.995, 0.995,
            f"Aktuell: {current_tariff:.2f} Rp/kWh",
            transform=ax.transAxes,
            ha="right", va="top",
            fontsize=12,
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec="black", alpha=0.7)
        )

    # Layout + Speichern (atomar)
    fig.autofmt_xdate()
    plt.tight_layout()
    tmp = path + ".tmp.png"     # .png-Endung beibehalten
    fig.savefig(tmp)
    plt.close(fig)
    os.replace(tmp, path)
    print(f"PNG aktualisiert: {path}")

def main():
    last_mtime = 0
    while True:
        try:
            mtime = os.path.getmtime(CSV_PATH)
            if mtime != last_mtime:
                times, values = read_csv(CSV_PATH)
                if times:
                    render_png(times, values, PNG_PATH)
                last_mtime = mtime
        except Exception as e:
            print("Fehler:", e)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()




