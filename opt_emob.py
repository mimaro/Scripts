import requests
from datetime import datetime, timezone
import json
from typing import Iterable, Tuple, Any

# =========================
# Konfiguration
# =========================
VZ_GET_URL    = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":  "58163cf0-95ff-11f0-b79d-252564addda6",
}
MAX_MINUTES   = 4320          # 72h
TARGET_VALUE  = 1             # <- zentral definierter Zielwert
VALUE_COLUMN_INDEX = 1        # Standard: 1 (tuples = [ts, value, quality]); bei Bedarf 2
AUTO_FALLBACK_TO_OTHER_COLUMN = True
DEBUG = True                  # <- für Diagnose auf True setzen

# =========================
# Fetch
# =========================
def get_vals(uuid: str, duration: str = f"-{MAX_MINUTES}min") -> Any:
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url, timeout=10, headers={"Accept": "application/json"})
    if DEBUG:
        print(f"[DEBUG] GET {url} -> {r.status_code}")
    r.raise_for_status()
    try:
        return r.json()
    except Exception:
        # Manche Instanzen liefern JSON als String mit falschem Content-Type
        return json.loads(r.text)

# =========================
# Normalisierung & Parser
# =========================
def _normalize_sections(payload: Any):
    """
    Versucht, eine Liste von 'Sections' zu erzeugen, die jeweils ein Dict mit 'tuples' enthalten.
    Unterstützte Formen:
      - {"version":"0.3","data":[{...}]}
      - {"data":{"tuples":[...]}}
      - {"tuples":[...]}
      - [{"tuples":[...]}]
      - [[ts, v, ...], ...]
    """
    # Direktliste von tuples?
    if isinstance(payload, list):
        if payload and isinstance(payload[0], (list, tuple)):
            return [{"tuples": payload}]
        # Liste von Sections
        if payload and isinstance(payload[0], dict):
            # z.B. [{"tuples":[...]}]
            return payload
        # Leere Liste
        return []

    # Dict-Fall
    if isinstance(payload, dict):
        # Volkszähler 0.3: {"data":[...]}
        if "data" in payload:
            data = payload["data"]
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                # {"data":{"tuples":[...]}}
                if "tuples" in data and isinstance(data["tuples"], list):
                    return [data]
                # manche liefern {"data":{"data":[...]}} etc.
                if "data" in data and isinstance(data["data"], list):
                    return data["data"]
                # Fallback: in Liste packen
                return [data]
            # data ist None oder anderes -> leer
            return []
        # Direkter Section-Body: {"tuples":[...]}
        if "tuples" in payload and isinstance(payload["tuples"], list):
            return [payload]
        # Manchmal steckt es unter anderem Key (z.B. "rows"): wir versuchen heuristisch
        for k, v in payload.items():
            if isinstance(v, list) and v and isinstance(v[0], (list, tuple)):
                # Das sieht nach tuples aus
                return [{"tuples": v}]
        return []

    # Alles andere -> leer
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
    last_ts_ms = None
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) <= col_idx:
                continue
            ts_ms = t[0]
            v = _cast_to_int(t[col_idx])
            if v is None:
                continue
            if v == target_value:
                try:
                    ts_ms = int(ts_ms)
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
    txt = json.dumps(payload, ensure_ascii=False)[:600]
    print(f"[DEBUG] payload head: {txt}{'...' if len(txt)==600 else ''}")

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
def minutes_since_last_target(uuid: str = UUIDS["Cable_State"],
                              target_value: int = TARGET_VALUE,
                              max_minutes: int = MAX_MINUTES) -> int:
    """
    Lädt die letzten max_minutes und liefert:
      - Minuten seit letztem Auftreten von target_value
      - oder max_minutes, falls nicht vorhanden.
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
            # zeige kurz Struktur der ersten Section
            print(f"[DEBUG] first section keys: {list(sections[0].keys())}")

    if not sections:
        if DEBUG:
            print("[DEBUG] Keine sections/tuples gefunden. Prüfe Endpoint/Parameter.")
        return max_minutes

    # 1) Konfigurierte Spalte
    _debug_sample(sections, VALUE_COLUMN_INDEX, "Primärversuch")
    last_ts_ms = _find_last_match_in_sections(sections, VALUE_COLUMN_INDEX, target_value)

    # 2) Optional: Fallback andere Spalte (nur sinnvoll bei 1/2)
    if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
        other = 2 if VALUE_COLUMN_INDEX == 1 else 1
        _debug_sample(sections, other, "Fallbackversuch")
        last_ts_ms = _find_last_match_in_sections(sections, other, target_value)

    if last_ts_ms is None:
        if DEBUG:
            print("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return max_minutes

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
# Ausführung
# =========================
if __name__ == "__main__":
    minutes = minutes_since_last_target()
    print(minutes)
