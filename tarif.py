#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Swisspower ESIT – dynamische Preise: aktueller Slot + 24h Vorschau (15-Minuten-Raster)

Erfordert:
  pip3 install requests python-dateutil

Doku-Details:
- GET /api/v1/metering_code mit start_timestamp, end_timestamp, metering_code, optional tariff_type
- Authorization: Bearer <token>
Siehe API-Doku (staging): swisspower-esit-api-staging.json
"""

import os
import sys
import csv
from datetime import datetime, timedelta, timezone
from dateutil import tz
import requests
import urllib.parse
import csv
from datetime import datetime
import logging

# ===== Konfiguration =====
# Production ist Standard; für Staging: ESIT_BASE_URL=https://esit-test.code-fabrik.ch
BASE_URL = os.environ.get("ESIT_BASE_URL", "https://esit.code-fabrik.ch")
API_PATH = "/api/v1/metering_code"

# Messpunkt & Token
METERING_CODE = os.environ.get(
    "ESIT_METERING_CODE",
    "CH1011701234500000000000002093987"  # <- von dir
)
AUTH_TOKEN = os.environ.get(
    "ESIT_API_TOKEN",
    "459cceb84e827d308cb61a14da203506"
)

# Tariftyp: "integrated" liefert Gesamtpreis; alternativ "electricity"/"dso"
TARIFF_TYPE = os.environ.get("ESIT_TARIFF_TYPE", "integrated")

VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

UUID = {
    "Energiepreis": "f828d020-88c1-11f0-87f7-958162b459c7"
   }

# ==========================

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    logging.info("Ok? {}".format(postreq.ok))

def floor_to_quarter(dt: datetime) -> datetime:
    return dt.replace(minute=(dt.minute // 15) * 15, second=0, microsecond=0)

def rfc3339(dt: datetime) -> str:
    # inkl. lokaler TZ, denn die API antwortet in derselben TZ (RFC3339)
    return dt.isoformat(timespec="seconds")

def build_url(base, path):
    return base.rstrip("/") + "/" + path.lstrip("/")

def fetch_tariffs(start_ts: str, end_ts: str, metering_code: str, tariff_type: str):
    url = build_url(BASE_URL, API_PATH)
    # start/end müssen URL-encoded sein (RFC3986 §2.1) – requests erledigt das, aber wir sind explizit.
    params = {
        "start_timestamp": start_ts,
        "end_timestamp": end_ts,
        "metering_code": metering_code,
        "tariff_type": tariff_type,
    }
    headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
    resp = requests.get(url, params=params, headers=headers, timeout=20)
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
    return resp.json()

def sum_chf_per_kwh(components):
    """Summiert nur Arbeitskomponenten in CHF/kWh."""
    if not isinstance(components, list):
        return 0.0
    total = 0.0
    for c in components:
        try:
            if c.get("unit") == "CHF/kWh" and c.get("component") == "work":
                total += float(c.get("value", 0.0))
        except Exception:
            continue
    return total

def extract_slot_price(slot, prefer="integrated"):
    """
    Liefert (price_chf_per_kwh, start_dt, end_dt).
    Fallback: electricity + dso, falls integrated fehlt.
    """
    # Zeitsstempel kommen in der TZ zurück, die wir abgefragt haben (hier: lokal)
    start = slot.get("start_timestamp")
    end = slot.get("end_timestamp")
    # robust parsen
    start_dt = datetime.fromisoformat(start)
    end_dt = datetime.fromisoformat(end)

    # Erst "integrated" versuchen
    if prefer and prefer in slot:
        p = sum_chf_per_kwh(slot[prefer])
        if p > 0 or isinstance(slot[prefer], list):
            return p, start_dt, end_dt

    # Fallback: electricity + dso
    p = 0.0
    if "electricity" in slot:
        p += sum_chf_per_kwh(slot["electricity"])
    if "dso" in slot:
        p += sum_chf_per_kwh(slot["dso"])
    # Falls trotzdem 0, noch "grid" addieren (manche Dokus differenzieren)
    if p == 0.0 and "grid" in slot:
        p += sum_chf_per_kwh(slot["grid"])

    return p, start_dt, end_dt

def main():
    if not AUTH_TOKEN:
        print("⚠️  Bitte das API-Token setzen, z.B.: export ESIT_API_TOKEN='...'", file=sys.stderr)
        sys.exit(1)

    # Lokale Zeitzone verwenden (die API spiegelt die TZ in der Antwort)
    local_tz = tz.tzlocal()
    now_local = datetime.now(local_tz)
    start_local = floor_to_quarter(now_local)
    # Ende inklusiv wie im Doku-Beispiel: 23:59:59 (hier +24h - 1s)
    end_local = start_local + timedelta(hours=24) - timedelta(seconds=1)

    start_ts = rfc3339(start_local)
    end_ts = rfc3339(end_local)

    try:
        data = fetch_tariffs(start_ts, end_ts, METERING_CODE, TARIFF_TYPE)
    except Exception as e:
        print(f"❌ Abruf fehlgeschlagen: {e}", file=sys.stderr)
        print("Tipps:\n- BASE_URL korrekt? (Prod vs. Staging)\n- Token gültig & als Bearer?\n- Zeitformat RFC3339?\n- Messpunkt stimmt?", file=sys.stderr)
        sys.exit(2)

    prices = data.get("prices", [])
    if not prices:
        print("Keine Preise erhalten.")
        sys.exit(3)

    # Slots extrahieren
    rows = []
    for s in prices:
        price, start_dt, end_dt = extract_slot_price(s, prefer="integrated")
        rows.append((start_dt, end_dt, price))

    # aktuellen Slot finden
    current = None
    for st, en, pr in rows:
        if st <= now_local <= en:
            current = (st, en, pr)
            break
    if current is None:
        # nächster zukünftiger
        rows_sorted = sorted(rows, key=lambda x: x[0])
        for st, en, pr in rows_sorted:
            if st > now_local:
                current = (st, en, pr)
                break
        if current is None:
            current = rows_sorted[-1]

    st, en, pr = current
    print("\n=== Swisspower ESIT – Dynamischer Tarif (CHF/kWh) ===")
    print(f"Messpunkt : {METERING_CODE}")
    print(f"Tariftyp  : {TARIFF_TYPE} (Gesamtpreis)")
    print(f"Zeitraum  : {rows[0][0].strftime('%Y-%m-%d %H:%M')} – {rows[-1][1].strftime('%Y-%m-%d %H:%M')} (lokal)\n")

    print(">> Aktueller Preis:")
    print(f"  {st.strftime('%Y-%m-%d %H:%M')} – {en.strftime('%H:%M')}  ->  {pr:.5f} CHF/kWh\n")

   
  
    print(">> Nächste 24h (15-Min-Raster):")
    for st, en, pr in sorted(rows, key=lambda x: x[0]):
        print(f"{st.strftime('%Y-%m-%d %H:%M')} ; {pr:.5f}")

    # CSV speichern
    csv_path = "esit_prices.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["start_local", "end_local", "price_chf_per_kwh"])
        for st, en, pr in sorted(rows, key=lambda x: x[0]):
            w.writerow([st.isoformat(timespec="seconds"), en.isoformat(timespec="seconds"), f"{pr:.8f}"])
    print(f"\nCSV gespeichert: {os.path.abspath(csv_path)}")

    csv_path = "esit_prices.csv"

    first_price = None
    first_start = None
    first_end = None

    with open(csv_path, newline="", encoding="utf-8") as f:
      reader = csv.DictReader(f)
      first_row = next(reader, None)  # erste Zeile nach dem Header
      if first_row:
        first_price = float(first_row["price_chf_per_kwh"])*100
        first_start = first_row["start_local"]
        first_end   = first_row["end_local"]

    if first_price is None:
      raise RuntimeError("CSV-Datei leer oder fehlerhaft!")

    print(first_price)
  
    write_vals(UUID["Energiepreis"], first_price)

if __name__ == "__main__":
    main()
