#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PV-Produktions-Forecast (24h) aus Volkszähler-IRR (W/m²) → kW
- Quelle (lesen):  UUID_P_IRR_FORECAST  (Globalstrahlung in W/m², Stundenende als ts_ms)
- Ziel  (schreiben):a1547420-8c87-11f0-ab9a-bd73b64c1942  (PV-Forecast in kW)
- Raster: exakt 24 Stunden ab Ende der aktuellen Stunde (Europe/Zurich)
- Vor dem Schreiben: vorhandene Werte im 24h-Bereich auf der Ziel-UUID löschen
- CSV-Ausgabe und Konsolen-Kontrolle

Env (optional):
  VZ_BASE_URL             (default: http://192.168.178.49/middleware.php)
  UUID_P_IRR_FORECAST     (default: 510567b0-990b-11f0-bb5b-d33e693aa264)
  UUID_T_OUTDOOR_FORECAST (default: c56767e0-97c1-11f0-96ab-41d2e85d0d5f)
  UUID_PV_FORECAST_OUT    (default: a1547420-8c87-11f0-ab9a-bd73b64c1942)
  OUTPUT_CSV              (default: /home/pi/Scripts/pv_forecast_24h.csv)
  LOCAL_TZ                (default: Europe/Zurich)
  LAT, LON                (default: 47.3870, 8.2500 – Hägglingen)
  DRY_RUN=1               → nur ausgeben, nichts löschen/schreiben
  DEBUG=1                 → Debug-Logs

Voraussetzung: pip install requests
"""

import os
import csv
import math
import sys
import requests
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# --------------------- CONFIG ---------------------
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")

UUID_P_IRR = os.environ.get(
    "UUID_P_IRR_FORECAST",
    "510567b0-990b-11f0-bb5b-d33e693aa264"  # Quelle: IRR W/m² (Forecast)
)
UUID_T_OUTDOOR = os.environ.get(
    "UUID_T_OUTDOOR_FORECAST",
    "c56767e0-97c1-11f0-96ab-41d2e85d0d5f"  # Standard-Quelle: Außentemperatur °C (Forecast)
)
UUID_PV_OUT = os.environ.get(
    "UUID_PV_FORECAST_OUT",
    "a1547420-8c87-11f0-ab9a-bd73b64c1942"  # Ziel: PV-Forecast in kW (neu gewünscht)
)

OUTPUT_CSV = os.environ.get("OUTPUT_CSV", "/home/pi/Scripts/esit_prices.csv")

LOCAL_TZ = os.environ.get("LOCAL_TZ", "Europe/Zurich")
LAT = float(os.environ.get("LAT", "47.3870"))
LON = float(os.environ.get("LON", "8.2500"))

USER_AGENT = "pv-forecast-from-vz/1.2"
TIMEOUT = 25
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# PV-Modell
CONFIG = {
    "noct_c": 45.0,               # Nominal Operating Cell Temp
    "temp_coeff_per_K": -0.004,   # Wirkungsgradänderung pro Kelvin
    "eta_stc": 0.17,              # Modulwirkungsgrad bei STC
    # Zwei Teildächer (Beispielwerte)
    "arrays": [
        {"name": "east", "tilt_deg": 20.0, "azimuth_deg": 90.0,  "area_m2": 58.8},
        {"name": "west", "tilt_deg": 20.0, "azimuth_deg": 270.0, "area_m2": 33.6},
    ],
}

# --------------------- Helpers ---------------------
def _tz() -> timezone:
    return ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc

def _debug(msg: str) -> None:
    if os.environ.get("DEBUG"):
        print(f"[DEBUG] {msg}", file=sys.stderr)

def next_24h_grid_ms() -> List[int]:
    """24 Zeitstempel (ms UTC) für das Ende der Stunden ab nächster voller Stunde."""
    tz = _tz()
    now_local = datetime.now(tz)
    start_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    grid: List[int] = []
    for i in range(24):
        dt_local = start_local + timedelta(hours=i)
        grid.append(int(dt_local.astimezone(timezone.utc).timestamp() * 1000))
    return grid

# --------------------- Volkszähler I/O ---------------------
def vz_get_tuples(uuid: str, from_ms: int, to_ms: int) -> List[Tuple[int, float, int]]:
    """Liest Rohdaten-Tupel [ts_ms, value, count] für UUID im Zeitfenster."""
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"from": str(from_ms), "to": str(to_ms)}
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    data = r.json().get("data", {})
    tuples = data.get("tuples") or []
    out: List[Tuple[int, float, int]] = []
    for t in tuples:
        try:
            ts = int(t[0])
            val = float(t[1])
            qual = int(t[2]) if len(t) > 2 else 1
            out.append((ts, val, qual))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out

def vz_delete_range(uuid: str, from_ms: int, to_ms: int) -> None:
    """Löscht Werte im Bereich [from_ms, to_ms] auf UUID (erfordert DELETE-Rechte)."""
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "delete", "from": str(from_ms), "to": str(to_ms)}
    if DRY_RUN:
        print(f"DRY_RUN: DELETE {url} {params}")
        return
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    if not r.ok:
        raise RuntimeError(f"Volkszähler-DELETE fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

def vz_write_point(uuid: str, ts_ms: int, value: float) -> None:
    """Schreibt einen Punkt (kW) auf UUID (operation=add, ts in ms UTC)."""
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "add", "ts": str(ts_ms), "value": f"{float(value):.6f}"}
    if DRY_RUN:
        print(f"DRY_RUN: POST {url} {params}")
        return
    r = requests.post(url, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    if not r.ok:
        raise RuntimeError(f"Volkszähler-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

# --------------------- Sonnenstand & PV-Modell ---------------------
def solar_position(dt_local: datetime, lat_deg: float, lon_deg: float) -> Dict[str, float]:
    """Vereinfachte Sonnenstandsberechnung: elevation_deg (α), azimuth_deg (0=N,90=E,180=S,270=W)."""
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
    alpha = math.degrees(math.asin(sin_alpha))

    az = math.degrees(math.atan2(
        math.sin(ha),
        math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat)
    ))
    az = (az + 180.0) % 360.0
    return {"elevation_deg": alpha, "azimuth_deg": az}

def plane_of_array_from_ghi(ghi_wm2: float, sun_elev_deg: float, sun_az_deg: float,
                            tilt_deg: float, panel_az_deg: float) -> float:
    """POA ≈ GHI * max(0, cos(θi)) / max(ε, sin(α)), begrenzt auf ≤ 1.6⋅GHI/sin(α)."""
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
    eta = eta_stc * (1.0 + temp_coeff_per_K * (t_mod_c - 25.0))
    eta = max(0.0, eta)
    p_w = poa_wm2 * area_m2 * eta
    return max(0.0, p_w) / 1000.0

# --------------------- CSV ---------------------
def write_csv(path: str, rows: List[Tuple[str, int, float, float, float]]) -> None:
    """
    rows: (local_str, ts_ms, irr_wm2, amb_c, p_kw)
    CSV-Spalten: date_time_local, ts_ms_utc, irr_wm2, t_amb_c, p_pv_kw
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date_time_local", "ts_ms_utc", "irr_wm2", "t_amb_c", "p_pv_kw"])
        for local_str, ts_ms, irr, amb, pkw in rows:
            w.writerow([local_str, ts_ms, f"{irr:.1f}", f"{amb:.1f}", f"{pkw:.3f}"])

# --------------------- MAIN ---------------------
def main() -> int:
    try:
        # 1) 24h-Gitter (ms UTC) ermitteln
        ts_grid = next_24h_grid_ms()
        start_ms, end_ms = ts_grid[0], ts_grid[-1]

        # 2) IRR und T aus VZ lesen
        irr_tuples = vz_get_tuples(UUID_P_IRR, start_ms, end_ms)
        if not irr_tuples:
            print("Keine IRR-Werte im gewünschten 24h-Fenster gefunden.", file=sys.stderr)
            return 2
        irr_map: Dict[int, float] = {ts: val for ts, val, _ in irr_tuples}

        t_tuples = vz_get_tuples(UUID_T_OUTDOOR, start_ms, end_ms)
        t_map: Dict[int, float] = {ts: val for ts, val, _ in t_tuples}

        # 3) Berechnung für alle 24 Zeitpunkte
        tz = _tz()
        preview: List[Tuple[str, int, float, float, float]] = []  # local_str, ts_ms, IRR, T_amb, P_kW

        for ts_ms in ts_grid:
            dt_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            dt_mid_local = (dt_utc - timedelta(minutes=30)).astimezone(tz)

            irr_wm2 = float(irr_map.get(ts_ms, 0.0))
            amb_c   = float(t_map.get(ts_ms, 15.0))  # Fallback 15°C, falls fehlend

            sun = solar_position(dt_mid_local, LAT, LON)

            total_kw = 0.0
            for arr in CONFIG["arrays"]:
                poa = plane_of_array_from_ghi(
                    ghi_wm2=irr_wm2,
                    sun_elev_deg=sun["elevation_deg"],
                    sun_az_deg=sun["azimuth_deg"],
                    tilt_deg=float(arr["tilt_deg"]),
                    panel_az_deg=float(arr["azimuth_deg"]),
                )
                t_mod = module_temperature(amb_c, poa, CONFIG["noct_c"])
                p_kw = pv_power_kw_from_area(
                    poa_wm2=poa,
                    t_mod_c=t_mod,
                    area_m2=float(arr["area_m2"]),
                    eta_stc=CONFIG["eta_stc"],
                    temp_coeff_per_K=CONFIG["temp_coeff_per_K"],
                )
                total_kw += p_kw

            local_str = dt_utc.astimezone(tz).strftime("%Y-%m-%d %H:%M %Z")
            preview.append((local_str, ts_ms, irr_wm2, amb_c, round(total_kw, 3)))

        # 4) Konsole: Kontrolle
        print("\n===== PV-Forecast (kW) – nächste 24h (exaktes Stundenraster) =====")
        print("Zeit lokal | ts_ms | IRR (W/m²) | T_amb (°C) | P_PV (kW)")
        for local_str, ts_ms, irr, amb, pkw in preview:
            print(f"{local_str} | {ts_ms} | {irr:.0f} | {amb:.1f} | {pkw:.3f}")

        # 5) CSV schreiben
        write_csv(OUTPUT_CSV, preview)
        print(f"\nOK – CSV geschrieben: {OUTPUT_CSV}")

        # 6) VZ-Bereich löschen & schreiben
        print(f"Lösche vorhandene PV-Forecast-Werte auf {UUID_PV_OUT}: {start_ms} … {end_ms}")
        vz_delete_range(UUID_PV_OUT, start_ms, end_ms)

        print(f"Schreibe {len(preview)} Stundenpunkte (kW) nach Volkszähler (UUID {UUID_PV_OUT})…")
        written = 0
        for _local, ts_ms, _irr, _amb, pkw in preview:
            try:
                vz_write_point(UUID_PV_OUT, ts_ms, pkw)
                written += 1
            except Exception as e:
                print(f"Warnung: Schreiben @ ts_ms={ts_ms} fehlgeschlagen: {e}", file=sys.stderr)

        print(f"\nFertig – geschrieben: {written} Punkte auf {UUID_PV_OUT}.")
        if DRY_RUN:
            print("(DRY_RUN aktiv – es wurde nichts in die DB geschrieben.)")
        return 0

    except requests.RequestException as e:
        print(f"Netzwerkfehler: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
