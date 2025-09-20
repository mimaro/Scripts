import requests
from datetime import datetime, timezone

# =========================
# Konfiguration
# =========================
VZ_GET_URL    = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":  "58163cf0-95ff-11f0-b79d-252564addda6",
}
MAX_MINUTES   = 4320          # 72h
TARGET_VALUE  = 1             # <— zentral definierter Zielwert
VALUE_COLUMN_INDEX = 1        # <— 1 oder 2 (dein Wert sitzt in tuples[INDEX])
AUTO_FALLBACK_TO_OTHER_COLUMN = True
DEBUG = True                 # auf True stellen für Diagnose

# =========================
# Fetch
# =========================
def get_vals(uuid, duration=f"-{MAX_MINUTES}min"):
    r = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# Parser & Suche
# =========================
def _iter_section_tuples(section):
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

def _find_last_match_in_sections(sections, col_idx, target_value):
    """
    Durchsucht alle sections und gibt den letzten ts_ms zurück, bei dem
    tuples[*][col_idx] == target_value war. (col_idx: 1 oder 2)
    """
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

def _debug_sample(sections, col_idx, target_value):
    if not DEBUG:
        return
    # zeige die letzten ~10 Punkte der gewählten Spalte
    recent = []
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > col_idx:
                recent.append((t[0], t[col_idx]))
    recent = recent[-10:]
    print(f"[DEBUG] gewählte Spalte: {col_idx}; TARGET={target_value}")
    print(f"[DEBUG] letzte Punkte (ts_ms, value):")
    for ts, v in recent:
        print(f"    {ts}, {v}")

def minutes_since_last_target(uuid=UUIDS["Cable_State"], target_value=TARGET_VALUE, max_minutes=MAX_MINUTES):
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

    sections = payload.get("data", [])
    if not isinstance(sections, list) or not sections:
        if DEBUG:
            print("[DEBUG] payload['data'] leer oder kein Listentyp")
        return max_minutes

    # 1) Versuch mit der konfigurierten Spalte
    _debug_sample(sections, VALUE_COLUMN_INDEX, target_value)
    last_ts_ms = _find_last_match_in_sections(sections, VALUE_COLUMN_INDEX, target_value)

    # 2) Optional: Fallback auf die andere Spalte (1 -> 2, 2 -> 1)
    if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
        other = 2 if VALUE_COLUMN_INDEX == 1 else 1
        if DEBUG:
            print(f"[DEBUG] kein Treffer in Spalte {VALUE_COLUMN_INDEX}, versuche Spalte {other}")
            _debug_sample(sections, other, target_value)
        last_ts_ms = _find_last_match_in_sections(sections, other, target_value)

    if last_ts_ms is None:
        if DEBUG:
            print("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return max_minutes

    # ts_ms ist Epoch in Millisekunden -> UTC
    last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)

    if diff_min < 0:
        diff_min = 0
    elif diff_min > max_minutes:
        diff_min = max_minutes

    if DEBUG:
        print(f"[DEBUG] letzter Treffer: ts={last_ts_ms} ({last_dt.isoformat()}), diff_min={diff_min}")

    return diff_min

# =========================
# Ausführung
# =========================
if __name__ == "__main__":
    minutes = minutes_since_last_target()
    print(minutes)
