import requests
from datetime import datetime, timezone

# Behalte dein lokales Volkszähler-Endpoint-Template
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"

UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":  "58163cf0-95ff-11f0-b79d-252564addda6",
}

MAX_MIN = 4320  # 72h

def get_vals(uuid, duration="-4320min"):
    """Daten von Volkszähler lesen."""
    r = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    r.raise_for_status()
    return r.json()

def _iter_points(payload):
    """
    Liefert (timestamp, value)-Tupel aus typischen Volkszähler-Antworten.
    Erwartet i. d. R.: {"data": [[ts, val], ...], ...}
    Unterstützt aber auch Varianten mit Dicts.
    """
    data = payload.get("data", payload)

    if isinstance(data, list):
        for item in data:
            # Standard: [timestamp, value]
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                yield item[0], item[1]
            elif isinstance(item, dict):
                ts = item.get("timestamp") or item.get("ts")
                val = item.get("value")
                if ts is not None and val is not None:
                    yield ts, val
    elif isinstance(data, dict):
        # Einzelnes Dict
        ts = data.get("timestamp") or data.get("ts")
        val = data.get("value")
        if ts is not None and val is not None:
            yield ts, val

def _parse_ts(ts):
    """Timestamp robust nach UTC-Datetime parsen (Epoch s/ms oder ISO-8601)."""
    if isinstance(ts, (int, float)):
        sec = ts / 1000.0 if ts > 1e12 else float(ts)  # ms -> s
        return datetime.fromtimestamp(sec, tz=timezone.utc)
    if isinstance(ts, str):
        # Versuche ISO-8601
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass
        # Fallback: numerisch
        try:
            num = float(ts)
            sec = num / 1000.0 if num > 1e12 else num
            return datetime.fromtimestamp(sec, tz=timezone.utc)
        except Exception:
            pass
    return None

def minutes_since_last_value(uuid, target_value=3, max_minutes=MAX_MIN):
    """
    Lädt 72h Daten und liefert:
      - Minuten seit letztem Auftreten von target_value
      - oder max_minutes (4320), falls nicht vorhanden.
    """
    try:
        payload = get_vals(uuid, f"-{max_minutes}min")
    except Exception:
        # Bei Fehlern konservativ max zurückgeben
        return max_minutes

    last_ts = None
    for ts_raw, val in _iter_points(payload):
        # robust auf int/float/string normalisieren
        try:
            is_target = int(float(val)) == int(target_value)
        except Exception:
            continue
        if not is_target:
            continue

        ts = _parse_ts(ts_raw)
        if ts is None:
            continue
        if (last_ts is None) or (ts > last_ts):
            last_ts = ts

    if last_ts is None:
        return max_minutes

    now = datetime.now(timezone.utc)
    diff_min = int((now - last_ts).total_seconds() // 60)
    # Clamp in [0, max_minutes]
    if diff_min < 0:
        diff_min = 0
    if diff_min > max_minutes:
        diff_min = max_minutes
    return diff_min

if __name__ == "__main__":
    value = minutes_since_last_value(UUIDS["Cable_State"], target_value=1, max_minutes=4320)
    print(value)
