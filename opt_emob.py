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
TARGET_VALUE  = 1            # <- zentral: gesuchter Status (z.B. 3)

DEBUG = True  # bei Bedarf True setzen, um Diagnose-Infos zu sehen

# =========================
# Fetch
# =========================
def get_vals(uuid, duration=f"-{MAX_MINUTES}min"):
    r = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# Hilfen: Spalten-Erkennung & Iteration
# =========================
def _detect_value_index(section):
    """
    Bestimmt, ob in section['tuples'] die Spalte 1 oder 2 der eigentliche 'value' ist,
    indem der jeweilige Spaltenmittelwert mit section['average'] verglichen wird.
    Fallback ist Index 1.
    """
    tuples = section.get("tuples", [])
    if not tuples:
        return 1

    avg = section.get("average", None)
    if avg is None:
        return 1

    def col_avg(idx):
        vals = []
        for t in tuples:
            if isinstance(t, (list, tuple)) and len(t) > idx:
                try:
                    vals.append(float(t[idx]))
                except Exception:
                    pass
        return (sum(vals) / len(vals)) if vals else None

    a1 = col_avg(1)
    a2 = col_avg(2)

    try:
        avg = float(avg)
    except Exception:
        return 1

    if a1 is None and a2 is None:
        return 1
    if a1 is None:
        return 2
    if a2 is None:
        return 1

    # wähle die Spalte, deren Durchschnitt näher an 'average' liegt
    return 1 if abs(a1 - avg) <= abs(a2 - avg) else 2

def iter_points_vz_v03(payload):
    """
    Erwartetes Format (Version 0.3):
    {
      "version": "0.3",
      "data": [
        {
          "tuples": [[ts_ms, col1, col2], ...],
          "average": <float|int>,
          ...
        }
      ]
    }
    Gibt (timestamp_ms, value) zurück – wobei 'value' dynamisch aus Spalte 1 oder 2 kommt.
    """
    data_sections = payload.get("data", [])
    if not isinstance(data_sections, list):
        return

    for section in data_sections:
        tuples = section.get("tuples", [])
        if not isinstance(tuples, list) or not tuples:
            continue

        val_idx = _detect_value_index(section)

        if DEBUG:
            print(f"[DEBUG] value index gewählt: {val_idx}")

        for t in tuples:
            if isinstance(t, (list, tuple)) and len(t) > val_idx:
                yield t[0], t[val_idx]

# =========================
# Kernfunktion
# =========================
def minutes_since_last_target(uuid=UUIDS["Cable_State"], target_value=TARGET_VALUE, max_minutes=MAX_MINUTES):
    """
    Lädt die letzten max_minutes und liefert:
      - Minuten seit letztem Auftreten von target_value
      - oder max_minutes (4320), falls nicht vorhanden.
    """
    try:
        payload = get_vals(uuid, f"-{max_minutes}min")
    except Exception as e:
        if DEBUG:
            print(f"[DEBUG] fetch error: {e}")
        return max_minutes

    last_ts_ms = None
    last_val = None

    for ts_ms, val in iter_points_vz_v03(payload):
        try:
            is_target = int(float(val)) == int(target_value)
        except Exception:
            continue
        if not is_target:
            continue

        try:
            ts_ms = int(ts_ms)
        except Exception:
            continue

        if (last_ts_ms is None) or (ts_ms > last_ts_ms):
            last_ts_ms = ts_ms
            last_val = val

    if last_ts_ms is None:
        if DEBUG:
            print("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return max_minutes

    # ts_ms ist Epoch in Millisekunden -> UTC
    last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)

    if DEBUG:
        print(f"[DEBUG] letzter Treffer: ts={last_ts_ms} ({last_dt.isoformat()}), val={last_val}, diff_min={diff_min}")

    # Clamp in [0, max_minutes]
    if diff_min < 0:
        diff_min = 0
    elif diff_min > max_minutes:
        diff_min = max_minutes
    return diff_min

# =========================
# Ausführung
# =========================
if __name__ == "__main__":
    minutes = minutes_since_last_target()
    print(minutes)


