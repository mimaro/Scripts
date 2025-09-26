#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import json
import math
import statistics
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import requests
from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:
    ZoneInfo = None


# =========================
# Konfiguration
# =========================
BASE_URL = "http://192.168.178.49/middleware.php"
VZ_GET_URL_FROM = BASE_URL + "/data/{}.json?from={}"            # from als Dauer/ISO/ms
VZ_GET_URL_BETWEEN = BASE_URL + "/data/{}.json?from={}&to={}"   # from & to
VZ_POST_URL = BASE_URL + "/data/{}.json"                        # ts & value als params

UUIDS: Dict[str, str] = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":   "58163cf0-95ff-11f0-b79d-252564addda6",     # 0/1
    "Emob_Cons":     "6cb255a0-6e5f-11ee-b899-c791d8058d25",     # Leistung/Energie (W/Wh)
    "Price":         "a1547420-8c87-11f0-ab9a-bd73b64c1942",     # Tarif (z.B. Rp/kWh)
}

# Suchfenster für den letzten "1"-Zustand am Kabel (Minuten)
MAX_LOOKBACK_MIN = 4320  # 72h

# Lade-Parameter
MAX_LADUNG_KWH = 20.0    # Ziel-Ladeenergie
LADELEISTUNG_KW = 7.0     # AC-Ladeleistung
RUND_MINUTEN = 15         # auf 15-Minuten-Schritte runden

# Debug
DEBUG = False
TRACE_ENERGY = False


# =========================
# Helpers / Debug
# =========================
def _d(msg: str) -> None:
    if DEBUG:
        print(msg)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ch_tz():
    return ZoneInfo("Europe/Zurich") if ZoneInfo else timezone(timedelta(hours=1))  # Fallback: CET (+1, ohne DST)


def fmt_ts(ms: int) -> str:
    try:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ms)


def ceil_to_step_minutes(minutes: float, step: int = 15) -> int:
    """Rundet Minuten auf das nächste Vielfache von 'step' nach oben."""
    if minutes <= 0:
        return 0
    return int(math.ceil(minutes / step) * step)


# =========================
# HTTP / Volkszähler I/O
# =========================
def _get_json(url: str) -> Any:
    r = requests.get(url, timeout=15, headers={"Accept": "application/json"})
    _d(f"[DEBUG] GET {url} -> {r.status_code}, bytes={len(r.content)}")
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def get_vals(uuid: str, duration: str) -> Any:
    return _get_json(VZ_GET_URL_FROM.format(uuid, duration))


def get_vals_between(uuid: str, frm: str, to: str = "now") -> Any:
    return _get_json(VZ_GET_URL_BETWEEN.format(uuid, frm, to))


def post_point(uuid: str, ts_ms: int, value: Union[int, float]) -> None:
    """Schreibt einen Punkt minütlich (operation=add, ts in ms UTC)."""
    params = {"operation": "add", "ts": str(int(ts_ms)), "value": str(value)}
    r = requests.post(VZ_POST_URL.format(uuid), params=params, timeout=15)
    if not r.ok:
        raise RuntimeError(f"POST failed {uuid}@{ts_ms}: {r.status_code} {r.text[:200]}")


def delete_range(uuid: str, from_ms: int, to_ms: int) -> None:
    """Löscht existierende Werte im Bereich (inklusive) – optional, hier genutzt um alte Werte zu bereinigen."""
    params = {"operation": "delete", "from": str(int(from_ms)), "to": str(int(to_ms))}
    r = requests.get(VZ_POST_URL.format(uu
