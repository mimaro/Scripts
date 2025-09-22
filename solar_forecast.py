#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PV-Ertragsforecast (48h, stündlich) aus SRF Meteo Stundenvorhersage

Eingabe:  /home/pi/Scripts/haegglingen_5607_48h.json  (aus srf_weather_haegglingen.py)
Ausgabe:  /home/pi/Scripts/pv_yield_48h.json

Berechnung:
- POA-Abschätzung aus GHI (IRRADIANCE_WM2) per Orientierungsfaktor ~ cos(θi)/sin(α)
  (α=Solarhöhe, θi=Einfallswinkel auf Modulfläche).
- Modultemperatur: T_mod ≈ T_amb + (NOCT-20)/800 * POA
- Temperaturkoeffizient: gamma_T = -0.004 / K  → P = P_STC * (POA/1000) * (1 + gamma_T*(T_mod-25))
- Stunde ≈ Mittelpunktszeit (date_time - 30 min). Bei α ≤ 0 → Ertrag 0.

Konfiguration unten anpassen (Neigung, Azimut, kWp je Teilanlage).
"""

import json
import math
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any

try:
    from zoneinfo import ZoneInfo  # Py 3.9+
except Exception:
    ZoneInfo = None

# ----------- zentrale KONFIGURATION ------------
INPUT_JSON  = "/home/pi/Scripts/haegglingen_5607_48h.json"
OUTPUT_JSON = "/home/pi/Scripts/pv_yield_48h.json"
LOCAL_TZ    = "Europe/Zurich"  # Zeitzone für Mittelpunktszeit u. Ausgabe

# Azimut-Konvention: 0°=Nord, 90°=Ost, 180°=Süd, 270°=West
CONFIG = {
    "noct_c": 45.0,              # typische NOCT in °C
    "temp_coeff_per_K": -0.004,  # -0.4 % / K
    "arrays": [
        {"name": "east", "tilt_deg": 20.0, "azimuth_deg": 90.0,  "power_kwp": 9.87},
        {"name": "west", "tilt_deg": 20.0, "azimuth_deg": 270.0, "power_kwp": 5.67},
    ],
}
# -----------------------------------------------


def parse_dt(dt_str: str) -> datetime:
    """ISO-8601 robust nach UTC wandeln."""
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    return (dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)


def solar_position(dt_local: datetime, lat_deg: float, lon_deg: float) -> Dict[str, float]:
    """
    NOAA-ähnliche vereinfachte Sonnenstandsberechnung.
    Eingabezeit: lokale Zonenzeit (keine Sommerzeit-Korrektur nötig, ZoneInfo erledigt das).
    Rückgabe: elevation_deg (α), azimuth_deg (0=N, 90=E, 180=S, 270=W).
    """
    # Datum/Zeiten
    doy = int(dt_local.timetuple().tm_yday)
    hr = dt_local.hour + dt_local.minute / 60.0 + dt_local.second / 3600.0
    tz_hours = dt_local.utcoffset().total_seconds() / 3600.0 if dt_local.utcoffset() else 0.0

    # Fraktionales Jahr γ (rad)
    gamma = 2.0 * math.pi / 365.0 * (doy - 1 + (hr - 12) / 24.0)

    # Gleichung der Zeit (min) & Deklination δ (rad)
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * math.cos(gamma)
        - 0.032077 * math.sin(gamma)
        - 0.014615 * math.cos(2 * gamma)
        - 0.040849 * math.sin(2 * gamma)
    )
    decl = (
        0.006918
        - 0.399912 * math.cos(gamma)
        + 0.070257 * math.sin(gamma)
        - 0.006758 * math.cos(2 * gamma)
        + 0.000907 * math.sin(2 * gamma)
        - 0.002697 * math.cos(3 * gamma)
        + 0.001480 * math.sin(3 * gamma)
    )

    # Stundenwinkel H (deg)
    time_offset = eq_time + 4.0 * lon_deg - 60.0 * tz_hours
    tst = hr * 60.0 + time_offset  # true solar time (min)
    ha_deg = (tst / 4.0) - 180.0
    # Wrap in [-180, 180]
    while ha_deg < -180.0:
        ha_deg += 360.0
    while ha_deg > 180.0:
        ha_deg -= 360.0
    ha = math.radians(ha_deg)

    lat = math.radians(lat_deg)
    # Elevation α
    sin_alpha = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    sin_alpha = max(-1.0, min(1.0, sin_alpha))
    alpha = math.asin(sin_alpha)

    # Azimut (0=N, 90=E ...) – robust via atan2
    cos_alpha = max(1e-6, math.cos(alpha))
    az = math.atan2(
        math.sin(ha),
        math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat),
    )
    # atan2 gibt Winkel relativ zu Süden; wir mappen auf 0..360 ab Norden:
    az_deg = (math.degrees(az) + 180.0) % 360.0

    return {"elevation_deg": math.degrees(alpha), "azimuth_deg": az_deg}


def plane_of_array_from_ghi(ghi_wm2: float, sun_elev_deg: float, sun_az_deg: float,
                            tilt_deg: float, panel_az_deg: float) -> float:
    """
    Sehr einfache POA-Schätzung aus GHI:
      POA ≈ GHI * max(0, cos(θi)) / max(ε, sin(α))
    mit α = Sonnenhöhe, θi = Einfallswinkel.
    Achtung: physikalisch nicht exakt – genügt als robuste Näherung ohne DNI/DHI.
    """
    if ghi_wm2 <= 0.0 or sun_elev_deg <= 0.0:
        return 0.0

    rad = math.radians
    alpha = rad(sun_elev_deg)
    beta = rad(tilt_deg)
    dgamma = rad((sun_az_deg - panel_az_deg + 540.0) % 360.0 - 180.0)  # auf [-180,180]

    cos_alpha = math.cos(alpha)
    sin_alpha = math.sin(alpha)

    # cos(θi) für geneigte Fläche:
    cos_ti = sin_alpha * math.cos(beta) + cos_alpha * math.sin(beta) * math.cos(dgamma)
    cos_ti = max(0.0, cos_ti)

    denom = max(0.05, sin_alpha)  # ε verhindert Division nahe Sonnenauf-/untergang
    factor = cos_ti / denom
    # Begrenzen, um irreale Peaks bei sehr flacher Sonne zu vermeiden
    factor = max(0.0, min(1.6, factor))
    return ghi_wm2 * factor


def module_temperature(amb_c: float, poa_wm2: float, noct_c: float) -> float:
    """T_mod ≈ T_amb + (NOCT-20)/800 * POA (°C)."""
    return amb_c + (noct_c - 20.0) / 800.0 * max(0.0, poa_wm2)


def pv_power_kw(poa_wm2: float, t_mod_c: float, p_stc_kwp: float, temp_coeff_per_K: float) -> float:
    """
    DC-Leistung in kW bei POA und Modultemperatur (einfaches STC-Scaling mit Temperaturkoeffizient).
    Clipping gegen <0.
    """
    p = p_stc_kwp * (max(0.0, poa_wm2) / 1000.0) * (1.0 + temp_coeff_per_K * (t_mod_c - 25.0))
    return max(0.0, p)


def load_input(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        raise FileNotFoundError(f"Eingabedatei nicht gefunden: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main() -> int:
    data = load_input(INPUT_JSON)
    hours: List[Dict[str, Any]] = data.get("hours") or []
    place = data.get("place") or {}
    lat = float(place.get("lat", 47.3870))  # Fallback grob Hägglingen
    lon = float(place.get("lon", 8.2500))

    if not hours:
        print("Keine Stundenwerte in der Eingabedatei gefunden.", file=sys.stderr)
        return 1

    tz = ZoneInfo(LOCAL_TZ) if ZoneInfo else None

    out_rows: List[Dict[str, Any]] = []

    for row in hours:
        # Zeitpunkt: Mittelpunktszeit der Stunde (dt_end - 30 min)
        dt_end_utc = parse_dt(row["date_time"])
        dt_mid_utc = dt_end_utc - timedelta(minutes=30)
        dt_local = dt_mid_utc.astimezone(tz) if tz else dt_mid_utc

        ghi = float(row.get("IRRADIANCE_WM2", 0) or 0)
        amb = float(row.get("TTT_C", 0) or 0)

        # Sonnenstand
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

            # Energie der Stunde in kWh ~ Leistung * 1h
            ekwh = pkw * 1.0

            total_power_kw += pkw
            parts[name] = {
                "poa_wm2": round(poa, 1),
                "t_module_c": round(tmod, 1),
                "p_kw": round(pkw, 3),
                "e_kwh": round(ekwh, 3),
            }

        out_rows.append({
            "time_iso": dt_local.isoformat(),
            "ghi_wm2": round(ghi, 1),
            "ambient_c": round(amb, 1),
            "sun_elevation_deg": round(elev, 2),
            "sun_azimuth_deg": round(az, 2),
            "east": parts.get("east"),
            "west": parts.get("west"),
            "pv_total_power_kw": round(total_power_kw, 3),
            "pv_total_energy_kwh": round(total_power_kw * 1.0, 3),
        })

    # Nur die nächsten 48h behalten (falls mehr im File steckt)
    out_rows.sort(key=lambda r: r["time_iso"])
    out_rows = out_rows[:48]

    # Speichern
    out_payload = {
        "source": INPUT_JSON,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": lat, "lon": lon, "tz": LOCAL_TZ},
        "config": CONFIG,
        "hours": out_rows,
    }
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)

    print(f"OK – PV-Ertragsforecast gespeichert: {OUTPUT_JSON} (Stunden: {len(out_rows)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

