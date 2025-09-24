#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SRF Meteo API v2 – vergangene Stunde + aktuelle Stunde + nächste 48h (Hägglingen, PLZ 5607)

Sicherheitsfeatures:
- Keine Secrets im Code.
- Lädt SRG_CLIENT_ID und SRG_CLIENT_SECRET aus Env oder aus ~/.srg-meteo.env (600, Besitzer = aktueller User).
- Verweigert unsichere Env-Dateirechte.
- Forecast-Calls ohne Redirect-Folgen (allow_redirects=False).

Token-Aufruf:
- Token-URL inkl. grant_type als Query-Parameter, Basic-Auth mit base64(ClientId:ClientSecret).
- Token-Request ohne Body (nur Header), allow_redirects=True für Kompatibilität.

NEU:
- Zusätzlich wird die **vergangene Stunde** berücksichtigt:
  Fenster = [Ende der vergangenen Stunde, Ende der aktuellen Stunde + 48h]  → bis zu 50 Einträge.
- Zeitzone ist explizit **Europe/Zurich** (LOCAL-TZ Handling via zoneinfo).

Konsolenausgabe (neu/robust):
- Außentemperatur (TTT_C) und Globalstrahlung (IRRADIANCE_WM2, W/m²) der laufenden Stunde.
- IRRADIANCE_WM2 wird fallbacksicher und case-insensitiv gesucht.
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
    Falls nicht gesetzt: versucht ~/.srg-meteo.env.
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
        raise ApiError(f"Token-
