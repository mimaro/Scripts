#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PV-Produktions-Forecast (48h) aus Volkszähler-IRR (W/m²) → kW nach Volkszähler schreiben

- Quelle (lesen):  UUID_P_IRR_FORECAST  (Globalstrahlung in W/m², Stundenende als ts_ms)
- Ziel  (schreiben):abcf6600-97c1-11f0-9348-db517d4efb8f  (PV-Forecast in kW)
- Bereich: nächste 48 Stunden ab nächster voller Stunde (Europe/Zurich)
- Vor dem Schreiben: vorhandene Werte im Bereich auf der Ziel-UUID löschen
- Konsole: je Stunde lokale Zeit, ts_ms, IRR (W/m²), optional T_amb (°C), P_PV (kW)

Umgebungsvariablen (optional):
  VZ_BASE_URL                (default: http://192.168.178.49/middleware.php)
  UUID_P_IRR_FORECAST        (default: 510567b0-990b-11f0-bb5b-d33e693aa264)
  UUID_T_OUTDOOR_FORECAST    (optional; wenn gesetzt, wird T_amb aus VZ gelesen)
  LOCAL_TZ                   (default: Europe/Zurich)
  LAT, LON                   (default: 47.3870, 8.2500 – Hägglingen)
  DRY_RUN=1                  → nur ausgeben, nichts löschen/schreiben
  DEBUG=1                    → Debug-Logs

Voraussetzung: pip install requests
"""

import os
import math
import sys
import json
import requests
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

# --------------------- CONFIG ---------------------
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")

UUID_P_IRR = os.environ.get(
    "UUID_P_IRR_FORECAST",
    "510567b0-990b-11f0-bb5b-d33e693aa264"  # <- Quelle: IRR W/m² (Forecast)
)
UUID_T_OUTDOOR = os.environ.get(
    "UUID_T_OUTDOOR_FORECAST", "c56767e0-97c1-11f0-96ab-41d2e85d0d5f"           # <- optional Quelle: T_amb °C (Forecast)
)
UUID_PV_OUT = os.environ.get(
    "UUID_PV_FORECAST_OUT",
    "abcf6600-97c1-11f0-9348-db517d4efb8f"  # <- Ziel: PV-Forecast in kW
)

LOCAL_TZ = os.environ.get("LOCAL_TZ", "Europe/Zurich")
LAT = float(os.environ.get("LAT", "47.3870"))
LON = float(os.environ.get("LON", "8.2500"))

USER_AGENT = "pv-forecast-from-vz/1.0"
TIMEOUT = 25
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"

# PV-Modell (einfach & robust; identisch zum bisherigen Ansatz)
CONFIG = {
    "noct_c": 45.0,               # Nominal Operating Cell Temp
    "temp_coeff_per_K": -0.004,   # Wirkungsgradänderung pro Kelvin
    "eta_stc": 0.17,              # Modulwirkungsgrad bei STC
    # Zwei Teildächer (Beispielwerte wie zuvor)
    "arrays": [
        {"name": "east", "tilt_deg": 20.0, "azimuth_deg": 90.0,  "area_m2": 58.8},
        {"name": "west", "tilt_deg": 20.0, "azimuth_deg": 270.0, "area_m2": 33.6},
    ],
}
# --------------------------------------------------

def _tz() -> timezone:
    return ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc

def _debug(msg: str) -> None:
    if os.environ.get("DEBUG"):
        print(f"[DEBUG] {msg}", file=sys.stderr)

# ---------- Zeitfenster: nächste 48h ab nächster voller Stunde ----------
def next_48h_window_ms() -> Tuple[int, int]:
    tz = _tz()
    now_local = datetime.now(tz)
    start_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    end_local = start_local + timedelta(hours=48)
    start_ms = int(start_local.astimezone(timezone.utc).timestamp() * 1000)
    end_ms   = int(end_local  .astimezone(timezone.utc).timestamp() * 1000)
    return start_ms, end_ms

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
    # sortieren & auf 48 Einträge begrenzen
    out.sort(key=lambda x: x[0])
    return out[:48]

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

# --------------------- Sonnenstand & Modell ---------------------
def solar_position(dt_local: datetime, lat_deg: float, lon_deg: float) -> Dict[str, float]:
    """
    Vereinfachte Sonnenstandsberechnung.
    Rückgabe: elevation_deg (α), azimuth_deg (0=N,90=E,180=S,270=W).
    """
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

    # Sonnenhöhe
    sin_alpha = math.sin(lat) * math.sin(decl) + math.cos(lat) * math.cos(decl) * math.cos(ha)
    sin_alpha = max(-1.0, min(1.0, sin_alpha))
    alpha = math.degrees(math.asin(sin_alpha))

    # Azimut (0=N -> 90=E -> 180=S -> 270=W)
    az = math.degrees(math.atan2(
        math.sin(ha),
        math.cos(ha) * math.sin(lat) - math.tan(decl) * math.cos(lat)
    ))
    az = (az + 180.0) % 360.0
    return {"elevation_deg": alpha, "azimuth_deg": az}

def plane_of_array_from_ghi(ghi_wm2: float, sun_elev_deg: float, sun_az_deg: float,
                            tilt_deg: float, panel_az_deg: float) -> float:
    """
    POA-Schätzung aus GHI:
      POA ≈ GHI * max(0, cos(θi)) / max(ε, sin(α)), begrenzt auf ≤ 1.6⋅GHI/sin(α)
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
    eta = eta_stc * (1.0 + temp_coeff_per_K * (t_mod_c - 25.0))
    eta = max(0.0, eta)
    p_w = poa_wm2 * area_m2 * eta
    return max(0.0, p_w) / 1000.0

# --------------------- Hauptlogik ---------------------
def main() -> int:
    try:
        # Zeitfenster bestimmen
        start_ms, end_ms = next_48h_window_ms()

        # IRR W/m² lesen
        irr_tuples = vz_get_tuples(UUID_P_IRR, start_ms, end_ms)
        if not irr_tuples:
            print("Keine IRR-Werte im gewünschten 48h-Fenster gefunden.", file=sys.stderr)
            return 2

        # Optional: T_amb lesen (wenn UUID vorhanden)
        t_map: Dict[int, float] = {}
        if UUID_T_OUTDOOR:
            try:
                t_tuples = vz_get_tuples(UUID_T_OUTDOOR, start_ms, end_ms)
                t_map = {ts: val for ts, val, _ in t_tuples}
            except Exception as e:
                print(f"Hinweis: Konnte T_amb nicht laden ({e}) – verwende Fallback 15.0 °C.")

        tz = _tz()
        preview: List[Tuple[str, int, float, Optional[float], float]] = []  # local_str, ts_ms, IRR, T_amb, P_kW

        # Berechnen
        for ts_ms, irr_wm2, _qual in irr_tuples:
            dt_utc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc)
            # Mittelpunktszeit für Sonnenstand
            dt_mid_local = (dt_utc - timedelta(minutes=30)).astimezone(tz)
            sun = solar_position(dt_mid_local, LAT, LON)

            # Ambient-Temp:
            amb_c = t_map.get(ts_ms, 15.0)  # 15°C Fallback
            # Leistung pro Array aufsummieren
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
            preview.append((local_str, ts_ms, float(irr_wm2), (amb_c if UUID_T_OUTDOOR else None), round(total_kw, 3)))

        # Konsole: Vorschau
        print("\n===== Vorschau: PV-Forecast (kW) – nächste 48h =====")
        hdr = "Zeit lokal | ts_ms | IRR (W/m²) | "
        hdr += ("T_amb (°C) | " if UUID_T_OUTDOOR else "")
        hdr += "P_PV (kW)"
        print(hdr)
        for row in preview:
            if UUID_T_OUTDOOR:
                local_str, ts_ms, irr, amb, pkw = row
                amb_s = f"{amb:.1f} °C" if amb is not None else "n/a"
                print(f"{local_str} | {ts_ms} | {irr:.0f} | {amb_s} | {pkw:.3f}")
            else:
                local_str, ts_ms, irr, _amb, pkw = row
                print(f"{local_str} | {ts_ms} | {irr:.0f} | {pkw:.3f}")

        # Zielbereich löschen
        print(f"\nLösche vorhandene PV-Forecast-Werte auf {UUID_PV_OUT}: {start_ms} … {preview[-1][1]}")
        vz_delete_range(UUID_PV_OUT, start_ms, preview[-1][1])

        # Schreiben
        print(f"Schreibe {len(preview)} Stundenpunkte (kW) nach Volkszähler…")
        written = 0
        for _, ts_ms, _irr, _amb, pkw in preview:
            try:
                vz_write_point(UUID_PV_OUT, ts_ms, pkw)
                written += 1
            except Exception as e:
                print(f"Warnung: Schreiben @ ts_ms={ts_ms} fehlgeschlagen: {e}", file=sys.stderr)

        print(f"\nFertig – geschrieben: P_PV_forecast={written} Punkte auf {UUID_PV_OUT}.")
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
