#!/usr/bin/env python3
import os, csv, time
from datetime import datetime
import matplotlib
matplotlib.use("Agg")  # kein GUI
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

CSV_PATH = "/home/pi/Scripts/esit_prices.csv"
PNG_PATH = "/home/pi/Scripts/esit_prices.png"
INTERVAL_SECONDS = 60

def read_csv(csv_path):
    xs, ys = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            xs.append(datetime.fromisoformat(row["start_local"]))
            ys.append(float(row["price_chf_per_kwh"]) * 100.0)  # Rp/kWh
    return xs, ys

def render_png(xs, ys, path):
    fig, ax = plt.subplots(figsize=(12, 6), dpi=100)
    ax.plot(xs, ys, linewidth=1.0)
    ax.set_xlabel("Zeit")
    ax.set_ylabel("Preis [Rp/kWh]")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=2))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    fig.autofmt_xdate()
    tmp = path + ".tmp"
    plt.tight_layout()
    fig.savefig(tmp)
    plt.close(fig)
    os.replace(tmp, path)  # atomar
    print(f"PNG aktualisiert: {path}")

def main():
    last_mtime = 0
    while True:
        try:
            mtime = os.path.getmtime(CSV_PATH)
            if mtime != last_mtime:
                xs, ys = read_csv(CSV_PATH)
                if xs:
                    render_png(xs, ys, PNG_PATH)
                last_mtime = mtime
        except Exception as e:
            print("Fehler:", e)
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()




