#!/usr/bin/env python3
import requests
from datetime import datetime, timezone
import json
import argparse
from typing import Any, Iterable

# =========================
# Konfiguration
# =========================
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":  "58163cf0-95ff-11f0-b79d-252564addda6",
    "Emob_Cons": 	"6cb255a0-6e5f-11ee-b899-c791d8058d25"
}
MAX_MINUTES = 4320      # 72h Lookback
TARGET_VALUE = 1        # <- Standard (kann per CLI überschrieben werden)
VALUE_COLUMN_INDEX = 1  # primäre Spalte (1 oder 2); wir prüfen bei Bedarf beide
AUTO_FALLBACK_TO_OTHER_COLUMN = True
DEBUG = True           # bei Bedarf True
EMOB_CONS_MAX = 20

# =========================
# Fetch
# =========================
def get_vals(uuid: str, duration: str) -> Any:
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url, timeout=10, headers={"Accept": "application/json"})
    if DEBUG:
        print(f"[DEBUG] GET {url} -> {r.status_code}")
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        return json.loads(r.text)


def get_vals_t(uuid, duration="-0min"):
    # Daten von vz lesen. 
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()

# =========================
# Normalisierung & Parser
# =========================
def _normalize_sections(payload: Any):
    """
    Liefert eine Liste von 'Sections', in der jede Section ein Dict mit 'tuples' enthält.
    Unterstützt u.a.:
      - {"version":"0.3","data":{"tuples":[...]}}
      - {"version":"0.3","data":[{"tuples":[...]}]}
      - {"tuples":[...]}
      - [{"tuples":[...]}]
      - [[ts, v, ...], ...]
    """
    # Direktliste von tuples?
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
        # heuristisch: suche eine List-Value, die wie tuples aussieht
        for _, v in payload.items():
            if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
                return [{"tuples": v}]
        return []
    return []

def _iter_section_tuples(section: dict) -> Iterable[list]:
    """
    Gibt alle tuples einer Section zurück: [ts_ms, c1, c2, ...]
    """
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

def _find_last_match_in_sections(sections, col_idx: int, target_value: int):
    """
    Durchsucht alle Sections und gibt den letzten ts_ms zurück, bei dem
    tuples[*][col_idx] == target_value war. (col_idx: 1 oder 2)
    """
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

def _debug_payload_shape(payload):
    if not DEBUG:
        return
    print(f"[DEBUG] payload type: {type(payload).__name__}")
    if isinstance(payload, dict):
        print(f"[DEBUG] payload keys: {list(payload.keys())}")
    elif isinstance(payload, list):
        print(f"[DEBUG] payload len: {len(payload)}; first type: {type(payload[0]).__name__ if payload else 'n/a'}")
    head = json.dumps(payload, ensure_ascii=False)[:600]
    print(f"[DEBUG] payload head: {head}{'...' if len(head)==600 else ''}")

def _debug_sample(sections, col_idx, label):
    if not DEBUG:
        return
    recent = []
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > col_idx:
                recent.append((t[0], t[col_idx]))
    recent = recent[-10:]
    print(f"[DEBUG] {label} – Spalte {col_idx}, letzte Punkte (ts_ms, val):")
    for ts, v in recent:
        print(f"    {ts}, {v}")

# =========================
# Kernfunktion
# =========================
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
        if DEBUG:
            print(f"[DEBUG] fetch error: {e}")
        return max_minutes

    _debug_payload_shape(payload)
    sections = _normalize_sections(payload)
    if DEBUG:
        print(f"[DEBUG] sections erkannt: {len(sections)}")
        if sections:
            print(f"[DEBUG] first section keys: {list(sections[0].keys())}")

    if not sections:
        if DEBUG:
            print("[DEBUG] Keine sections/tuples gefunden.")
        return max_minutes

    # 1) Versuch mit der konfigurierten Spalte
    _debug_sample(sections, VALUE_COLUMN_INDEX, "Primärversuch")
    last_ts_ms = _find_last_match_in_sections(sections, VALUE_COLUMN_INDEX, target_value)

    # 2) Optionaler Fallback auf die andere Spalte (1 <-> 2)
    if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
        other = 2 if VALUE_COLUMN_INDEX == 1 else 1
        _debug_sample(sections, other, "Fallbackversuch")
        last_ts_ms = _find_last_match_in_sections(sections, other, target_value)

    if last_ts_ms is None:
        if DEBUG:
            print("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return max_minutes

    # ts_ms ist Epoch in ms -> UTC
    last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)

    if diff_min < 0:
        diff_min = 0
    elif diff_min > max_minutes:
        diff_min = max_minutes

    if DEBUG:
        print(f"[DEBUG] letzter Treffer: {last_dt.isoformat()}Z, diff_min={diff_min}")

    return diff_min

# =========================
# CLI / Main
# =========================
def main():
    parser = argparse.ArgumentParser(description="Minuten seit letztem Auftreten eines Zielwerts (Cable_State).")
    parser.add_argument("--target", type=int, default=TARGET_VALUE,
                        help="Zielwert, der gesucht wird (Default: 3). Für Tests z.B. --target 1")
    parser.add_argument("--uuid", type=str, default=UUIDS["Cable_State"],
                        help="UUID, Default: Cable_State")
    parser.add_argument("--window", type=int, default=MAX_MINUTES,
                        help="Suchfenster in Minuten (Default: 4320)")
    parser.add_argument("--debug", action="store_true", help="Debug-Ausgaben aktivieren")
    parser.add_argument("--show-ts", action="store_true",
                        help="Zusätzlich den ISO-Zeitpunkt des letzten Treffers ausgeben")
    args = parser.parse_args()

    global DEBUG
    DEBUG = args.debug

    minutes = minutes_since_last_target(args.uuid, args.target, args.window)
    print(minutes)

    if args.show_ts and minutes < args.window:
        # Zeitpunkt erneut bestimmen (nutzt die gleiche Logik)
        payload = get_vals(args.uuid, f"-{args.window}min")
        sections = _normalize_sections(payload)
        last_ts_ms = _find_last_match_in_sections(sections, VALUE_COLUMN_INDEX, args.target)
        if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
            other = 2 if VALUE_COLUMN_INDEX == 1 else 1
            last_ts_ms = _find_last_match_in_sections(sections, other, args.target)
        if last_ts_ms is not None:
            last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc).isoformat()
            print(last_dt)

    emob_cons = get_vals_t(UUID["Emob_Cons"], duration=minutes)["data"]["conspumtion"]
    print(emob_cons)




if __name__ == "__main__":
    main()

