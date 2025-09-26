#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SRF Meteo 48h → Volkszähler
- Holt stündliche Forecasts (TTT_C, IRRADIANCE_WM2) für Hägglingen (PLZ 5607)
- Wählt die nächsten 48 Stunden ab nächster voller Stunde (Europe/Zurich)
- Schreibt pro Stunde:
    TTT_C → UUID_T_OUTDOOR
    IRRADIANCE_WM2 → UUID_P_PV
- Zeitstempel: ms seit 1970-01-01 UTC (SRF date_time = Ende der Stunde)

Konfiguration via Env:
  SRG_CLIENT_ID / SRG_CLIENT_SECRET    OAuth für SRF Meteo
  SRF_ZIP=5607, SRF_PLACE="Hägglingen", LOCAL_TZ="Europe/Zurich"
  VZ_BASE_URL="http://<host>/middleware.php"
  UUID_T_OUTDOOR_FORECAST, UUID_P_PV_FORECAST
  DRY_RUN=1        → nur ausgeben
  VZ_OVERWRITE=1   → 48h-Bereich pro Kanal vorher löschen (sonst: skipduplicates)
  DEBUG=1          → Debug-Logs

API-Referenzen:
- Daten schreiben (add): /middleware/data/<uuid>.json?ts=<ms>&value=<num>  (POST oder GET)  【Doku】
- Daten löschen (delete): …?operation=delete&from=<ms>&to=<ms>            【Doku】
- options=skipduplicates: Fehler beim Hinzufügen (insb. Duplikate) ignorieren【Doku】
"""

import base64, os, stat, sys, json, requests
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None

API_BASE = "https://api.srgssr.ch/srf-meteo/v2"
OAUTH_TOKEN_URL = "https://api.srgssr.ch/oauth/v1/accesstoken?grant_type=client_credentials"

ZIP = int(os.environ.get("SRF_ZIP", "5607"))
PLACE_NAME = os.environ.get("SRF_PLACE", "Hägglingen")
TZ = os.environ.get("LOCAL_TZ", "Europe/Zurich")

VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")
UUID_T_OUTDOOR = os.environ.get("UUID_T_OUTDOOR_FORECAST", "c56767e0-97c1-11f0-96ab-41d2e85d0d5f")
UUID_P_PV      = os.environ.get("UUID_P_PV_FORECAST",      "abcf6600-97c1-11f0-9348-db517d4efb8f")

USER_AGENT = "srf-weather-vz/1.1"
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
OVERWRITE = os.environ.get("VZ_OVERWRITE", "0") == "1"
TIMEOUT = 30

class ApiError(RuntimeError):
    pass

def _debug(msg: str) -> None:
    if os.environ.get("DEBUG"):
        print(f"[DEBUG] {msg}", file=sys.stderr)

def mask(s: str) -> str:
    if not s: return ""
    return (s[:2] + "…" + s[-2:]) if len(s) > 6 else "…" * len(s)

def load_env_file_secure(path: str) -> Dict[str, str]:
    env: Dict[str, str] = {}
    if not os.path.exists(path): return env
    st = os.stat(path); mode = stat.S_IMODE(st.st_mode)
    if mode != 0o600 or st.st_uid != os.getuid():
        raise ApiError(f"Unsichere Env-Datei {path}: erwartet chmod 600 und Besitzer UID={os.getuid()}.")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line=line.strip()
            if not line or line.startswith("#") or "=" not in line: continue
            k,v = line.split("=",1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env

def get_credentials() -> Tuple[str,str]:
    cid = (os.environ.get("SRG_CLIENT_ID") or "").strip().strip('"').strip("'")
    csec= (os.environ.get("SRG_CLIENT_SECRET") or "").strip().strip('"').strip("'")
    if not cid or not csec:
        home = os.path.expanduser("~/.srg-meteo.env")
        env = load_env_file_secure(home)
        if not cid:  cid  = (env.get("SRG_CLIENT_ID") or "").strip().strip('"').strip("'")
        if not csec: csec = (env.get("SRG_CLIENT_SECRET") or "").strip().strip('"').strip("'")
    if not cid or not csec:
        print("SRG_CLIENT_ID / SRG_CLIENT_SECRET fehlen (Env oder ~/.srg-meteo.env mit chmod 600).", file=sys.stderr)
        sys.exit(2)
    _debug(f"Creds: {mask(cid)} / {mask(csec)}")
    return cid, csec

def get_access_token(cid: str, csec: str) -> str:
    hdr = {"Authorization": "Basic " + base64.b64encode(f"{cid}:{csec}".encode()).decode("ascii"),
           "Accept":"application/json", "User-Agent": USER_AGENT, "Cache-Control":"no-cache"}
    r = requests.post(OAUTH_TOKEN_URL, headers=hdr, timeout=TIMEOUT, allow_redirects=True)
    if not r.ok: raise ApiError(f"Token-Request fehlgeschlagen: HTTP {r.status_code} – {r.text}")
    tok = (r.json().get("access_token") or "").strip()
    if not tok: raise ApiError(f"Kein access_token in Antwort: {r.text}")
    return tok

def api_get(path: str, token: str, params: Optional[Dict[str,Any]]=None) -> Dict[str,Any]:
    url = f"{API_BASE}{path}"
    hdr = {"Authorization": f"Bearer {token}", "Accept":"application/json", "User-Agent": USER_AGENT}
    r = requests.get(url, headers=hdr, params=params or {}, timeout=TIMEOUT, allow_redirects=False)
    if not r.ok: raise ApiError(f"GET {url} fehlgeschlagen: HTTP {r.status_code} – {r.text}")
    return r.json()

def find_geolocation_by_zip_and_name(token: str, zip_code: int, name: str) -> Tuple[float,float,str]:
    res = api_get("/geolocationNames", token, params={"zip": zip_code, "limit": 20})
    items = res if isinstance(res, list) else res.get("items") or res.get("data") or []
    if not items: raise ApiError(f"Keine geolocationNames für PLZ {zip_code} gefunden: {res}")
    best = next((it for it in items if (it.get("name") or it.get("default_name") or "").strip().lower()==name.lower()), items[0])
    geo = best.get("geolocation") or {}
    lat=float(geo.get("lat")); lon=float(geo.get("lon"))
    return lat, lon, f"{lat:.4f},{lon:.4f}"

def get_hourly_forecast(token: str, geolocation_id: str) -> List[Dict[str,Any]]:
    res = api_get(f"/forecastpoint/{geolocation_id}", token)
    hours = res.get("hours") or res.get("data",{}).get("hours")
    if not isinstance(hours, list): raise ApiError(f"Unerwartetes Forecast-Format: {res}")
    return hours

def parse_dt(dt_str: str) -> datetime:
    if dt_str.endswith("Z"):
        return datetime.fromisoformat(dt_str.replace("Z","+00:00")).astimezone(timezone.utc)
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
        dt = dt.replace(tzinfo=tz)
    return dt.astimezone(timezone.utc)

def select_next_48h(hours: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
    now_local = datetime.now(tz)
    start_local = (now_local.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))
    end_local   = start_local + timedelta(hours=48)
    start_utc = start_local.astimezone(timezone.utc)
    end_utc   = end_local.astimezone(timezone.utc)
    rows=[]
    for r in hours:
        ds=r.get("date_time"); if not ds: continue
        try: dt_utc = parse_dt(ds)
        except Exception: continue
        if start_utc <= dt_utc <= end_utc: rows.append((dt_utc,r))
    rows.sort(key=lambda t:t[0])
    return [r for _,r in rows[:48]]

# ------------------- Volkszähler helpers --------------------------------------

def vz_write(uuid: str, value: float,_
