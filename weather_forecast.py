#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SRF Meteo 48h → Volkszähler
- Holt stündliche Forecasts (TTT_C, IRRADIANCE_WM2) für Hägglingen (PLZ 5607)
- Wählt genau die nächsten 48 Stunden ab der nächsten vollen Stunde (Europe/Zurich)
- Schreibt pro Stunde TTT_C in UUID_T_OUTDOOR und IRRADIANCE_WM2 in UUID_P_PV
- Nutzt Volkszähler-Middleware-API mit ts (ms seit 1970-01-01 UTC) und value

Konfiguration via Umgebungsvariablen (optional):
  SRG_CLIENT_ID, SRG_CLIENT_SECRET     OAuth für SRF Meteo
  SRF_ZIP=5607, SRF_PLACE="Hägglingen"
  LOCAL_TZ="Europe/Zurich"
  VZ_BASE_URL="http://<host>/middleware.php"
  UUID_T_OUTDOOR_FORECAST="<uuid>"
  UUID_P_PV_FORECAST="<uuid>"
  DRY_RUN=1  → nur ausgeben, nicht schreiben
  DEBUG=1    → zusätzliche Logausgaben
"""

import base64
import os
import stat
import sys
import json
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

# Standort / Zeitzone
ZIP = int(os.environ.get("SRF_ZIP", "5607"))
PLACE_NAME = os.environ.get("SRF_PLACE", "Hägglingen")
TZ = os.environ.get("LOCAL_TZ", "Europe/Zurich")

# Volkszähler
# Hinweis: Wenn dein Volkszähler anders erreichbar ist, passe VZ_BASE_URL an.
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")
UUID_T_OUTDOOR = os.environ.get("UUID_T_OUTDOOR_FORECAST", "c56767e0-97c1-11f0-96ab-41d2e85d0d5f")
UUID_P_PV = os.environ.get("UUID_P_PV_FORECAST", "abcf6600-97c1-11f0-9348-db517d4efb8f")

# Sonstiges
USER_AGENT = "srf-weather-vz/1.0"
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
TIMEOUT = 30  # Sekunden für HTTP-Requests

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
    """Liest KEY=VALUE aus path, erlaubt nur Modus 600 und Besitzer = aktueller User."""
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
    """
    Bevorzugt SRG_CLIENT_ID / SRG_CLIENT_SECRET aus Env.
    Falls nicht gesetzt: versucht ~/.srg-meteo.env (chmod 600).
    """
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
        msg = (
            "SRG_CLIENT_ID / SRG_CLIENT_SECRET nicht gefunden.\n"
            "Setze sie als Umgebungsvariablen ODER lege ~/.srg-meteo.env (chmod 600) an:\n"
            "  echo 'SRG_CLIENT_ID=…\\nSRG_CLIENT_SECRET=…' > ~/.srg-meteo.env && chmod 600 ~/.srg-meteo.env\n"
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    _debug(f"Nutze SRG_CLIENT_ID={mask(client_id)} / SRG_CLIENT_SECRET={mask(client_secret)}")
    return client_id, client_secret

def get_access_token(client_id: str, client_secret: str) -> str:
    """
    OAuth2 Client-Credentials:
      - grant_type als Query-Param
      - Basic Auth: base64(client_id:client_secret)
    """
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
    """Findet Geopunkt via PLZ; nimmt den mit Name==PLACE_NAME oder ersten Treffer."""
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
        _debug(f"Exakte Übereinstimmung '{name}' nicht gefunden – verwende: {best.get('name') or best.get('default_name')}")

    geo = best.get("geolocation") or {}
    lat = float(geo.get("lat"))
    lon = float(geo.get("lon"))
    geolocation_id = f"{lat:.4f},{lon:.4f}"  # API verlangt "[lat],[lon]"
    return lat, lon, geolocation_id

def get_hourly_forecast(token: str, geolocation_id: str) -> List[Dict[str, Any]]:
    res = api_get(f"/forecastpoint/{geolocation_id}", token)
    hours = res.get("hours") or res.get("data", {}).get("hours")
    if not isinstance(hours, list):
        raise ApiError(f"Unerwartetes Forecast-Format: {res}")
    return hours

def parse_dt(dt_str: str) -> datetime:
    """SRF 'date_time' (Ende der Stunde) → aware UTC datetime."""
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)

def select_next_48h(hours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Wählt genau die nächsten 48 Stunden (Ende der Stunde), beginnend ab Ende der laufenden Stunde (lokal).
    """
    tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
    now_local = datetime.now(tz)
    start_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    end_local = start_local + timedelta(hours=48)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)

    rows = []
    for r in hours:
        dt_str = r.get("date_time")
        if not dt_str:
            continue
        try:
            dt_utc = parse_dt(dt_str)
        except Exception:
            continue
        if start_utc <= dt_utc <= end_utc:
            rows.append((dt_utc, r))

    rows.sort(key=lambda t: t[0])
    if len(rows) > 48:
        rows = rows[:48]
    return [r for (_, r) in rows]

# -------------------------- Volkszähler ---------------------------------------
def vz_write(uuid: str, value: float, ts_ms: int) -> None:
    """
    Schreibt einen Wert in die Volkszähler-Middleware mit explizitem Timestamp (ms, UTC).
    """
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "add", "ts": str(ts_ms), "value": f"{float(value):.6f}"}
    if DRY_RUN:
        print(f"DRY_RUN: POST {url} params={params}")
        return
    r = requests.post(url, params=params, timeout=15)
    if not r.ok:
        raise RuntimeError(f"Volkszähler-POST fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

# ============================== MAIN ==========================================
def main() -> int:
    try:
        client_id, client_secret = get_credentials()
        token = get_access_token(client_id, client_secret)
        lat, lon, geo_id = find_geolocation_by_zip_and_name(token, ZIP, PLACE_NAME)
        hours = get_hourly_forecast(token, geo_id)
        next48 = select_next_48h(hours)

        if len(next48) == 0:
            print("Keine Forecastdaten für die nächsten 48 h gefunden.", file=sys.stderr)
            return 2

        print(f"Schreibe {len(next48)} Stunden (ab nächster voller Stunde, TZ={TZ}) nach Volkszähler…")
        count_T = count_I = 0

        for row in next48:
            # SRF date_time bezeichnet das STUNDENENDE
            dt_utc = parse_dt(row.get("date_time"))
            ts_ms = int(dt_utc.timestamp() * 1000)

            # Temperatur (°C)
            ttt = row.get("TTT_C")
            try:
                if ttt is not None:
                    t_val = float(str(ttt).replace(",", "."))
                    vz_write(UUID_T_OUTDOOR, t_val, ts_ms)
                    count_T += 1
            except Exception as e:
                print(f"Warnung: TTT_C für {dt_utc.isoformat()} konnte nicht geschrieben werden: {e}", file=sys.stderr)

            # Globalstrahlung (W/m²)
            irr = row.get("IRRADIANCE_WM2")
            try:
                if irr is not None:
                    i_val = float(str(irr).replace(",", "."))
                    vz_write(UUID_P_PV, i_val, ts_ms)
                    count_I += 1
            except Exception as e:
                print(f"Warnung: IRRADIANCE_WM2 für {dt_utc.isoformat()} konnte nicht geschrieben werden: {e}", file=sys.stderr)

        print(f"OK – geschrieben: T_outdoor_forecast={count_T} Werte, P_PV_forecast={count_I} Werte.")
        return 0

    except ApiError as e:
        print(f"API-Fehler: {e}", file=sys.stderr)
        return 1
    except requests.RequestException as e:
        print(f"Netzwerkfehler: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unerwarteter Fehler: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
