#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PV-Ertragsforecast aus CSV (robust):
- Liest GHI (Globalstrahlung) in W/m² und Lufttemperatur aus flexiblen Spaltennamen.
- Exakte Zeitpunkte des Input-CSV (Spalte 'date_time' – anpassbar) werden 1:1 übernommen.
- Mittelpunktszeit = date_time_end - 30 min (Europe/Zurich) für Sonnenstand/Geometrie.
- POA-Abschätzung aus GHI mit einfacher Geometrie (Tilt/Azimut).
- Modultemperatur: T_mod ≈ T_amb + (NOCT-20)/800 * POA.
- Temperaturkoeffizient: -0.4 % / K (anpassbar).

NEU (gemäß Anforderung):
- Anlagengröße in m² statt kWp.
- Zentraler Anlagenwirkungsgrad (eta_stc, z. B. 17 %).
- Leistung: P_kW = (POA_Wm2 * Fläche_m2 * eta_stc * (1 + gamma*(Tmod-25))) / 1000.

Eingabe:  /home/pi/Scripts/haegglingen_5607_48h.csv
Ausgaben: /home/pi/Scripts/pv_yield_48h.json  und  /home/pi/Scripts/pv_yield_48h.csv

Hinweis: Dieses Skript versucht automatisch, die korrekten Spalten für GHI und Temperatur
zu finden (mehrere Kandidaten, inkl. deutschsprachiger Varianten). Bei Bedarf in CONFIG
zentral anpassen.
"""

import csv
import json
import math
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# ------------- zentrale KONFIGURATION -------------
INPUT_CSV    = "/home/pi/Scripts/haegglingen_5607_48h.csv"
OUTPUT_JSON  = "/home/pi/Scripts/pv_yield_48h.json"
OUTPUT_CSV   = "/home/pi/Scripts/pv_yield_48h.csv"
LOCAL_TZ     = "Europe/Zurich"  # Zeitzone für Mittelpunktszeit

# Standort Hägglingen (falls nicht separat angegeben)
LAT = 47.3870
LON = 8.2500

# Azimut: 0°=Nord, 90°=Ost, 180°=Süd, 270°=West
CONFIG = {
    # CSV-Konfiguration: Spaltenkandidaten (Groß-/Kleinschreibung egal)
    "csv_columns": {
        "time": "date_time",
        "ghi_candidates": [
            "IRRADIANCE_WM2", "GHI_WM2", "GHI", "GLOBAL_IRRADIANCE_WM2",
            "GLOBALSTRAHLUNG_W_M2", "GLOBALSTRAHLUNG", "RAD_GLOB_WM2",
            "SHORTWAVE_RADIATION_W_M2", "SWGDN"
        ],
        "temp_candidates": [
            "TTT_C", "T2M_C", "TEMP_C", "T_AIR_C", "TA_C", "AIR_TEMPERATURE_C"
        ],
    },

    # Physikalische/Anlagen-Parameter
    "noct_c": 45.0,              # typische NOCT in °C
    "temp_coeff_per_K": -0.004,  # -0.4 % / K
    "eta_stc": 0.17,             # Anlagenwirkungsgrad (STC) → 17 %

    # Zwei Teilanlagen (Fläche in m² statt kWp!)
    "arrays": [
        {"name": "east", "tilt_deg": 30.0, "azimuth_deg": 90.0,  "area_m2": 30.0},
        {"name": "west", "tilt_deg": 30.0, "azimuth_deg": 270.0, "area_m2": 30.0},
    ],
}
# --------------------------------------------------


def ensure_tz() -> Optional[ZoneInfo]:
    return ZoneInfo(LOCAL_TZ) if ZoneInfo else None


def parse_iso_to_utc(s: str) -> datetime:
    """CSV-ISO-Zeit robust nach UTC (aware) wandeln."""
    s = s.strip()
    if s.endswith("Z"):
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    else:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            tz = ensure_tz() or timezone.utc
            dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)


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


def pv_power_kw_from_area(poa_wm2: float, t_mod_c: float, area_m2: float,
                          eta_stc: float, temp_coeff_per_K: float) -> float:
    """DC-Leistung [kW] aus Fläche [m²], POA [W/m²], Wirkungsgrad und Temp.-Korrektur."""
    if poa_wm2 <= 0.0 or area_m2 <= 0.0 or eta_stc <= 0.0:
        return 0.0
    # Wirkungsgrad mit Temperaturkorrektur (linear):
    eta = eta_stc * (1.0 + temp_coeff_per_K * (t_mod_c - 25.0))
    eta = max(0.0, eta)  # physikalische Untergrenze
    p_w = poa_wm2 * area_m2 * eta
    return max(0.0, p_w) / 1000.0


# ---------- CSV-Helfer ----------

def _norm(s: str) -> str:
    return "".join(ch for ch in s.strip().lower() if ch.isalnum() or ch == "_")


def choose_column(fieldnames: List[str], candidates: List[str]) -> Optional[str]:
    if not fieldnames:
        return None
    norm_map = {_norm(fn): fn for fn in fieldnames}
    for cand in candidates:
        n = _norm(cand)
        if n in norm_map:
            return norm_map[n]
    # fallback: einfache startswith/contains-Heuristik
    for fn in fieldnames:
        nfn = _norm(fn)
        for cand in candidates:
            nc = _norm(cand)
            if nfn.startswith(nc) or nc in nfn:
                return fn
    return None


def to_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    if isinstance(val, (float, int)):
        return float(val)
    s = str(val).strip().replace(",", ".")
    try:
        return float(s)
    except Exception:
        return default


def read_weather_rows(csv_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Eingabedatei nicht gefunden: {csv_path}")
    with open(csv_path, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        fields = r.fieldnames or []
        if not fields:
            raise RuntimeError("CSV hat keine Kopfzeile/Spalten.")

        cols_cfg = CONFIG["csv_columns"]
        time_col = cols_cfg.get("time", "date_time")
        ghi_col = choose_column(fields, cols_cfg.get("ghi_candidates", []))
        t_col   = choose_column(fields, cols_cfg.get("temp_candidates", []))

        missing = []
        if time_col not in fields:
            missing.append(time_col)
        if not ghi_col:
            missing.append("<GHI-Spalte>")
        if not t_col:
            missing.append("<Temp-Spalte>")
        if missing:
            raise RuntimeError(
                "Pflichtspalten fehlen oder wurden nicht gefunden: " + ", ".join(missing) +
                f".\nVorhandene Spalten: {fields}"
            )

        rows_raw = list(r)
        colmap = {"time": time_col, "ghi": ghi_col, "temp": t_col}
        return rows_raw, colmap


# ---------- Output CSV ----------

def write_pv_csv(path: str, rows: List[Dict[str, Any]], array_names: List[str]) -> None:
    base_cols = ["date_time", "ghi_wm2", "ambient_c", "sun_elevation_deg", "sun_azimuth_deg"]
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
    tz = ensure_tz()
    weather_rows, colmap = read_weather_rows(INPUT_CSV)

    results: List[Dict[str, Any]] = []

    for row in weather_rows:
        # 1) Zeit aus Input übernehmen (Format unverändert)
        dt_end_str = row[colmap["time"]]
        dt_end_utc = parse_iso_to_utc(dt_end_str)
        dt_mid_utc = dt_end_utc - timedelta(minutes=30)
        dt_mid_local = dt_mid_utc.astimezone(tz) if tz else dt_mid_utc

        # 2) Werte aus CSV
        ghi = to_float(row.get(colmap["ghi"]))
        amb = to_float(row.get(colmap["temp"]))

        # 3) Sonnenstand zur Mittelpunktszeit in Europe/Zurich
        sp = solar_position(dt_mid_local, LAT, LON)
        elev = sp["elevation_deg"]
        az = sp["azimuth_deg"]

        # 4) PV pro Teilanlage (Fläche & Wirkungsgrad)
        total_power_kw = 0.0
        parts: Dict[str, Any] = {}

        for arr in CONFIG["arrays"]:
            name = arr["name"]
            tilt = float(arr["tilt_deg"])  # Neigung
            paz  = float(arr["azimuth_deg"])  # Azimut
            area = float(arr.get("area_m2", 0.0))

            poa  = plane_of_array_from_ghi(ghi, elev, az, tilt, paz)
            tmod = module_temperature(amb, poa, CONFIG["noct_c"])
            pkw  = pv_power_kw_from_area(
                poa_wm2=poa,
                t_mod_c=tmod,
                area_m2=area,
                eta_stc=CONFIG["eta_stc"],
                temp_coeff_per_K=CONFIG["temp_coeff_per_K"],
            )
            ekwh = pkw * 1.0  # 1 Stunde

            total_power_kw += pkw
            parts[name] = {
                "poa_wm2": round(poa, 1),
                "t_module_c": round(tmod, 1),
                "p_kw": round(pkw, 3),
                "e_kwh": round(ekwh, 3),
            }

        # 5) Datensatz mit exakt dem Input-Zeitformat
        record = {
            "date_time": dt_end_str,               # 1:1 aus CSV übernommen
            "ghi_wm2": round(ghi, 1),
            "ambient_c": round(amb, 1),
            "sun_elevation_deg": round(elev, 2),
            "sun_azimuth_deg": round(az, 2),
            "pv_total_power_kw": round(total_power_kw, 3),
            "pv_total_energy_kwh": round(total_power_kw * 1.0, 3),
        }
        for name, part in parts.items():
            record[name] = part

        results.append(record)

    # JSON schreiben
    out_payload = {
        "source": INPUT_CSV,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "location": {"lat": LAT, "lon": LON, "tz": LOCAL_TZ},
        "config": CONFIG,
        "selected_columns": colmap,
        "count_hours": len(results),
        "hours": results,
        "note": (
            "Zeitpunkte ('date_time') stammen 1:1 aus dem Input-CSV; "
            "Sonnenstand bei Mittelpunktszeit (date_time - 30 min) in Europe/Zurich."
        ),
    }
    os.makedirs(os.path.dirname(OUTPUT_JSON), exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump(out_payload, f, ensure_ascii=False, indent=2)

    # CSV schreiben (mit identischen Zeitpunkten/Strings)
    array_names = [a["name"] for a in CONFIG["arrays"]]
    write_pv_csv(OUTPUT_CSV, results, array_names)

    print(
        "OK – PV-Ertragsforecast gespeichert: "
        f"{OUTPUT_JSON} und {OUTPUT_CSV} (Zeilen: {len(results)})\n"
        f"Benutzte Spalten → Zeit: '{colmap['time']}', GHI: '{colmap['ghi']}', T: '{colmap['temp']}'"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
