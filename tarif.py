#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Swisspower ESIT – dynamische Preise:
- Vergangene 2h + nächste 24h (15-Minuten-Raster)
- Aktueller Slot + CSV-Ausgabe
- Post des (aktuellen Slot-)Werts in Rp/kWh an Volkszähler (write_vals)

Voraussetzungen:
  pip3 install requests python-dateutil
"""

import os
import sys
import csv
import logging
from datetime import datetime, timedelta
from dateutil import tz
import requests

# ===== Konfiguration =====
BASE_URL = os.environ.get("ESIT_BASE_URL", "https://esit.code-fabrik.ch")
API_PATH = "/api/v1/metering_code"

METERING_CODE = os.environ.get(
    "ESIT_METERING_CODE",
    "CH1011701234500000000000002093987"
)
AUTH_TOKEN = os.environ.get(
    "ESIT_API_TOKEN",
    "459cceb84e827d308cb61a14da203506"
)

# Tariftyp: "integrated" = Gesamtpreis; Alternativen: "electricity", "dso"
TARIFF_TYPE = os.environ.get("ESIT_TARIFF_TYPE", "integrated")

# Zeitraumsteuerung
PAST_HOURS = 2
FUTURE_HOURS = 24

# Volkszähler (optional)
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
UUID = {"Energiepreis": "f828d020-88c1-11f0-87f7-958162b459c7"}

# Absoluter Pfad zur CSV
CSV_PATH = "/home/pi/Scripts/esit_prices.csv"
HTTP_TIMEOUT = 20
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

def write_vals(uuid, val):
    """Wert an Volkszähler posten; robust gegen Netzwerkfehler."""
    try:
        url = VZ_POST_URL.format(uuid, val)
        resp = requests.post(url, timeout=10)
        logging.info("VZ post -> %s (%s)", resp.status_code, "OK" if resp.ok else "FAIL")
    except Exception as e:
        logging.warning("VZ post fehlgeschlagen: %s", e)

def floor_to_quarter(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)

def rfc3339(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")  # lokale TZ; API spiegelt TZ zurück

def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")

def fetch_tariffs(start_ts: str, end_ts: str, metering_code: str, tariff_type: str):
    url = build_url(BASE_URL, API_PATH)
    params = {
        "start_timestamp": start_ts,
        "end_timestamp": end_ts,
        "metering_code": metering_code,
        "tariff_type": tariff_type,
    }
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    resp = requests.get(url, params=params, headers=headers, timeout=HTTP_TIMEOUT)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
    return resp.json()

def sum_chf_per_kwh(components):
    """Summiert nur Arbeitskomponenten in CHF/kWh."""
    if not isinstance(components, list):
        return 0.0
    total = 0.0
    for c in components:
        if c.get("unit") == "CHF/kWh" and c.get("component") == "work":
            try:
                total += float(c.get("value", 0.0))
            except Exception:
                pass
    return total

def extract_slot_price(slot, prefer="integrated"):
    """
    Liefert (price_chf_per_kwh, start_dt, end_dt).
    Fallback: electricity + dso, falls integrated fehlt.
    Zeitstempel sind in der abgefragten lokalen TZ.
    """
    start_dt = datetime.fromisoformat(slot["start_timestamp"])
    end_dt   = datetime.fromisoformat(slot["end_timestamp"])

    # Bevorzugt 'integrated'
    if prefer and prefer in slot:
        p_int = sum_chf_per_kwh(slot[prefer])
        if p_int > 0 or isinstance(slot.get(prefer), list):
            return p_int, start_dt, end_dt

    # Fallback: electricity + dso (+ grid falls vorhanden)
    p = 0.0
    if "electricity" in slot:
        p += sum_chf_per_kwh(slot["electricity"])
    if "dso" in slot:
        p += sum_chf_per_kwh(slot["dso"])
    if p == 0.0 and "grid" in slot:
        p += sum_chf_per_kwh(slot["grid"])
    return p, start_dt, end_dt

# === CSV atomar schreiben ===
def write_csv_atomic(path, rows):
    """
    Schreibt die CSV atomar.
    Erwartet rows als Iterable von (price, start_dt, end_dt).
    Header: start_local, end_local, price_chf_per_kwh
    """
    tmp = f"{path}.tmp"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    with open(tmp, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start_local", "end_local", "price_chf_per_kwh"])
        for price, st, en in rows:
            w.writerow([
                st.isoformat(timespec="seconds"),
                en.isoformat(timespec="seconds"),
                f"{price:.8f}",
            ])
        f.flush()
        os.fsync(f.fileno())

    os.replace(tmp, path)
    try:
        os.chmod(path, 0o644)
    except Exception:
        pass
# ================================

def main():
    if not AUTH_TOKEN:
        print("⚠️  Bitte ESIT_API_TOKEN setzen!", file=sys.stderr)
        sys.exit(1)

    local_tz = tz.tzlocal()
    now_local = datetime.now(local_tz)

    # letzten 2h + nächsten 24h
    start_local = floor_to_quarter(now_local - timedelta(hours=PAST_HOURS))
    end_local   = floor_to_quarter(now_local) + timedelta(hours=FUTURE_HOURS) - timedelta(seconds=1)

    start_ts = rfc3339(start_local)
    end_ts   = rfc3339(end_local)

    logging.info("Hole Preise von %s bis %s", start_ts, end_ts)

    try:
        data = fetch_tariffs(start_ts, end_ts, METERING_CODE, TARIFF_TYPE)
    except Exception as e:
        print(f"❌ Abruf fehlgeschlagen: {e}", file=sys.stderr)
        sys.exit(2)

    prices = data.get("prices", [])
    if not prices:
        print("Keine Preise erhalten.")
        sys.exit(3)

    # Slots extrahieren und sortieren
    rows = [extract_slot_price(s, prefer="integrated") for s in prices]
    rows.sort(key=lambda x: x[1])  # sortiere nach start_dt

    # Aktuellen Slot finden
    current = None
    for price, st, en in rows:
        if st <= now_local <= en:
            current = (st, en, price)
            break
    if current is None:
        for price, st, en in rows:
            if st > now_local:
                current = (st, en, price)
                break
        if current is None:
            price, st, en = rows[-1]
            current = (st, en, price)

    st, en, pr = current
    print("\n=== Swisspower ESIT – Dynamischer Tarif (CHF/kWh) ===")
    print(f"Messpunkt : {METERING_CODE}")
    print(f"Tariftyp  : {TARIFF_TYPE} (Gesamtpreis)")
    print(f"Zeitraum  : {rows[0][1].strftime('%Y-%m-%d %H:%M')} – {rows[-1][2].strftime('%Y-%m-%d %H:%M')} (lokal)\n")
    print(">> Aktueller Preis:")
    print(f"  {st.strftime('%Y-%m-%d %H:%M')} – {en.strftime('%H:%M')}  ->  {pr:.5f} CHF/kWh\n")

    # CSV schreiben (ATOMAR)
    try:
        write_csv_atomic(CSV_PATH, rows)
        print(f"CSV gespeichert: {os.path.abspath(CSV_PATH)}")
    except Exception as e:
        print(f"⚠️ CSV konnte nicht gespeichert werden: {e}", file=sys.stderr)

    # >>> NEU: aktuellen Slot an VZ posten (Rp/kWh)
    try:
        current_price_rp = pr * 100.0  # CHF/kWh -> Rp/kWh
        logging.info("Poste aktuellen Preis an VZ: %.2f Rp/kWh (Slot %s–%s)", current_price_rp, st, en)
        write_vals(UUID["Energiepreis"], current_price_rp)
    except Exception as e:
        logging.warning("Post des aktuellen Slot-Werts fehlgeschlagen: %s", e)

if __name__ == "__main__":
    main()

