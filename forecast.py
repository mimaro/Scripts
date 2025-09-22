#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import csv
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# ---------------------------------------------------------------------------------------------------
# Volkszähler Endpoints
VZ_GET_URL  = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
# ---------------------------------------------------------------------------------------------------

# UUIDs in Volkszähler (bitte prüfen)
UUID = {
    "T_outdoor_forecast": "c56767e0-97c1-11f0-96ab-41d2e85d0d5f",
    "P_PV_forecast":      "abcf6600-97c1-11f0-9348-db517d4efb8f",
}

# Eingaben/Ausgabe
WEATHER_CSV = "/home/pi/Scripts/haegglingen_5607_48h.csv"
PV_CSV_MAIN = "/home/pi/Scripts/pv_yield_48h.csv"
PV_CSV_ALT  = "/home/pi/Scripts/py_yield_48h.csv"   # Fallback, falls Tippfehler
OUT_JSON    = "/home/pi/Scripts/next_hour_values.json"
LOCAL_TZ    = "Europe/Zurich"


# ========== Hilfsfunktionen Volkszähler ==========
def get_vals(uuid: str, duration: str = "-0min"):
    """Daten von Volkszähler lesen (optional, hier nicht zwingend genutzt)."""
    req = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    req.raise_for_status()
    return req.json()

def write_vals(uuid: str, val: float) -> None:
    """Wert zu Volkszähler posten."""
    post_url = VZ_POST_URL.format(uuid, val)
    r = requests.post(post_url, timeout=10)
    if not r.ok:
        raise RuntimeError(f"VZ-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")


# ========== Zeit & Parsing ==========
def parse_iso_any(s: str) -> datetime:
    """ISO-8601 robust parsen und als aware UTC zurückgeben."""
    s = s.strip()
    if s.endswith("Z"):
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc
            dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)

def next_full_hour_local(now: Optional[datetime] = None) -> datetime:
    """Ende der aktuellen Stunde als aware Local-Zeit (Europe/Zurich)."""
    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc
    if now is None:
        now = datetime.now(tz)
    else:
        now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    return (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))


# ========== CSV-Leser ==========
def read_weather_next_ttt(weather_csv: str, hour_end_local: datetime) -> Tuple[float, datetime]:
    """
    Aus Wetter-CSV die Zeile mit date_time == hour_end_local (Ende der laufenden Stunde) holen.
    Fallback: erste Zeile mit date_time > jetzt.
    """
    target_end_utc = hour_end_local.astimezone(timezone.utc)

    best_row = None
    best_dt_utc = None

    with open(weather_csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "date_time" not in r.fieldnames:
            raise RuntimeError("Spalte 'date_time' fehlt im Wetter-CSV.")
        # Tolerant bzgl. Temperatur-Spaltenname
        t_col_name = "TTT_C" if "TTT_C" in r.fieldnames else ("TTT C" if "TTT C" in r.fieldnames else None)
        if not t_col_name:
            raise RuntimeError("Spalte für Lufttemperatur ('TTT_C' / 'TTT C') fehlt im Wetter-CSV.")

        for row in r:
            try:
                dt_utc = parse_iso_any(row["date_time"])
            except Exception:
                continue

            if dt_utc == target_end_utc:
                best_row, best_dt_utc = row, dt_utc
                break

            if dt_utc > datetime.now(timezone.utc):
                if best_dt_utc is None or dt_utc < best_dt_utc:
                    best_row, best_dt_utc = row, dt_utc

    if not best_row or best_dt_utc is None:
        raise RuntimeError("Keine passende Wetter-Zeile für die nächste volle Stunde gefunden.")

    try:
        ttt_c = float(best_row[t_col_name])
    except Exception as e:
        raise RuntimeError(f"Lufttemperatur konnte nicht gelesen werden: {e}") from e

    return ttt_c, best_dt_utc


def read_pv_next_energy(pv_csv_path: str, hour_end_local: datetime) -> Tuple[float, datetime]:
    """
    Aus PV-CSV die Zeile finden, deren Mittelpunktszeit = hour_end_local - 30 min.
    Fallback: erste Zeile mit time_iso >= target_mid.
    """
    if not os.path.exists(pv_csv_path) and os.path.exists(PV_CSV_ALT):
        pv_csv_path = PV_CSV_ALT

    if not os.path.exists(pv_csv_path):
        raise FileNotFoundError(f"PV-CSV nicht gefunden: {pv_csv_path} (oder {PV_CSV_ALT})")

    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc
    target_mid_local = hour_end_local - timedelta(minutes=30)
    target_mid_utc = target_mid_local.astimezone(timezone.utc)

    chosen_row = None
    chosen_dt_utc = None

    with open(pv_csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "time_iso" not in r.fieldnames:
            raise RuntimeError("Spalte 'time_iso' fehlt im PV-CSV.")
        if "pv_total_energy_kwh" not in r.fieldnames:
            raise RuntimeError("Spalte 'pv_total_energy_kwh' fehlt im PV-CSV.")

        for row in r:
            try:
                dt_utc = parse_iso_any(row["time_iso"])
            except Exception:
                continue

            if abs((dt_utc - target_mid_utc).total_seconds()) <= 30:
                chosen_row, chosen_dt_utc = row, dt_utc
                break

            if dt_utc >= target_mid_utc:
                if chosen_dt_utc is None or dt_utc < chosen_dt_utc:
                    chosen_row, chosen_dt_utc = row, dt_utc

    if not chosen_row or chosen_dt_utc is None:
        raise RuntimeError("Keine passende PV-Zeile für die nächste volle Stunde gefunden.")

    try:
        pv_kwh = float(chosen_row["pv_total_energy_kwh"])
    except Exception as e:
        raise RuntimeError(f"PV-Ertrag konnte nicht gelesen werden: {e}") from e

    return pv_kwh, chosen_dt_utc.astimezone(tz)


# ========== Main ==========
def main() -> int:
    try:
        hour_end_local = next_full_hour_local()

        # Werte für die laufende Stunde ermitteln
        t_aktuell, weather_dt_utc = read_weather_next_ttt(WEATHER_CSV, hour_end_local)
        pv_aktuell, pv_time_local = read_pv_next_energy(PV_CSV_MAIN, hour_end_local)

        # Rundung/Formatierung für VZ (Kommazahl mit Punkt)
        t_out = round(t_aktuell, 2)
        pv_out = round(pv_aktuell, 3)

        # Optional: lokale JSON-Ablage
        out = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "hour_end_local": hour_end_local.isoformat(),
            "weather": {"date_time_end_utc": weather_dt_utc.isoformat(), "TTT_C": t_out},
            "pv": {"time_mid_local": pv_time_local.isoformat(), "pv_total_energy_kwh": pv_out},
            "sources": {"weather_csv": WEATHER_CSV, "pv_csv": PV_CSV_MAIN if os.path.exists(PV_CSV_MAIN) else PV_CSV_ALT},
        }
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        # >>> an Volkszähler schreiben <<<
        write_vals(UUID["T_outdoor_forecast"], t_out)
        write_vals(UUID["P_PV_forecast"], pv_out)

        print(f"OK – geschrieben: T_outdoor_forecast={t_out} °C, P_PV_forecast={pv_out} kWh")
        print(f"(Details auch in {OUT_JSON})")
        return 0

    except Exception as e:
        print(f"Fehler: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


