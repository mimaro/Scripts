#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Swisspower ESIT – dynamische Preise:
- Vergangene 2h + nächste 24h (15-Minuten-Raster)
- Aktueller Slot + CSV-Ausgabe
- NEU: Alle Slots zusätzlich nach Volkszähler schreiben (Rp/kWh) mit korrektem ts (ms UTC)

Voraussetzungen:
  pip3 install requests python-dateutil
"""

import os
import sys
import csv
import logging
from datetime import datetime, timedelta, timezone
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

# Volkszähler
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")
VZ_UUID_PRICE = os.environ.get("VZ_UUID_PRICE", "a1547420-8c87-11f0-ab9a-bd73b64c1942")  # Ziel-UUID
HTTP_TIMEOUT = 20
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
USER_AGENT = "esit-prices-to-vz/1.0"

# CSV
CSV_PATH = os.path.abspath(os.environ.get("ESIT_CSV_PATH", "/home/pi/Scripts/esit_prices.csv"))
# ==========================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------------- Volkszähler-Helfer ----------------
def vz_delete_range(uuid: str, from_ts_ms: int, to_ts_ms: int) -> None:
    """Zeitbereich [from..to] auf UUID löschen (verhindert Duplikate)."""
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "delete", "from": str(from_ts_ms), "to": str(to_ts_ms)}
    if DRY_RUN:
        logging.info("DRY_RUN: VZ DELETE %s %s", url, params)
        return
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
    if not r.ok:
        raise RuntimeError(f"Volkszähler-DELETE fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

def vz_write_point(uuid: str, ts_ms_utc: int, value_float: float) -> None:
    """Punkt (ts in ms UTC, value mit Punktnotation) auf UUID schreiben."""
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {
        "operation": "add",
        "ts": str(ts_ms_utc),
        "value": f"{float(value_float):.6f}",
    }
    if DRY_RUN:
        logging.info("DRY_RUN: VZ POST %s %s", url, params)
        return
    r = requests.post(url, params=params, timeout=HTTP_TIMEOUT, headers={"User-Agent": USER_AGENT})
    if not r.ok:
        raise RuntimeError(f"Volkszähler-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

# ---------------- ESIT/CSV-Logik ----------------
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
    Liefert (price_chf_per_kwh, start_dt_local, end_dt_local).
    Zeitstempel aus API sind i.d.R. TZ-aware (lokal). Falls naiv, als lokal interpretieren.
    """
    st = datetime.fromisoformat(slot["start_timestamp"])
    en = datetime.fromisoformat(slot["end_timestamp"])

    # Bevorzugt 'integrated'
    if prefer and prefer in slot:
        p_int = sum_chf_per_kwh(slot[prefer])
        if p_int > 0 or isinstance(slot.get(prefer), list):
            return p_int, st, en

    # Fallback: electricity + dso (+ grid)
    p = 0.0
    if "electricity" in slot:
        p += sum_chf_per_kwh(slot["electricity"])
    if "dso" in slot:
        p += sum_chf_per_kwh(slot["dso"])
    if p == 0.0 and "grid" in slot:
        p += sum_chf_per_kwh(slot["grid"])
    return p, st, en

def write_csv_atomic(path, rows):
    """
    rows: Iterable (price_chf_per_kwh, start_dt_local, end_dt_local)
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

# ---------------- Zeitstempel-Helfer ----------------
def to_utc_ms(dt_local: datetime) -> int:
    """
    Konvertiert einen (lokalen) datetime nach ms seit Epoch (UTC).
    Falls dt_local naiv ist, wird lokale System-TZ angenommen.
    """
    if dt_local.tzinfo is None:
        dt_local = dt_local.replace(tzinfo=tz.tzlocal())
    dt_utc = dt_local.astimezone(timezone.utc)
    return int(dt_utc.timestamp() * 1000)

# ================================ MAIN ================================
def main():
    if not AUTH_TOKEN:
        print("⚠️  Bitte ESIT_API_TOKEN setzen!", file=sys.stderr)
        sys.exit(1)

    local_tz = tz.tzlocal()
    now_local = datetime.now(local_tz)

    # letzten 2h + nächsten 24h
    start_local = floor_to_quarter(now_local - timedelta(hours=PAST_HOURS))
    # Ende inkl. letztem vollen Slot innerhalb der 24h
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
    rows.sort(key=lambda x: x[1])  # nach Startzeit

    # Aktuellen Slot ermitteln (nur für Anzeige)
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
    print("\n=== Swisspower ESIT – Dynamischer Tarif ===")
    print(f"Messpunkt : {METERING_CODE}")
    print(f"Tariftyp  : {TARIFF_TYPE} (Gesamtpreis)")
    print(f"Zeitraum  : {rows[0][1].strftime('%Y-%m-%d %H:%M')} – {rows[-1][2].strftime('%Y-%m-%d %H:%M')} (lokal)\n")
    print(">> Aktueller Slot:")
    print(f"  {st.strftime('%Y-%m-%d %H:%M')} – {en.strftime('%H:%M')}  ->  {pr:.5f} CHF/kWh\n")

    # CSV atomar schreiben
    try:
        write_csv_atomic(CSV_PATH, rows)
        print(f"CSV gespeichert: {CSV_PATH}")
    except Exception as e:
        print(f"⚠️ CSV konnte nicht gespeichert werden: {e}", file=sys.stderr)

    # ---- NEU: Alle Slots in Rp/kWh an Volkszähler schreiben (mit ts=Slot-START) ----
    # Vorbereitung Zeitbereich zum Löschen
    first_start_ms = to_utc_ms(rows[0][1])
    last_end_ms    = to_utc_ms(rows[-1][2])

    print(f"\nLösche bestehenden Bereich auf {VZ_UUID_PRICE}: {first_start_ms} … {last_end_ms}")
    try:
        vz_delete_range(VZ_UUID_PRICE, first_start_ms, last_end_ms)
    except Exception as e:
        print(f"⚠️ DELETE fehlgeschlagen: {e}", file=sys.stderr)

    print(f"\nSchreibe {len(rows)} 15-Min-Punkte nach Volkszähler (UUID {VZ_UUID_PRICE})…")
    print("Zeit (lokal) | ts_ms_utc | Preis (Rp/kWh)")

    written = 0
    for price_chf, st_local, _en_local in rows:
        ts_ms = to_utc_ms(st_local)                 # Slot-Start als Zeitstempel
        price_rp = price_chf * 100.0                # CHF/kWh → Rp/kWh
        # Konsole zur Kontrolle
        print(f"{st_local.strftime('%Y-%m-%d %H:%M:%S %Z')} | {ts_ms} | {price_rp:.3f}")
        # Schreiben
        try:
            vz_write_point(VZ_UUID_PRICE, ts_ms, price_rp)
            written += 1
        except Exception as e:
            print(f"Warnung: Schreiben @ ts_ms={ts_ms} fehlgeschlagen: {e}", file=sys.stderr)

    print(f"\nFertig – geschrieben: {written}/{len(rows)} Punkte auf {VZ_UUID_PRICE}.")
    if DRY_RUN:
        print("(DRY_RUN aktiv – es wurde nichts in die DB geschrieben.)")

if __name__ == "__main__":
    main()
