#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import csv
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# -----------------------------------------------------------------------------------
# Volkszähler Endpoints
VZ_BASE_URL = "http://192.168.178.49/middleware.php"
# -----------------------------------------------------------------------------------

# UUIDs in Volkszähler (prüfen!)
UUID = {
    "T_outdoor_forecast": "c56767e0-97c1-11f0-96ab-41d2e85d0d5f",
    "P_PV_forecast":      "abcf6600-97c1-11f0-9348-db517d4efb8f",
}

# Eingaben/Ausgabe
WEATHER_CSV = "/home/pi/Scripts/haegglingen_5607_48h.csv"
PV_CSV_MAIN = "/home/pi/Scripts/pv_yield_48h.csv"
PV_CSV_ALT  = "/home/pi/Scripts/py_yield_48h.csv"   # Fallback, falls alter Name
OUT_JSON    = "/home/pi/Scripts/next_hour_values.json"
LOCAL_TZ    = "Europe/Zurich"


# ===================== Volkszähler =====================
def write_vals(uuid: str, val: float) -> None:
    """
    Wert als FLOAT an Volkszähler posten.
    - Immer in float konvertieren
    - Mit Dezimalpunkt formatieren (6 Nachkommastellen)
    - Als Query-Parameter senden (operation=add, value=<float>)
    """
    try:
        v = float(val)
    except Exception as e:
        raise ValueError(f"Wert für UUID {uuid} ist nicht als float interpretierbar: {val!r}") from e

    # Feste Punktnotation, 6 Nachkommastellen
    value_str = f"{v:.6f}"

    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "add", "value": value_str}
    r = requests.post(url, params=params, timeout=10)
    if not r.ok:
        raise RuntimeError(f"VZ-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")


# ===================== Zeit/Parsing =====================
def parse_iso_any(s: str) -> datetime:
    """ISO-8601 robust parsen (mit/ohne ‚Z‘/Offset) → aware UTC."""
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
    """Ende der laufenden Stunde als aware Local (Europe/Zurich)."""
    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc
    if now is None:
        now = datetime.now(tz)
    else:
        now = now.astimezone(tz) if now.tzinfo else now.replace(tzinfo=tz)
    return (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))


# ===================== CSV-Leser =====================
def read_weather_next_ttt(weather_csv: str, hour_end_local: datetime) -> Tuple[float, datetime]:
    """
    Wetter-CSV: die Zeile mit date_time == Ende der laufenden Stunde (lokal) finden.
    Fallback: erste Zeile mit date_time >= jetzt.
    """
    target_end_utc = hour_end_local.astimezone(timezone.utc)

    best_row = None
    best_dt_utc = None

    with open(weather_csv, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        if "date_time" not in r.fieldnames:
            raise RuntimeError("Spalte 'date_time' fehlt im Wetter-CSV.")

        # Temperatur-Spalte tolerant behandeln
        t_col = "TTT_C" if "TTT_C" in r.fieldnames else ("TTT C" if "TTT C" in r.fieldnames else None)
        if not t_col:
            raise RuntimeError("Spalte für Lufttemperatur ('TTT_C' / 'TTT C') fehlt im Wetter-CSV.")

        for row in r:
            try:
                dt_utc = parse_iso_any(row["date_time"])
            except Exception:
                continue

            # exakte Übereinstimmung ±30s
            if abs((dt_utc - target_end_utc).total_seconds()) <= 30:
                best_row, best_dt_utc = row, dt_utc
                break

            # Fallback: erste Zeit >= jetzt
            if dt_utc >= datetime.now(timezone.utc):
                if best_dt_utc is None or dt_utc < best_dt_utc:
                    best_row, best_dt_utc = row, dt_utc

    if not best_row or best_dt_utc is None:
        raise RuntimeError("Keine passende Wetter-Zeile für die nächste volle Stunde gefunden.")

    try:
        ttt_c = float(best_row[t_col])
    except Exception as e:
        raise RuntimeError(f"Lufttemperatur konnte nicht gelesen werden: {e}") from e

    return ttt_c, best_dt_utc


def read_pv_next_energy(pv_csv_path: str, hour_end_local: datetime) -> Tuple[float, datetime]:
    """
    PV-CSV lesen:
      - Wenn 'time_iso' existiert → Zielzeit = Mitte der Stunde = hour_end_local - 30 min.
      - Sonst, wenn 'date_time' existiert → Zielzeit = Stundenende = hour_end_local.
      - Fallback: erste Zeile mit Zeit >= Zielzeit.
      - Energie: bevorzugt 'pv_total_energy_kwh'; falls nicht vorhanden, 'pv_total_power_kw' * 1 h.
    Gibt (Energie_kWh, Zeitstempel_local) zurück.
    """
    if not os.path.exists(pv_csv_path) and os.path.exists(PV_CSV_ALT):
        pv_csv_path = PV_CSV_ALT
    if not os.path.exists(pv_csv_path):
        raise FileNotFoundError(f"PV-CSV nicht gefunden: {pv_csv_path} (oder {PV_CSV_ALT})")

    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc
    chosen_row = None
    chosen_dt_utc = None

    with open(pv_csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fields = r.fieldnames or []

        # Zeitspalte
        if "time_iso" in fields:
            target_dt_local = hour_end_local - timedelta(minutes=30)
            time_col = "time_iso"
        elif "date_time" in fields:
            target_dt_local = hour_end_local
            time_col = "date_time"
        else:
            raise RuntimeError("Weder 'time_iso' noch 'date_time' in PV-CSV gefunden.")

        # Energie-/Leistungsspalte
        energy_col = None
        if "pv_total_energy_kwh" in fields:
            energy_col = "pv_total_energy_kwh"
        elif "pv_total_power_kw" in fields:
            energy_col = "pv_total_power_kw"  # interpretieren als kWh für 1h
        else:
            raise RuntimeError("Weder 'pv_total_energy_kwh' noch 'pv_total_power_kw' im PV-CSV gefunden.")

        target_dt_utc = target_dt_local.astimezone(timezone.utc)

        for row in r:
            try:
                dt_utc = parse_iso_any(row[time_col])
            except Exception:
                continue

            if abs((dt_utc - target_dt_utc).total_seconds()) <= 30:
                chosen_row, chosen_dt_utc = row, dt_utc
                break

            if dt_utc >= target_dt_utc:
                if chosen_dt_utc is None or dt_utc < chosen_dt_utc:
                    chosen_row, chosen_dt_utc = row, dt_utc

    if not chosen_row or chosen_dt_utc is None:
        raise RuntimeError("Keine passende PV-Zeile für die laufende Stunde gefunden.")

    try:
        val = float(chosen_row[energy_col])
    except Exception as e:
        raise RuntimeError(f"PV-Wert konnte nicht gelesen werden ({energy_col}): {e}") from e

    pv_kwh = val if energy_col == "pv_total_energy_kwh" else val * 1.0  # 1h
    return float(pv_kwh), chosen_dt_utc.astimezone(tz)


# ===================== Main =====================
def main() -> int:
    try:
        hour_end_local = next_full_hour_local()

        # Werte für die laufende Stunde
        t_aktuell, weather_dt_utc = read_weather_next_ttt(WEATHER_CSV, hour_end_local)
        pv_aktuell, pv_time_local = read_pv_next_energy(PV_CSV_MAIN, hour_end_local)

        # Float-Format für VZ
        t_out = float(f"{float(t_aktuell):.6f}")   # garantiert float, punktbasiert
        pv_out = float(f"{float(pv_aktuell):.6f}")/60

        # Lokale JSON-Ablage (Debug)
        out = {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "hour_end_local": hour_end_local.isoformat(),
            "weather": {"date_time_end_utc": weather_dt_utc.isoformat(), "TTT_C": t_out},
            "pv": {"time_ref_local": pv_time_local.isoformat(), "pv_total_energy_kwh": pv_out},
            "sources": {"weather_csv": WEATHER_CSV, "pv_csv": PV_CSV_MAIN if os.path.exists(PV_CSV_MAIN) else PV_CSV_ALT},
        }
        os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
        with open(OUT_JSON, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)

        # → Volkszähler schreiben (float)
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
