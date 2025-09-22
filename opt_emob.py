#!/usr/bin/env python3
import re
import requests
from datetime import datetime, timezone
import json
import argparse
from typing import Any, Iterable, List, Tuple
import statistics

# =========================
# Konfiguration
# =========================
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":  "58163cf0-95ff-11f0-b79d-252564addda6",
    "Emob_Cons":    "85ffa8d0-683e-11ee-9486-113294e4804d"
}

MAX_MINUTES = 4320      # 72h Lookback
TARGET_VALUE = 1        # <- Standard (kann per CLI überschrieben werden)
VALUE_COLUMN_INDEX = 1  # primäre Spalte (1 oder 2); wir prüfen bei Bedarf beide
AUTO_FALLBACK_TO_OTHER_COLUMN = True
DEBUG = True            # bei Bedarf True
TRACE_ENERGY = True    # Trapezregel-Trace
EMOB_CONS_MAX = 20      # (unbenutzt, nur Beispiel-Grenze)

# =========================
# Helpers (Debug)
# =========================
def fmt_ts(ms: int) -> str:
    try:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ms)

def _print_debug(msg: str):
    if DEBUG:
        print(msg)

def _summary_stats(vals: List[float]) -> str:
    if not vals:
        return "n=0"
    try:
        return (f"n={len(vals)}, min={min(vals):.3f}, p25={statistics.quantiles(vals, n=4)[0]:.3f}, "
                f"median={statistics.median(vals):.3f}, p75={statistics.quantiles(vals, n=4)[-1]:.3f}, "
                f"max={max(vals):.3f}, mean={statistics.fmean(vals):.3f}")
    except Exception:
        return f"n={len(vals)}, min={min(vals):.3f}, max={max(vals):.3f}, mean≈{sum(vals)/len(vals):.3f}"

# =========================
# HTTP / Payload
# =========================
def get_vals(uuid: str, duration: str) -> Any:
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url, timeout=10, headers={"Accept": "application/json"})
    _print_debug(f"[DEBUG] GET {url} -> {r.status_code}, bytes={len(r.content)}")
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)

def vz_get(uuid: str, duration: str):
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url, timeout=10, headers={"Accept": "application/json"})
    _print_debug(f"[DEBUG] GET {url} -> {r.status_code}, bytes={len(r.content)}")
    r.raise_for_status()
    return r.json()

def _normalize_sections(payload: Any):
    # (unverändert, nur kleine Debug-Erweiterungen)
    if isinstance(payload, list):
        if payload and isinstance(payload[0], (list, tuple)):
            return [{"tuples": payload}]
        if payload and isinstance(payload[0], dict):
            return payload
        return []

    if isinstance(payload, dict):
        if "data" in payload:
            data = payload["data"]
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                if "tuples" in data and isinstance(data["tuples"], list):
                    return [data]
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
                return [data]
            return []
        if "tuples" in payload and isinstance(payload["tuples"], list):
            return [payload]
        for _, v in payload.items():
            if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
                return [{"tuples": v}]
        return []
    return []

def _iter_section_tuples(section: dict) -> Iterable[list]:
    tuples = section.get("tuples", [])
    if isinstance(tuples, list):
        for t in tuples:
            if isinstance(t, (list, tuple)) and len(t) >= 2:
                yield t

def _cast_to_int(val):
    try:
        return int(float(val))
    except Exception:
        return None

def _debug_payload_shape(payload: Any, label: str = "payload"):
    _print_debug(f"[DEBUG] {label} type: {type(payload).__name__}")
    if isinstance(payload, dict):
        _print_debug(f"[DEBUG] {label} keys: {list(payload.keys())}")
    elif isinstance(payload, list):
        _print_debug(f"[DEBUG] {label} len: {len(payload)}; first type: {type(payload[0]).__name__ if payload else 'n/a'}")
    head = json.dumps(payload, ensure_ascii=False)[:600]
    _print_debug(f"[DEBUG] {label} head: {head}{'...' if len(head)==600 else ''}")

def _debug_sample(sections, col_idx, label):
    recent = []
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > col_idx:
                recent.append((t[0], t[col_idx]))
    recent = recent[-10:]
    _print_debug(f"[DEBUG] {label} – Spalte {col_idx}, letzte Punkte (ts_ms, val):")
    for ts, v in recent:
        _print_debug(f"    {ts} ({fmt_ts(int(ts))}), {v}")

def _scan_matches(sections, col_idx: int, target_value: int) -> List[int]:
    hits: List[int] = []
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > col_idx and _cast_to_int(t[col_idx]) == target_value:
                try:
                    hits.append(int(t[0]))
                except Exception:
                    pass
    return hits

def _sections_time_range(sections) -> Tuple[int, int, int]:
    ts_all: List[int] = []
    for s in sections:
        for t in _iter_section_tuples(s):
            try:
                ts_all.append(int(t[0]))
            except Exception:
                pass
    if not ts_all:
        return (0, 0, 0)
    return (len(ts_all), min(ts_all), max(ts_all))

# =========================
# Kernfunktion
# =========================
def _find_last_match_in_sections(sections, col_idx: int, target_value: int):
    last_ts_ms = None
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) <= col_idx:
                continue
            v = _cast_to_int(t[col_idx])
            if v is None or v != target_value:
                continue
            try:
                ts_ms = int(t[0])
            except Exception:
                continue
            if (last_ts_ms is None) or (ts_ms > last_ts_ms):
                last_ts_ms = ts_ms
    return last_ts_ms

def minutes_since_last_target(uuid: str,
                              target_value: int,
                              max_minutes: int = MAX_MINUTES) -> int:
    """
    Lädt die letzten max_minutes und liefert die Minuten seit dem letzten Auftreten
    von target_value; andernfalls max_minutes.
    """
    try:
        payload = get_vals(uuid, f"-{max_minutes}min")
    except Exception as e:
        _print_debug(f"[DEBUG] fetch error: {e}")
        return max_minutes

    _debug_payload_shape(payload, "state-payload")
    sections = _normalize_sections(payload)
    _print_debug(f"[DEBUG] sections erkannt: {len(sections)}")
    if sections:
        _print_debug(f"[DEBUG] first section keys: {list(sections[0].keys())}")

    if not sections:
        _print_debug("[DEBUG] Keine sections/tuples gefunden.")
