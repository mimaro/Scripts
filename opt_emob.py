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
TARGET_VALUE  = 3             # <— hier zentral setzen (z.B. 3; in deinem Beispiel ist der Wert 1)

# =========================
# Fetch
# =========================
def get_vals(uuid, duration=f"-{MAX_MINUTES}min"):
    r = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    r.raise_for_status()
    return r.json()

# =========================
# Parser für dein Schema
# =========================
def iter_points_vz_v03(payload):
    """
    Erwartetes Format (Version 0.3):
    {
      "version": "0.3",
      "data": [
        {
          "tuples": [[ts_ms, value, quality], ...],
          "uuid": "...",
          ...
        },
        ...
      ]
    }
    Gibt (timestamp_ms, value) über ALLE Reihen in payload["data"] zurück.
    """
    data_sections = payload.get("data", [])
    if not isinstance(data_sections, list):
        return

    for section in data_sections:
        tuples = section.get("tuples", [])
        for t in tuples:
            # t: [timestamp_ms, value, quality] (quality optional)
            if isinstance(t, (list, tuple)) and len(t) >= 2:
                yield t[0], t[1]

def minutes_since_last_target(uuid=UUIDS["Cable_State"], target_value=TARGET_VALUE, max_minutes=MAX_MINUTES):
    """
    Lädt die letzten max_minutes und liefert:
      - Minuten seit letztem Auftreten von target_value
      - oder max_minutes (4320), falls nicht vorhanden.
    """
    try:
        payload = get_vals(uuid, f"-{max_minutes}min")
    except Exception:
        return max_minutes

    last_ts_ms = None
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

    if last_ts_ms is None:
        return max_minutes

    # ts_ms ist Epoch in Millisekunden -> UTC
    last_dt = datetime.fromtimestamp(last_ts_ms / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)

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
    value = minutes_since_last_target()
    print(value)

