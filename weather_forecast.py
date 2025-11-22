#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SRF Meteo 48h → Volkszähler (Vorschau, dann: Bereich löschen & neu schreiben)
+ Zusatz: 24h-Mittel TTT_C → WP-Strom (kWh) & Heizwärmebedarf (kWh)
+ Zusatz: stündlicher COP (48h) aus TTT_C
+ Zusatz: stündliche max. Aufnahmeleistung der WP (48h) aus TTT_C
+ NEU:    PV-Clip: min( PV-Prognose , PV-Max ) je Stunde (48h) → Ziel-UUID

NEU:
- Startzeitpunkt für VZ-Datenabfragen ist lokale Zeit Europe/Zurich (DST-fest).
- Skalierungen:
  • UUID_HP_MAX_POWER         (kW → W, ×1000)
  • UUID_HEAT_DEMAND_KWH      (kWh → Wh, ×1000)
  • UUID_WP_POWER_KWH         (kWh → Wh, ×1000)
  • UUID_PV_CAPPED_FORECAST_OUT: KEINE zusätzliche Skalierung (W bleibt W)
"""

import base64
import json
import os
import stat
import sys
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

import requests

# ============================== CONFIG ========================================
API_BASE = "https://api.srgssr.ch/srf-meteo/v2"
OAUTH_TOKEN_URL = "https://api.srgssr.ch/oauth/v1/accesstoken?grant_type=client_credentials"

ZIP = int(os.environ.get("SRF_ZIP", "5607"))
PLACE_NAME = os.environ.get("SRF_PLACE", "Hägglingen")
TZ = os.environ.get("LOCAL_TZ", "Europe/Zurich")

# Volkszähler
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")
UUID_T_OUTDOOR = os.environ.get("UUID_T_OUTDOOR_FORECAST", "c56767e0-97c1-11f0-96ab-41d2e85d0d5f")
UUID_P_IRR     = os.environ.get("UUID_P_IRR_FORECAST",     "510567b0-990b-11f0-bb5b-d33e693aa264")

# Zusätzliche Kennzahlen (Ziele)
UUID_WP_POWER_KWH    = os.environ.get("UUID_WP_POWER_KWH",    "58cbc600-9aaa-11f0-8a74-894e01bd6bb7")  # kWh → schreiben als Wh (×1000)
UUID_HEAT_DEMAND_KWH = os.environ.get("UUID_HEAT_DEMAND_KWH", "9d6f6990-9aac-11f0-8991-c9bc212463c9")  # kWh → schreiben als Wh (×1000)
UUID_COP_FORECAST    = os.environ.get("UUID_COP_FORECAST",    "31877e20-9aaa-11f0-8759-733431a03535")  # dimensionslos
UUID_HP_MAX_POWER    = os.environ.get("UUID_HP_MAX_POWER",    "46e21920-9ab9-11f0-9359-d3451ca32acb")  # kW → schreiben als W (×1000)

# PV-Clip: Eingänge (in W lesen) & Ziel (W schreiben, keine Skalierung)
UUID_PV_PROD_FORECAST_IN    = os.environ.get("UUID_PV_PROD_FORECAST_IN",
                                             "abcf6600-97c1-11f0-9348-db517d4efb8f")  # PV Prognose (W)
UUID_PV_MAX_FORECAST_IN     = os.environ.get("UUID_PV_MAX_FORECAST_IN",
                                             "46e21920-9ab9-11f0-9359-d3451ca32acb")  # PV Max (W)
UUID_PV_CAPPED_FORECAST_OUT = os.environ.get("UUID_PV_CAPPED_FORECAST_OUT",
                                             "2ef42c20-9abb-11f0-9cfd-ad07953daec6")  # schreiben in W (unverändert)

# Mittelwert-Fenster & Formeln
AVG_TEMP_HOURS = int(os.environ.get("AVG_TEMP_HOURS", "24"))
TEMP_CAP_MAX_C = float(os.environ.get("TEMP_CAP_MAX_C", "15.0"))

#Funktion Prognose Strombedarf WP
FORM_HP_A = float(os.environ.get("FORM_HP_A", "0.0474"))
FORM_HP_B = float(os.environ.get("FORM_HP_B", "-1.6072"))
FORM_HP_C = float(os.environ.get("FORM_HP_C", "15.326"))

#Funktion Prognose Wärmebedarf
FORM_Q_A  = float(os.environ.get("FORM_Q_A",  "0.0762"))
FORM_Q_B  = float(os.environ.get("FORM_Q_B",  "-4.0294"))
FORM_Q_C  = float(os.environ.get("FORM_Q_C",  "54.037"))

#Funktion Prognose COP
FORM_COP_M = float(os.environ.get("FORM_COP_M", "0.1986"))
FORM_COP_B = float(os.environ.get("FORM_COP_B", "3.8"))

#Funktion Prognose WP-Aufnahmeleistung
FORM_HP_MAX_M = float(os.environ.get("FORM_HP_MAX_M", "-0.06"))
FORM_HP_MAX_B = float(os.environ.get("FORM_HP_MAX_B", "1.3"))

USER_AGENT = "srf-weather-vz/2.0"
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
TIMEOUT = 30  # Sekunden

# ===== Skalierungsfaktoren =====
SCALE_HP_MAX_kW_TO_W   = 1000.0   # für UUID_HP_MAX_POWER
SCALE_ENERGY_kWh_TO_Wh = 1000.0   # für UUID_WP_POWER_KWH & UUID_HEAT_DEMAND_KWH
# Für PV-Clip KEINE Skalierung mehr (W → W)
# SCALE_PV_CLIP = 1.0

# ============================== UTILS =========================================
class ApiError(RuntimeError):
    pass

def _debug(msg: str) -> None:
    if os.environ.get("DEBUG"):
        print(f"[DEBUG] {msg}", file=sys.stderr)

def mask(s: str) -> str:
    if not s:
        return ""
    return (s[:2] + "…" + s[-2:]) if len(s) > 6 else "…" * len(s)

def load_env_file_secure(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path):
        return env
    st = os.stat(path)
    mode = stat.S_IMODE(st.st_mode)
    if mode != 0o600 or st.st_uid != os.getuid():
        raise ApiError(
            f"Unsichere Env-Datei {path}: erwartet chmod 600 und Besitzer UID={os.getuid()}."
        )
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_credentials() -> Tuple[str, str]:
    client_id = (os.environ.get("SRG_CLIENT_ID") or "").strip().strip('"').strip("'")
    client_secret = (os.environ.get("SRG_CLIENT_SECRET") or "").strip().strip('"').strip("'")
    if not client_id or not client_secret:
        home_env_path = os.path.expanduser("~/.srg-meteo.env")
        try:
            env = load_env_file_secure(home_env_path)
            if not client_id:
                client_id = (env.get("SRG_CLIENT_ID") or "").strip().strip('"').strip("'")
            if not client_secret:
                client_secret = (env.get("SRG_CLIENT_SECRET") or "").strip().strip('"').strip("'")
        except ApiError as e:
            print(str(e), file=sys.stderr)
            sys.exit(2)
    if not client_id or not client_secret:
        print("SRG_CLIENT_ID / SRG_CLIENT_SECRET fehlen.", file=sys.stderr)
        sys.exit(2)
    _debug(f"Creds: {mask(client_id)} / {mask(client_secret)}")
    return client_id, client_secret

def get_access_token(client_id: str, client_secret: str) -> str:
    auth_raw = f"{client_id}:{client_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
        "Cache-Control": "no-cache",
    }
    r = requests.post(OAUTH_TOKEN_URL, headers=headers, timeout=TIMEOUT, allow_redirects=True)
    if not r.ok:
        raise ApiError(f"Token-Request fehlgeschlagen: HTTP {r.status_code} – {r.text}")
    token = (r.json().get("access_token") or "").strip()
    if not token:
        raise ApiError(f"Kein gültiges access_token in Antwort: {r.text}")
    return token

def api_get(path: str, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": USER_AGENT,
    }
    r = requests.get(url, headers=headers, params=params or {}, timeout=TIMEOUT, allow_redirects=False)
    if not r.ok:
        raise ApiError(f"GET {url} fehlgeschlagen: HTTP {r.status_code} – {r.text}")
    return r.json()

def find_geolocation_by_zip_and_name(token: str, zip_code: int, name: str) -> Tuple[float, float, str]:
    res = api_get("/geolocationNames", token, params={"zip": zip_code, "limit": 20})
    items: List[Dict[str, Any]] = []
    if isinstance(res, list):
        items = res
    elif isinstance(res, dict):
        for key in ("items", "data", "results"):
            if key in res and isinstance(res[key], list):
                items = res[key]
                break
        if not items and "geolocation" in res:
            items = [res]
    if not items:
        raise ApiError(f"Keine geolocationNames für PLZ {zip_code} gefunden: {res}")
    best = None
    for it in items:
        nm = (it.get("name") or it.get("default_name") or "").strip().lower()
        if nm == name.lower():
            best = it
            break
    if best is None:
        best = items[0]
    geo = best.get("geolocation") or {}
    lat = float(geo.get("lat"))
    lon = float(geo.get("lon"))
    geolocation_id = f"{lat:.4f},{lon:.4f}"
    return lat, lon, geolocation_id

def get_hourly_forecast(token: str, geolocation_id: str) -> List[Dict[str, Any]]:
    res = api_get(f"/forecastpoint/{geolocation_id}", token)
    hours = res.get("hours") or res.get("data", {}).get("hours")
    if not isinstance(hours, list):
        raise ApiError(f"Unerwartetes Forecast-Format: {res}")
    return hours

def parse_dt(dt_str: str) -> datetime:
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)

def select_next_48h(hours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    tzloc = ZoneInfo(TZ) if ZoneInfo else timezone.utc
    now_local = datetime.now(tzloc)
    start_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    end_local = start_local + timedelta(hours=48)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    rows: List[Tuple[datetime, Dict[str, Any]]] = []
    for r in hours:
        ds = r.get("date_time")
        if not ds:
            continue
        try:
            dt_utc = parse_dt(ds)
        except Exception:
            continue
        if start_utc <= dt_utc <= end_utc:
            rows.append((dt_utc, r))
    rows.sort(key=lambda t: t[0])
    rows = rows[:48] if len(rows) > 48 else rows
    return [r for (_, r) in rows]

# -------------------------- Volkszähler I/O -----------------------------------
def vz_delete_range(uuid: str, from_ts_ms: int, to_ts_ms: int) -> None:
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "delete", "from": str(from_ts_ms), "to": str(to_ts_ms)}
    if DRY_RUN:
        print(f"DRY_RUN: DELETE-Range GET {url} params={params}")
        return
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"Volkszähler-DELETE fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

def vz_write(uuid: str, value: float, ts_ms: int) -> None:
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "add", "ts": str(ts_ms), "value": f"{float(value):.6f}"}
    if DRY_RUN:
        print(f"DRY_RUN: POST {url} params={params}")
        return
    r = requests.post(url, params=params, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"Volkszähler-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

def vz_get_tuples(uuid: str, from_ms: int, to_ms: int) -> List[Tuple[int, float, int]]:
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"from": str(from_ms), "to": str(to_ms)}
    r = requests.get(url, params=params, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    r.raise_for_status()
    data = r.json().get("data", {})
    tuples = data.get("tuples") or []
    out: List[Tuple[int, float, int]] = []
    for t in tuples:
        try:
            ts = int(t[0]); val = float(t[1]); qual = int(t[2]) if len(t) > 2 else 1
            out.append((ts, val, qual))
        except Exception:
            continue
    out.sort(key=lambda x: x[0])
    return out

# ============================== FORMEL-FUNKTIONEN ==============================
def wp_power_kwh_from_t(t_c: float) -> float:
    t_eff = min(t_c, TEMP_CAP_MAX_C)
    return FORM_HP_A * t_eff * t_eff + FORM_HP_B * t_eff + FORM_HP_C

def heat_demand_kwh_from_t(t_c: float) -> float:
    t_eff = min(t_c, TEMP_CAP_MAX_C)
    return FORM_Q_A * t_eff * t_eff + FORM_Q_B * t_eff + FORM_Q_C

def cop_from_t(t_c: float) -> float:
    return FORM_COP_M * t_c + FORM_COP_B

def hp_max_power_kw_from_t(t_c: float) -> float:
    return max(0.0, FORM_HP_MAX_M * t_c + FORM_HP_MAX_B)

# ============================== NEU: Zeit-Helfer (DST-sicher) =================
def now_local_dt() -> datetime:
    """Aktuelle lokale Zeit (Europe/Zurich), inkl. Sommer-/Winterzeit."""
    return datetime.now(ZoneInfo(TZ) if ZoneInfo else timezone.utc)

def local_now_ms_utc() -> int:
    """Aktueller lokaler Zeitpunkt → UTC-ms."""
    return int(now_local_dt().astimezone(timezone.utc).timestamp() * 1000)

# ============== PV-Clip-Funktion: min(PV_Prod, PV_Max) je Stunde schreiben ====
def pv_clip_and_write(ts_grid: List[int], from_ms_localnow: int, to_ms: int, tz_loc) -> None:
    """
    - Liest PV-Prod (W) und PV-Max (W) aus VZ für [from_ms_localnow, to_ms]
    - Ermittelt je ts in ts_grid das Minimum (W)
    - Löscht Zielbereich und schreibt 48 Punkte **ohne zusätzliche Skalierung** (W)
    """
    print("\n===== PV-Clip: min( PV-Prognose, PV-Max ) – stündlich, nächste 48h =====")

    # Daten laden (Inputs in W)
    prod = vz_get_tuples(UUID_PV_PROD_FORECAST_IN, from_ms_localnow, to_ms)
    vmax = vz_get_tuples(UUID_PV_MAX_FORECAST_IN,  from_ms_localnow, to_ms)
    prod_map = {ts: v for ts, v, _ in prod}
    vmax_map = {ts: v for ts, v, _ in vmax}

    # Zielbereich löschen
    print(f"Lösche Zielbereich {from_ms_localnow} … {to_ms} (UUID {UUID_PV_CAPPED_FORECAST_OUT})")
    try:
        vz_delete_range(UUID_PV_CAPPED_FORECAST_OUT, from_ms_localnow, to_ms)
    except Exception as e:
        print(f"Warnung: PV-Clip DELETE fehlgeschlagen: {e}", file=sys.stderr)

    print("Zeit lokal | ts_ms | PV_Prod_W | PV_Max_W | min_W | geschrieben (W)")
    written = 0
    for ts in ts_grid:
        dt_local = datetime.fromtimestamp(ts/1000.0, tz=timezone.utc).astimezone(tz_loc)
        local_str = dt_local.strftime("%Y-%m-%d %H:%M %Z")
        p = prod_map.get(ts); m = vmax_map.get(ts)

        if p is None or m is None:
            p_str = "n/a" if p is None else f"{p:.1f}"
            m_str = "n/a" if m is None else f"{m:.1f}"
            print(f"{local_str} | {ts} | {p_str} | {m_str} | n/a | n/a")
            continue

        v_w = min(float(p), float(m))   # W
        v_write = v_w                   # W (keine ×1000 mehr)
        print(f"{local_str} | {ts} | {p:.1f} | {m:.1f} | {v_w:.1f} | {v_write:.1f}")
        try:
            vz_write(UUID_PV_CAPPED_FORECAST_OUT, v_write, ts)
            written += 1
        except Exception as e:
            print(f"Warnung: Schreiben @ ts_ms={ts} fehlgeschlagen: {e}", file=sys.stderr)

    print(f"\nFertig – PV-Clip geschrieben: {written}/{len(ts_grid)} Punkte → {UUID_PV_CAPPED_FORECAST_OUT} (W).")

# ============================== MAIN ==========================================
def main() -> int:
    try:
        client_id, client_secret = get_credentials()
        token = get_access_token(client_id, client_secret)
        lat, lon, geo_id = find_geolocation_by_zip_and_name(token, ZIP, PLACE_NAME)
        hours = get_hourly_forecast(token, geo_id)
        next48 = select_next_48h(hours)
        if not next48:
            print("Keine Forecastdaten für die nächsten 48 h gefunden.", file=sys.stderr)
            return 2

        # Vorschau-Daten (Temperatur / IRR)
        tz_loc = ZoneInfo(TZ) if ZoneInfo else timezone.utc
        preview_T: List[Tuple[str, int, Optional[float]]] = []
        preview_I: List[Tuple[str, int, Optional[float]]] = []

        for row in next48:
            dt_utc = parse_dt(row.get("date_time"))
            ts_ms = int(dt_utc.timestamp() * 1000)
            dt_local = dt_utc.astimezone(tz_loc)
            local_str = dt_local.strftime("%Y-%m-%d %H:%M %Z")

            t_val = None
            i_val = None
            t_raw = row.get("TTT_C"); i_raw = row.get("IRRADIANCE_WM2")
            try:
                if t_raw is not None: t_val = float(str(t_raw).replace(",", "."))
            except Exception: t_val = None
            try:
                if i_raw is not None: i_val = float(str(i_raw).replace(",", "."))
            except Exception: i_val = None

            preview_T.append((local_str, ts_ms, t_val))
            preview_I.append((local_str, ts_ms, i_val))

        # Konsole
        print("\n===== Vorschau: Temperatur (TTT_C) – nächste 48h =====")
        for local_str, ts_ms, val in preview_T:
            vs = "n/a" if val is None else f"{val:.2f} °C"
            print(f"{local_str} | ts_ms={ts_ms} | TTT_C={vs}")

        print("\n===== Vorschau: Einstrahlung (IRRADIANCE_WM2) – nächste 48h =====")
        for local_str, ts_ms, val in preview_I:
            vs = "n/a" if val is None else f"{val:.0f} W/m²"
            print(f"{local_str} | ts_ms={ts_ms} | IRRADIANCE_WM2={vs}")

        # Bereich (inklusive)
        ts_grid = [ts for (_loc, ts, _v) in preview_T]
        start_ts_ms = ts_grid[0]
        end_ts_ms   = ts_grid[-1]

        # TTT_C / IRR in VZ schreiben
        print(f"\nLösche vorhandene Daten in Volkszähler: {start_ts_ms} … {end_ts_ms} (TTT_C & IRR)")
        vz_delete_range(UUID_T_OUTDOOR, start_ts_ms, end_ts_ms)
        vz_delete_range(UUID_P_IRR,     start_ts_ms, end_ts_ms)

        print(f"Schreibe {len(ts_grid)} Stunden (ab nächster voller Stunde, TZ={TZ}) nach Volkszähler…")
        count_T = count_I = 0
        for (_, ts_ms, t_val), (_, _, i_val) in zip(preview_T, preview_I):
            if t_val is not None:
                try:
                    vz_write(UUID_T_OUTDOOR, float(t_val), ts_ms); count_T += 1
                except Exception as e:
                    print(f"Warnung: TTT_C @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)
            if i_val is not None:
                try:
                    vz_write(UUID_P_IRR, float(i_val), ts_ms); count_I += 1
                except Exception as e:
                    print(f"Warnung: IRRADIANCE_WM2 @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)
        print(f"\nFertig – geschrieben: T_outdoor_forecast={count_T}, P_IRR_forecast={count_I}.")
        if DRY_RUN:
            print("(DRY_RUN aktiv – es wurde nichts in die DB geschrieben.)")

        # 24h-Mittel / Kennzahlen
        temps = [v for (_, _, v) in preview_T[:AVG_TEMP_HOURS] if v is not None]
        if temps:
            t_mean = sum(temps) / len(temps)
            t_eff = min(t_mean, TEMP_CAP_MAX_C)
            wp_kwh = wp_power_kwh_from_t(t_mean)       # kWh
            q_kwh  = heat_demand_kwh_from_t(t_mean)    # kWh
            ts_now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

            wp_wh = wp_kwh * SCALE_ENERGY_kWh_TO_Wh    # schreiben als Wh
            q_wh  = q_kwh  * SCALE_ENERGY_kWh_TO_Wh    # schreiben als Wh

            print("\n===== 24h-Mittel & abgeleitete Kennzahlen =====")
            print(f"Fenster    : nächste {len(temps)} h")
            print(f"T_mean     : {t_mean:.2f} °C (Deckel {TEMP_CAP_MAX_C:.1f} °C → {t_eff:.2f} °C)")
            print(f"WP-Strom   : {wp_kwh:.3f} kWh → write {wp_wh:.1f} Wh (UUID {UUID_WP_POWER_KWH}) @ ts_ms={ts_now_ms}")
            print(f"Heizwärme  : {q_kwh:.3f} kWh → write {q_wh:.1f} Wh (UUID {UUID_HEAT_DEMAND_KWH}) @ ts_ms={ts_now_ms}")

            try: vz_write(UUID_WP_POWER_KWH, float(wp_wh), ts_now_ms)
            except Exception as e: print(f"Warnung: WP-Strom (Wh) nicht geschrieben: {e}", file=sys.stderr)
            try: vz_write(UUID_HEAT_DEMAND_KWH, float(q_wh), ts_now_ms)
            except Exception as e: print(f"Warnung: Heizwärme (Wh) nicht geschrieben: {e}", file=sys.stderr)
        else:
            print("Keine Temperaturwerte für die Mittelwertbildung gefunden.", file=sys.stderr)

        # COP (48h) – dimensionslos
        print("\n===== COP-Forecast (stündlich, nächste 48h) =====")
        print(f"Lösche COP-Bereich: {start_ts_ms} … {end_ts_ms} (UUID {UUID_COP_FORECAST})")
        try: vz_delete_range(UUID_COP_FORECAST, start_ts_ms, end_ts_ms)
        except Exception as e: print(f"Warnung: COP-DELETE fehlgeschlagen: {e}", file=sys.stderr)
        count_COP = 0
        for (local_str, ts_ms, t_val) in preview_T:
            if t_val is None:
                print(f"{local_str} | ts_ms={ts_ms} | COP=n/a (kein T)"); continue
            cop = cop_from_t(t_val)
            print(f"{local_str} | ts_ms={ts_ms} | COP={cop:.3f}")
            try: vz_write(UUID_COP_FORECAST, float(cop), ts_ms); count_COP += 1
            except Exception as e: print(f"Warnung: COP @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)
        print(f"\nFertig – COP geschrieben: {count_COP}/{len(preview_T)} Punkte.")

        # WP max Aufnahmeleistung (48h) – kW → schreiben als W
        print("\n===== Max. Aufnahmeleistung WP – stündlich, nächste 48h =====")
        print(f"Lösche Bereich: {start_ts_ms} … {end_ts_ms} (UUID {UUID_HP_MAX_POWER})")
        try: vz_delete_range(UUID_HP_MAX_POWER, start_ts_ms, end_ts_ms)
        except Exception as e: print(f"Warnung: HP_MAX-DELETE fehlgeschlagen: {e}", file=sys.stderr)
        count_HP_MAX = 0
        for (local_str, ts_ms, t_val) in preview_T:
            if t_val is None:
                print(f"{local_str} | ts_ms={ts_ms} | Pmax=n/a (kein T)"); continue
            pmax_kw = hp_max_power_kw_from_t(t_val)            # kW
            pmax_w  = pmax_kw * SCALE_HP_MAX_kW_TO_W           # W
            print(f"{local_str} | ts_ms={ts_ms} | T={t_val:.2f} °C | Pmax={pmax_kw:.3f} kW → write {pmax_w:.1f} W")
            try: vz_write(UUID_HP_MAX_POWER, float(pmax_w), ts_ms); count_HP_MAX += 1
            except Exception as e: print(f"Warnung: Pmax @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)
        print(f"\nFertig – Pmax geschrieben: {count_HP_MAX}/{len(preview_T)} Punkte (W).")

        # PV-CLIP: Startzeitpunkt der Abfrage = lokale Jetztzeit (DST-fest)
        from_ms_localnow = local_now_ms_utc()
        pv_clip_and_write(ts_grid, from_ms_localnow, end_ts_ms, tz_loc)

        return 0

    except ApiError as e:
        print(f"API-Fehler: {e}", file=sys.stderr); return 1
    except requests.RequestException as e:
        print(f"Netzwerkfehler: {e}", file=sys.stderr); return 1
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr); return 1

if __name__ == "__main__":
    raise SystemExit(main())
