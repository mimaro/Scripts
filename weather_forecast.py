#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRF Meteo API v2 – aktuelle Stunde + nächste 48h (Hägglingen, PLZ 5607)

Sicherheitsfeatures:
- Keine Secrets im Code.
- Lädt SRG_CLIENT_ID und SRG_CLIENT_SECRET aus Env oder aus ~/.srg-meteo.env (600, Besitzer = aktueller User).
- Verweigert unsichere Env-Dateirechte.
- Forecast-Calls ohne Redirect-Folgen (allow_redirects=False).

Änderungen gem. Anleitung:
- Token-URL inkl. grant_type als Query-Parameter, Basic-Auth mit base64(ClientId:ClientSecret).
- Token-Request ohne Body (nur Header), allow_redirects=True für Kompatibilität.

NEU:
- Es wird zusätzlich die **aktuelle Stunde** berücksichtigt:
  Fenster = [Ende der aktuellen Stunde (nächste volle Stunde), +48h]  → bis zu 49 Einträge.
"""

import base64
import csv
import json
import os
import stat
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

import requests

API_BASE = "https://api.srgssr.ch/srf-meteo/v2"
# grant_type als Query-Parameter wie in der Anleitung
OAUTH_TOKEN_URL = "https://api.srgssr.ch/oauth/v1/accesstoken?grant_type=client_credentials"

OUTPUT_DIR = "/home/pi/Scripts"
JSON_OUT = os.path.join(OUTPUT_DIR, "haegglingen_5607_48h.json")
CSV_OUT  = os.path.join(OUTPUT_DIR, "haegglingen_5607_48h.csv")

ZIP = 5607
PLACE_NAME = "Hägglingen"
TZ = "Europe/Zurich"

CSV_COLUMNS = [
    "date_time","TTT_C","TTL_C","TTH_C","TTTFEEL_C","PROBPCP_PERCENT","RRR_MM",
    "RELHUM_PERCENT","DEWPOINT_C","FF_KMH","FX_KMH","DD_DEG","SUN_MIN",
    "FRESHSNOW_MM","FRESHSNOW_CM","PRESSURE_HPA","IRRADIANCE_WM2",
    "symbol_code","symbol24_code","cur_color",
]

class ApiError(RuntimeError):
    pass

def _debug(msg: str) -> None:
    if os.environ.get("DEBUG"):
        print(f"[SRF-API] {msg}", file=sys.stderr)

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
    Bevorzugt Umgebungsvariablen SRG_CLIENT_ID / SRG_CLIENT_SECRET.
    Falls nicht gesetzt: versucht ~/.srg-meteo.env (nur beim manuellen Start sinnvoll).
    Für systemd wird empfohlen, /etc/srf-meteo.env mit EnvironmentFile zu nutzen.
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
            '  echo \'SRG_CLIENT_ID=…\nSRG_CLIENT_SECRET=…\n\' > ~/.srg-meteo.env && chmod 600 ~/.srg-meteo.env\n\n'
            "Für systemd: /etc/srf-meteo.env (root-only) via EnvironmentFile= in der Unit."
        )
        print(msg, file=sys.stderr)
        sys.exit(2)

    _debug(f"Nutze SRG_CLIENT_ID={mask(client_id)} / SRG_CLIENT_SECRET={mask(client_secret)}")
    return client_id, client_secret

def get_access_token(client_id: str, client_secret: str) -> str:
    """
    OAuth2 Client-Credentials – exakt nach Anleitung:
    - grant_type als Query-Param in der URL
    - Authorization: Basic base64(ClientId:ClientSecret)
    - kein Body erforderlich
    """
    auth_raw = f"{client_id}:{client_secret}".encode("utf-8")
    auth_b64 = base64.b64encode(auth_raw).decode("ascii")
    headers = {
        "Authorization": f"Basic {auth_b64}",
        "Accept": "application/json",
        "User-Agent": "srf-weather-haegglingen/1.0",
        "Cache-Control": "no-cache",
    }
    _debug("Hole Access Token…")
    r = requests.post(OAUTH_TOKEN_URL, headers=headers, timeout=20, allow_redirects=True)
    if not r.ok:
        raise ApiError(f"Token-Request fehlgeschlagen: HTTP {r.status_code} – {r.text}")
    payload = r.json()
    token = (payload.get("access_token") or "").strip()
    if not token:
        raise ApiError(f"Kein gültiges access_token in Antwort: {r.text}")
    return token

def api_get(path: str, token: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "srf-weather-haegglingen/1.0",
    }
    r = requests.get(url, headers=headers, params=params or {}, timeout=30, allow_redirects=False)
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
        _debug(f"Exakte Übereinstimmung '{name}' nicht gefunden – verwende: {best.get('name') or best.get('default_name')}")

    geo = best.get("geolocation") or {}
    lat = float(geo.get("lat"))
    lon = float(geo.get("lon"))
    geolocation_id = f"{lat:.4f},{lon:.4f}"  # API erwartet <lat>,<lon> (4 Nachkommastellen)
    return lat, lon, geolocation_id

def get_hourly_forecast(token: str, geolocation_id: str) -> List[Dict[str, Any]]:
    res = api_get(f"/forecastpoint/{geolocation_id}", token)
    hours = res.get("hours") or res.get("data", {}).get("hours")
    if not isinstance(hours, list):
        raise ApiError(f"Unerwartetes Forecast-Format: {res}")
    return hours

def parse_dt(dt_str: str) -> datetime:
    """date_time (Ende der Stunde) -> aware UTC"""
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(TZ) if ZoneInfo else timezone.utc)
    return dt.astimezone(timezone.utc)

def filter_current_plus_48h(hours: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Liefert Einträge von **Ende der aktuellen Stunde** (nächste volle Stunde, lokal) bis +48h.
    Das umfasst die laufende Stunde **plus** die folgenden 48 Stunden → bis zu 49 Zeilen.
    """
    tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
    now_local = datetime.now(tz)
    current_hour_end_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    current_hour_end_utc = current_hour_end_local.astimezone(timezone.utc)
    window_end_utc = current_hour_end_utc + timedelta(hours=48)

    selected: List[Dict[str, Any]] = []
    for row in hours:
        dt_str = row.get("date_time")
        if not dt_str:
            continue
        try:
            dt_utc = parse_dt(dt_str)
        except Exception:
            _debug(f"Konnte date_time nicht parsen: {dt_str!r}")
            continue
        if current_hour_end_utc <= dt_utc <= window_end_utc:
            selected.append(row)

    selected.sort(key=lambda r: parse_dt(r["date_time"]))
    return selected

def write_json(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in CSV_COLUMNS})

def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)

def main() -> int:
    ensure_dir(OUTPUT_DIR)
    client_id, client_secret = get_credentials()

    try:
        token = get_access_token(client_id, client_secret)
        lat, lon, geo_id = find_geolocation_by_zip_and_name(token, ZIP, PLACE_NAME)
        _debug(f"Geopunkt: {PLACE_NAME} {ZIP} → lat={lat:.4f}, lon={lon:.4f} → geolocationId='{geo_id}'")
        hours = get_hourly_forecast(token, geo_id)

        # NEU: aktuelle Stunde + nächste 48h
        hours_cur_48 = filter_current_plus_48h(hours)

        payload = {
            "place": {"name": PLACE_NAME, "zip": ZIP, "geolocation_id": geo_id, "lat": round(lat, 4), "lon": round(lon, 4)},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "note": "Enthält die laufende Stunde (Ende = nächste volle Stunde) + die folgenden 48 Stunden.",
            "source": f"{API_BASE}/forecastpoint/{geo_id}",
            "count": len(hours_cur_48),
            "hours": hours_cur_48,
        }
        write_json(JSON_OUT, payload)
        write_csv(CSV_OUT, hours_cur_48)
        print(f"OK – gespeichert: {JSON_OUT} und {CSV_OUT} (Stunden: {len(hours_cur_48)})")
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
