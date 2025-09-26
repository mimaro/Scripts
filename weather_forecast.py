#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SRF Meteo 48h → Volkszähler (Vorschau, dann: Bereich löschen & neu schreiben)

- Holt stündliche Forecasts (TTT_C, IRRADIANCE_WM2) für Hägglingen (PLZ 5607)
- Auswahl: genau die nächsten 48 Stunden ab Ende der laufenden Stunde (Europe/Zurich)
- Konsole: getrennte Vorschau-Listen (Temperatur / Einstrahlung) mit lokaler Zeit + ts_ms
- Volkszähler: löscht 48h-Bereich (beide Kanäle) und schreibt dann neu
- Zeitstempel beim Schreiben: Millisekunden seit 1970-01-01 00:00:00 **UTC**

Umgebungsvariablen (optional):
  SRG_CLIENT_ID / SRG_CLIENT_SECRET   OAuth für SRF Meteo
  SRF_ZIP=5607, SRF_PLACE="Hägglingen", LOCAL_TZ="Europe/Zurich"
  VZ_BASE_URL="http://<host>/middleware.php"   # ggf. /middleware statt /middleware.php
  UUID_T_OUTDOOR_FORECAST, UUID_P_PV_FORECAST
  DRY_RUN=1  → nur ausgeben, nichts schreiben
  DEBUG=1    → Debug-Logs

Voraussetzung: requests (pip install requests)
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

# Volkszähler (deine Defaults; bei Bedarf via Env überschreiben)
VZ_BASE_URL = os.environ.get("VZ_BASE_URL", "http://192.168.178.49/middleware.php")
UUID_T_OUTDOOR = os.environ.get("UUID_T_OUTDOOR_FORECAST", "c56767e0-97c1-11f0-96ab-41d2e85d0d5f")
UUID_P_PV      = os.environ.get("UUID_P_PV_FORECAST",      "510567b0-990b-11f0-bb5b-d33e693aa264")

	

USER_AGENT = "srf-weather-vz/1.4"
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
TIMEOUT = 30  # Sekunden

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
    """SRG_CLIENT_ID / SRG_CLIENT_SECRET aus Env oder ~/.srg-meteo.env (chmod 600)."""
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
        print("SRG_CLIENT_ID / SRG_CLIENT_SECRET fehlen (Env oder ~/.srg-meteo.env mit chmod 600).", file=sys.stderr)
        sys.exit(2)

    _debug(f"Creds: {mask(client_id)} / {mask(client_secret)}")
    return client_id, client_secret

def get_access_token(client_id: str, client_secret: str) -> str:
    """OAuth2 Client-Credentials: grant_type in URL, Basic Auth im Header."""
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
    """Geopunkt via PLZ; falls Name nicht exakt passt, nimm ersten Treffer."""
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
    geolocation_id = f"{lat:.4f},{lon:.4f}"  # "[lat],[lon]"
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
    Wähle genau die nächsten 48 Stunden (Ende jeder Stunde), beginnend ab Ende der laufenden Stunde (lokal).
    """
    tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
    now_local = datetime.now(tz)
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

# -------------------------- Volkszähler ---------------------------------------
def vz_delete_range(uuid: str, from_ts_ms: int, to_ts_ms: int) -> None:
    """
    Zeitbereich löschen (GET, operation=delete).
    Erfordert DELETE-Rechte des DB-Users.
    """
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {"operation": "delete", "from": str(from_ts_ms), "to": str(to_ts_ms)}
    if DRY_RUN:
        print(f"DRY_RUN: DELETE-Range GET {url} params={params}")
        return
    r = requests.get(url, params=params, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(f"Volkszähler-DELETE fehlgeschlagen ({uuid}): HTTP {r.status_code} – {r.text}")

def vz_write(uuid: str, value: float, ts_ms: int) -> None:
    """
    Wert schreiben (POST, operation=add) – Zeitstempel in ms (UTC).
    """
    url = f"{VZ_BASE_URL}/data/{uuid}.json"
    params = {
        "operation": "add",
        "ts": str(ts_ms),
        "value": f"{float(value):.6f}",
    }
    if DRY_RUN:
        print(f"DRY_RUN: POST {url} params={params}")
        return
    r = requests.post(url, params=params, timeout=TIMEOUT)
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

        if not next48:
            print("Keine Forecastdaten für die nächsten 48 h gefunden.", file=sys.stderr)
            return 2

        # Vorschau-Listen zusammenstellen
        tz = ZoneInfo(TZ) if ZoneInfo else timezone.utc
        preview_T: List[Tuple[str, int, Optional[float]]] = []
        preview_I: List[Tuple[str, int, Optional[float]]] = []
        for row in next48:
            dt_utc = parse_dt(row.get("date_time"))
            ts_ms = int(dt_utc.timestamp() * 1000)
            dt_local = dt_utc.astimezone(tz)
            local_str = dt_local.strftime("%Y-%m-%d %H:%M %Z")

            t_val_raw = row.get("TTT_C")
            i_val_raw = row.get("IRRADIANCE_WM2")

            t_val = None
            i_val = None
            try:
                if t_val_raw is not None:
                    t_val = float(str(t_val_raw).replace(",", "."))
            except Exception:
                t_val = None
            try:
                if i_val_raw is not None:
                    i_val = float(str(i_val_raw).replace(",", "."))
            except Exception:
                i_val = None

            preview_T.append((local_str, ts_ms, t_val))
            preview_I.append((local_str, ts_ms, i_val))

        # --- KONSOLE: getrennte Vorschau-Ausgabe ---
        print("\n===== Vorschau: Temperatur (TTT_C) – nächste 48h =====")
        for local_str, ts_ms, val in preview_T:
            vs = "n/a" if val is None else f"{val:.2f} °C"
            print(f"{local_str} | ts_ms={ts_ms} | TTT_C={vs}")

        print("\n===== Vorschau: Einstrahlung (IRRADIANCE_WM2) – nächste 48h =====")
        for local_str, ts_ms, val in preview_I:
            vs = "n/a" if val is None else f"{val:.0f} W/m²"
            print(f"{local_str} | ts_ms={ts_ms} | IRRADIANCE_WM2={vs}")

        # Bereich bestimmen (inklusive)
        start_ts_ms = preview_T[0][1]
        end_ts_ms   = preview_T[-1][1]

        # Löschen & Neu schreiben
        print(f"\nLösche vorhandene Daten in Volkszähler: {start_ts_ms} … {end_ts_ms} (beide Kanäle)")
        vz_delete_range(UUID_T_OUTDOOR, start_ts_ms, end_ts_ms)
        vz_delete_range(UUID_P_PV,      start_ts_ms, end_ts_ms)

        print(f"Schreibe {len(next48)} Stunden (ab nächster voller Stunde, TZ={TZ}) nach Volkszähler…")
        count_T = count_I = 0

        for (_, ts_ms, t_val), (_, _, i_val) in zip(preview_T, preview_I):
            if t_val is not None:
                try:
                    vz_write(UUID_T_OUTDOOR, float(t_val), ts_ms)
                    count_T += 1
                except Exception as e:
                    print(f"Warnung: TTT_C @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)
            if i_val is not None:
                try:
                    vz_write(UUID_P_PV, float(i_val), ts_ms)
                    count_I += 1
                except Exception as e:
                    print(f"Warnung: IRRADIANCE_WM2 @ ts_ms={ts_ms} nicht geschrieben: {e}", file=sys.stderr)

        print(f"\nFertig – geschrieben: T_outdoor_forecast={count_T}, P_PV_forecast={count_I}.")
        if DRY_RUN:
            print("(DRY_RUN aktiv – es wurde nichts in die DB geschrieben.)")
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
