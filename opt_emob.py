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
        return max_minutes

    # Überblick über Zeitbereich der State-Daten
    n, tmin, tmax = _sections_time_range(sections)
    if n:
        _print_debug(f"[DEBUG] State-Zeitbereich: n={n}, first={tmin} ({fmt_ts(tmin)}), last={tmax} ({fmt_ts(tmax)})")

    # 1) Primärspalte
    _debug_sample(sections, VALUE_COLUMN_INDEX, "Primärversuch")
    hits_primary = _scan_matches(sections, VALUE_COLUMN_INDEX, target_value)
    last_ts_ms = max(hits_primary) if hits_primary else None
    _print_debug(f"[DEBUG] Treffer Primärspalte: {len(hits_primary)}; last={fmt_ts(last_ts_ms) if last_ts_ms else 'n/a'}")

    # 2) Optionaler Fallback
    if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
        other = 2 if VALUE_COLUMN_INDEX == 1 else 1
        _debug_sample(sections, other, "Fallbackversuch")
        hits_other = _scan_matches(sections, other, target_value)
        last_ts_ms = max(hits_other) if hits_other else None
        _print_debug(f"[DEBUG] Treffer Fallback-Spalte {other}: {len(hits_other)}; last={fmt_ts(last_ts_ms) if last_ts_ms else 'n/a'}")

    if last_ts_ms is None:
        _print_debug("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return max_minutes

    last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)

    if diff_min < 0:
        _print_debug(f"[DEBUG] WARN: last_dt liegt in der Zukunft ({last_dt.isoformat()}Z); setze diff_min=0")
        diff_min = 0
    elif diff_min > max_minutes:
        diff_min = max_minutes

    _print_debug(f"[DEBUG] letzter Treffer: {last_dt.isoformat()}Z, diff_min={diff_min}")
    if diff_min == 0:
        _print_debug("[DEBUG] diff_min=0 -> Energie-Zeitfenster wäre -0min (leer). Prüfe, ob Target derzeit = 1 ist und ob das beabsichtigt ist.")

    return diff_min

# =========================
# Energie seit letzten Einstecken abrufen
# =========================
def parse_minutes(minutes) -> int:
    """
    Normalisiert 'minutes' zu einem positiven int in [0, MAX_MINUTES].
    Akzeptiert z.B.: 273, "273", "-273", "-273min", "273min".
    """
    if isinstance(minutes, (int, float)):
        m = int(minutes)
    elif isinstance(minutes, str):
        m = 0
        m_str = "".join(re.findall(r"-?\d+", minutes))  # erste Zahl extrahieren
        if m_str:
            m = int(m_str)
    else:
        m = 0

    if m < 0:
        m = -m  # wir brauchen die Größe; das Minus kommt erst im duration-String
    if m > MAX_MINUTES:
        m = MAX_MINUTES
    return m

def _energy_debug_overview(tuples: List[list]):
    if not DEBUG:
        return
    if not tuples:
        _print_debug("[DEBUG] ENERGY: keine Datenpunkte erhalten.")
        return
    ts = [int(t[0]) for t in tuples]
    p  = [float(t[1]) for t in tuples if len(t) >= 2]
    dts = [ (ts[i]-ts[i-1])/1000.0 for i in range(1, len(ts)) ]  # in s
    _print_debug(f"[DEBUG] ENERGY: tuples={len(tuples)}, range={fmt_ts(min(ts))} .. {fmt_ts(max(ts))}")
    _print_debug(f"[DEBUG] ENERGY: Δt(s) stats -> {_summary_stats(dts)}")
    _print_debug(f"[DEBUG] ENERGY: P(W) stats  -> {_summary_stats(p)} (all_zero={all(v==0 for v in p)})")
    _print_debug("[DEBUG] ENERGY: letzte 5 Punkte (ts, iso, W):")
    for t in tuples[-5:]:
        try:
            _print_debug(f"    {t[0]}  {fmt_ts(int(t[0]))}  {float(t[1])}")
        except Exception:
            _print_debug(f"    {t}")

def energy_kwh_from_power(uuid: str, minutes) -> float:
    """
    Robuste Integration eines Leistungs-Kanals (W) über 'minutes' Minuten -> kWh.
    Nutzt Trapezregel (für ungleichmäßige Abstände).
    Erwartetes Format:
      {"data":{"tuples":[[ts_ms, value_W, (quality)], ...]}} oder
      {"data":[{"tuples":[...]}]}
    """
    m = parse_minutes(minutes)
    if m == 0:
        _print_debug("[DEBUG] ENERGY: Fenster-Minuten = 0 -> kWh=0. (Ist das beabsichtigt?)")
        return 0.0

    duration = f"-{m}min"
    payload = vz_get(uuid, duration=duration)
    _debug_payload_shape(payload, "energy-payload")

    data = payload.get("data", [])
    if isinstance(data, dict):
        tuples = data.get("tuples", [])
    elif isinstance(data, list):
        tuples = []
        for section in data:
            tuples.extend(section.get("tuples", []))
    else:
        tuples = []

    # Sortieren / Aufbereiten
    tuples = [t for t in tuples if isinstance(t, (list, tuple)) and len(t) >= 2]
    tuples.sort(key=lambda t: int(t[0]) )

    _energy_debug_overview(tuples)

    if not tuples:
        _print_debug("[DEBUG] ENERGY: keine tuples -> kWh=0.")
        return 0.0

    # Trapezregel
    energy_Wh = 0.0
    prev_ts = None
    prev_p  = None
    for tup in tuples:
        ts_ms = int(tup[0])
        p_w   = float(tup[1])
        if prev_ts is not None:
            dt_h = (ts_ms - prev_ts) / 1000.0 / 3600.0
            area = 0.5 * (prev_p + p_w) * dt_h  # Wh
            energy_Wh += area
            if TRACE_ENERGY:
                _print_debug(f"[TRACE] ts={fmt_ts(prev_ts)}→{fmt_ts(ts_ms)} dt_h={dt_h:.6f} prev_p={prev_p:.3f} p={p_w:.3f} add_Wh={area:.6f}")
        prev_ts = ts_ms
        prev_p  = p_w

    kwh = energy_Wh / 1000.0
    _print_debug(f"[DEBUG] ENERGY: Ergebnis -> {kwh:.6f} kWh (Wh={energy_Wh:.3f})")
    return kwh

def energy_kwh_from_power_simple(uuid: str, minutes) -> float:
    """
    Einfache Formel, NUR korrekt wenn genau 1 Messpunkt pro Minute (Durchschnittsleistung) vorhanden ist:
      kWh ≈ Σ(W)*60s / 3_600_000 = Σ(W) / 60_000
    """
    m = parse_minutes(minutes)
    if m == 0:
        _print_debug("[DEBUG] ENERGY(simple): Fenster-Minuten = 0 -> kWh=0.")
        return 0.0
    payload = vz_get(uuid, duration=f"-{m}min")
    data = payload.get("data", [])
    tuples = (
        data.get("tuples", [])
        if isinstance(data, dict)
        else (data[0].get("tuples", []) if data else [])
    )
    tuples = [t for t in tuples if isinstance(t, (list, tuple)) and len(t) >= 2]
    if DEBUG:
        _energy_debug_overview(tuples)
    return sum(float(t[1]) for t in tuples) / 60000.0

# =========================
# CLI / Main
# =========================
def main():
    parser = argparse.ArgumentParser(description="Minuten seit letztem Auftreten eines Zielwerts (Cable_State).")
    parser.add_argument("--target", type=int, default=TARGET_VALUE,
                        help="Zielwert, der gesucht wird (Default: 1)")
    parser.add_argument("--uuid", type=str, default=UUIDS["Cable_State"],
                        help="UUID, Default: Cable_State")
    parser.add_argument("--window", type=int, default=MAX_MINUTES,
                        help="Suchfenster in Minuten (Default: 4320)")
    parser.add_argument("--debug", action="store_true", help="Debug-Ausgaben aktivieren")
    parser.add_argument("--trace-energy", action="store_true",
                        help="Trapezregel Schritt-für-Schritt protokollieren")
    parser.add_argument("--show-ts", action="store_true",
                        help="Zusätzlich den ISO-Zeitpunkt des letzten Treffers ausgeben")
    parser.add_argument("--energy-uuid", type=str, default=UUIDS["Emob_Cons"],
                        help="UUID für Energie/Leistung (Default: Emob_Cons)")
    args = parser.parse_args()

    global DEBUG, TRACE_ENERGY
    DEBUG = args.debug
    TRACE_ENERGY = args.trace_energy

    # 1) Minuten seit letztem Target
    minutes = minutes_since_last_target(args.uuid, args.target, args.window)
    print(minutes)
    minutes_val = f"-{int(minutes)}min"
    print(minutes_val)

    # Optional: Zeitpunkt nochmal anzeigen
    if args.show_ts and minutes < args.window:
        payload = get_vals(args.uuid, f"-{args.window}min")
        sections = _normalize_sections(payload)
        # Primär + Fallback (nur für Anzeige)
        last_ts_ms = _find_last_match_in_sections(sections, VALUE_COLUMN_INDEX, args.target)
        if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
            other = 2 if VALUE_COLUMN_INDEX == 1 else 1
            last_ts_ms = _find_last_match_in_sections(sections, other, args.target)
        if last_ts_ms is not None:
            last_dt_iso = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc).isoformat().replace("+00:00","Z")
            print(last_dt_iso)

    # 2) Energie seit diesem Zeitpunkt
    if minutes == 0:
        _print_debug("[DEBUG] HINWEIS: minutes==0 -> das Fenster für die Energieabfrage ist leer. "
                     "Falls du Energie 'seit der letzten Änderung AUF 1' willst, brauchst du den Zeitpunkt "
                     "des Übergangs (0→1) statt 'letztes Mal ==1'.")
    emob_cons_kwh = energy_kwh_from_power(args.energy_uuid, minutes=minutes_val)
    print(f"{emob_cons_kwh:.3f} kWh")

if __name__ == "__main__":
    main()
