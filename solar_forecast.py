#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PV-Ertragsforecast: aktuelle Stunde + nächste 48h (insgesamt bis zu 49 Stundenpunkte)

Eingabe:  /home/pi/Scripts/haegglingen_5607_48h.json  (aus srf_weather_haegglingen.py)
Ausgabe:  /home/pi/Scripts/pv_yield_48h.json  und  /home/pi/Scripts/pv_yield_48h.csv

Berechnung:
- POA-Abschätzung aus GHI (IRRADIANCE_WM2) mit einfacher Geometrie (Ausrichtung/Neigung).
- Modultemperatur: T_mod ≈ T_amb + (NOCT-20)/800 * POA
- Tempkoeffizient: -0.4 %/K → P = kWp * (POA/1000) * (1 + gamma*(T_mod-25))
- Stundenenergie ≈ P_kW * 1 h
- Zeitstempel: Mittelpunktszeit der Stunde (date_time_end - 30 min).
- Auswahlfenster: ab Ende der laufenden Stunde (nächste volle Stunde) inkl. dieser bis +48h danach.

Konfiguration unten anpassen (Neigung, Azimut, kWp je Teilanlage).
"""

import csv
import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

try:
    from zoneinfo import ZoneInfo  # Py 3.9+
except Exception:
    ZoneInfo = None

# ----------- zentrale KONFIGURATION ------------
INPUT_JSON   = "/home/pi/Scripts/haegglingen_5607_48h.json"
OUTPUT_JSON  = "/home/pi/Scripts/pv_yield_48h.json"
OUTPUT_CSV   = "/home/pi/Scripts/pv_yield_48h.csv"
LOCAL_TZ     = "Europe/Zurich"  # Ausgabe-Zone

# Azimut: 0°=Nord, 90°=Ost, 180°=Süd, 270°=West
CONFIG = {
    "noct_c": 45.0,              # typische NOCT in °C
    "temp_coeff_per_K": -0.004,  # -0.4 % / K
    "arrays": [
        {"name": "east", "tilt_deg": 30.0, "azimuth_deg": 90.0,  "power_kwp": 5.0},
        {"name": "west", "tilt_deg": 30.0, "azimuth_deg": 270.0, "power_kwp": 5.0},
    ],
}
# -----------------------------------------------


def parse_dt(dt_str: str) -> datetime:
    """ISO-8601 robust nach UTC wandeln (SRF date_time ist Ende des Stundenintervalls)."""
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def solar_position(dt_local: datetime, lat_deg: float, lon_deg: float) -> Dict[str, float]:
    """Vereinfachte Sonnenstandsberechnung. Rückgabe: elevation_deg (α), azimuth_deg (0=N,90=E,180=S,270=W)."""
    doy = int(dt_local.timetuple().tm_yday)
    hr = dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0
    tz_hours = dt_local.utcoffset().total_seconds() / 3600.0 if dt_local.utcoffset() else 0.0

    gamma = 2.0 * math.pi / 365.0 * (doy - 1 + (hr - 12) / 24.0)
    eq_time = 229.18 * (
        0.000075 + 0.001868 * math.cos(gamma) - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma) - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918 - 0.399912 * math.cos(gamma) + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma) + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma) + 0.001480 * math.sin(3 * gamma)
    )

    time_offset = eq_time + 4.0 * lon_deg - 60.0 * tz_hours
    tst = hr * 60.0 + time_offset
    ha_deg = (tst / 4.0) - 180.0
    # wrap
    while ha_deg < -180.0:
        ha_deg += 360.0
    while ha_deg > 180.0:
        ha_deg -= 360.0
    ha = math.radians(ha_deg)
    lat = math.radians(lat_deg)

    sin_alpha = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    sin_alpha = max(-1.0, min(1.0, sin_alpha))
    alpha = math.asin(sin_alpha)

    az = math.atan2(
        math.sin(ha),
        math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat),
    )
    az_deg = (math.degrees(az) + 180.0) % 360.0
    return {"elevation_deg": math.degrees(alpha), "azimuth_deg": az_deg}


def plane_of_array_from_ghi(ghi_wm2: float, sun_elev_deg: float, sun_az_deg: float,
                            tilt_deg: float, panel_az_deg: float) -> float:
    """
    POA-Schätzung aus GHI:
      POA ≈ GHI * max(0, cos(θi)) / max(ε, sin(α)), begrenzt auf ≤1.6⋅GHI/sin(α)
    """
    if ghi_wm2 <= 0.0 or sun_elev_deg <= 0.0:
        return 0.0

    rad = math.radians
    alpha = rad(sun_elev_deg)
    beta = rad(tilt_deg)
    dgamma = rad((sun_az_deg - panel_az_deg + 540.0) % 360.0 - 180.0)

    cos_alpha = math.cos(alpha)
    sin_alpha = math.sin(alpha)

    cos_ti = sin_alpha * math.cos(beta) + cos_alpha * math.sin(beta) * math.cos(dgamma)
    cos_ti = max(0.0, cos_ti)

    denom = max(0.05, sin_alpha)
    factor = max(0.0, min(1.6, cos_ti / denom))
    return ghi_wm2 * factor


def module_temperature(amb_c: float, poa_wm2: float, noct_c: float) -> float:
    """T_mod ≈ T_amb + (NOCT-20)/800 * POA (°C)."""
    return amb_c + (noct_c - 20.0) / 800.0 * max(0.0, poa_wm2)


def pv_power_kw(poa_wm2: float, t_mod_c: float, p_stc_kwp: float, temp_coeff_per_K: float) -> float:
    """DC-Leistung in kW (STC-Skalierung + Temperaturkoeffizient)."""
    p = p_stc_kwp * (max(0.0, poa_wm2) / 1000.0) * (1.0 + temp_coeff_per_K * (t_mod_c - 25.0))
    return max(0.0, p)


def load_input(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Eingabedatei nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_csv(path: str, rows: List[Dict[str, Any]], array_names: List[str]) -> None:
    """Flacht die Teilanlagenwerte für die CSV-Ausgabe auf Spaltenebene ab."""
    base_cols = ["time_iso", "ghi_wm2", "ambient_c", "sun_elevation_deg", "sun_azimuth_deg"]
    per_arr_cols = []
    for name in array_names:
        per_arr_cols += [
            f"{name}_poa_wm2",
            f"{name}_t_module_c",
            f"{name}_p_kw",
            f"{name}_e_kwh",
        ]
    tail_cols = ["pv_total_power_kw", "pv_total_energy_kwh"]
    columns = base_cols + per_arr_cols + tail_cols

    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=columns)
        w.writeheader()
        for r in rows:
            out = {k: r.get(k, "") for k in base_cols}
            for name in array_names:
                part = r.get(name) or {}
                out[f"{name}_poa_wm2"] = part.get("poa_wm2", "")
                out[f"{name}_t_module_c"] = part.get("t_module_c", "")
                out[f"{name}_p_kw"] = part.get("p_kw", "")
                out[f"{name}_e_kwh"] = part.get("e_kwh", "")
            out["pv_total_power_kw"] = r.get("pv_total_power_kw", "")
            out["pv_total_energy_kwh"] = r.get("pv_total_energy_kwh", "")
            w.writerow(out)


def main() -> int:
    data = load_input(INPUT_JSON)
    hours: List[Dict[str, Any]] = data.get("hours") or []
    place = data.get("place") or {}
    lat = float(place.get("lat", 47.3870))  # Fallback: Hägglingen
    lon = float(place.get("lon", 8.2500))

    if not hours:
        print("Keine Stundenwerte in der Eingabedatei gefunden.", file=sys.stderr)
        return 1

    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else None
    now_local = datetime.now(tz) if tz else datetime.now(timezone.utc)
    # Ende der aktuellen Stunde (nächste volle Stunde, lokale Zeit)
    current_hour_end_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    current_hour_end_utc = current_hour_end_local.astimezone(timezone.utc)

    # Auswahlfenster: [Ende aktuelle Stunde, Ende aktuelle + 48h]
    window_end_utc = current_hour_end_utc + timedelta(hours=48)

    # Parse alle Stunden-Endzeiten (UTC) und filtere auf Fenster
    parsed: List[Dict[str, Any]] = []
    for row in hours:
        dt_end_utc = parse_dt(row["date_time"])
        if current_hour_end_utc <= dt_end_utc <= window_end_utc:
            parsed.append({"raw": row, "dt_end_utc": dt_end_utc})

    # Sortieren nach Endzeit
    parsed.sort(key=lambda r: r["dt_end_utc"])

    results: List[Dict[str, Any]] = []

    for item in parsed:
        row = item["raw"]
        dt_end_utc = item["dt_end_utc"]
        dt_mid_utc = dt_end_utc - timedelta(minutes=30)
        dt_local = dt_mid_utc.astimezone(tz) if tz else dt_mid_utc

        ghi = float(row.get("IRRADIANCE_WM2", 0) or 0)
        amb = float(row.get("TTT_C", 0) or 0)

        # Sonnenstand zur Mittelpunktszeit
        sp = solar_position(dt_local, lat, lon)
        elev = sp["elevation_deg"]
        az = sp["azimuth_deg"]

        total_power_kw = 0.0
        parts: Dict[str, Any] = {}

        for arr in CONFIG["arrays"]:
            name = arr["name"]
            tilt = float(arr["tilt_deg"])
            paz  = float(arr["azimuth_deg"])
            pkwp = float(arr["power_kwp"])

            poa = plane_of_array_from_ghi(ghi, elev, az, tilt, paz)
            tmod = module_temperature(amb, poa, CONFIG["noct_c"])
            pkw  = pv_power_kw(poa, tmod, pkwp, CONFIG["temp_coeff_per_K"])
            ekwh = pkw * 1.0  # 1 Stunde

            total_power_kw += pkw
            parts[name] = {
                "poa_wm2": round(poa, 1),
                "t_module_c": round(tmod, 1),
                "p_kw": round(pkw, 3),
                "e_kwh": round(ekwh, 3),
            }

        # Standardmäßig erwarten wir "east" und "west" – die CSV baut aber dynamisch aus CONFIG["arrays"].
        record = {
            "time_iso": dt_local.isoformat(),
            "ghi_wm2": round(ghi, 1),
            "ambient_c": round(amb, 1),
            "sun_elevation_deg": round(elev, 2),
            "sun_azimuth_deg": round(az, 2),
            "pv_total_power_kw": round(total_power_kw, 3),
            "pv_total_energy_kwh": round(total_power_kw * 1.0, 3),
        }
        # Teilanlagen unter ihren Namen anfügen (z. B. "east", "west")
        for name, part in parts.items():
            record[name] = part

        results.append(record)

    # Speichern (JSON)
    out_payload = {
        "source": INPUT_JSON,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "note": "Enthält die aktuelle Stunde (Ende = nächste volle Stunde) + die nächsten 48 Stunden.",
        "location": {"lat": lat, "lon": lon, "tz": LOCAL_TZ},
        "config": CONFIG,
        "count_hours": len(results),
        "hours": results,
    }
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)

    # Speichern (CSV) – Spalten aus den in CONFIG definierten Teilanlagen gebildet
    array_names = [a["name"] for a in CONFIG["arrays"]]
    write_csv(OUTPUT_CSV, results, array_names)

    print(f"OK – PV-Ertragsforecast gespeichert: {OUTPUT_JSON} und {OUTPUT_CSV} (Stunden: {len(results)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
