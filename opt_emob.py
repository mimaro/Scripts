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
    r = requests.get(VZ_POST_URL.format(uuid), params=params, timeout=20)
    if not r.ok:
        raise RuntimeError(f"DELETE failed {uuid} [{from_ms}..{to_ms}]: {r.status_code} {r.text[:200]}")


# =========================
# Payload-Normalisierung
# =========================
def _normalize_sections(payload: Any) -> List[dict]:
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


def _sections_time_range(sections: List[dict]) -> Tuple[int, int, int]:
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
# 1) Letzten Zeitpunkt finden, an dem Cable_State == 1 war
# =========================
def find_last_ts_equal(uuid: str, target_value: int, lookback_min: int) -> Optional[int]:
    payload = get_vals(uuid, f"-{lookback_min}min")
    sections = _normalize_sections(payload)

    if not sections:
        return None

    last_ts_ms = None
    for section in sections:
        for t in _iter_section_tuples(section):
            try:
                ts_ms = int(t[0])
                val = int(float(t[1]))
                if val == target_value:
                    if last_ts_ms is None or ts_ms > last_ts_ms:
                        last_ts_ms = ts_ms
            except Exception:
                continue
    return last_ts_ms


# =========================
# 2) Energie seit last_ts in kWh
# =========================
def energy_kwh_from_power_between(uuid: str, from_ts_ms: int, to: str = "now") -> float:
    if from_ts_ms is None:
        return 0.0

    payload = get_vals_between(uuid, str(int(from_ts_ms)), to)
    data = payload.get("data", [])
    data_obj = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else {})

    # 1) consumption (Wh)
    if isinstance(data_obj, dict) and data_obj.get("consumption") is not None:
        try:
            return float(data_obj["consumption"]) / 1000.0
        except Exception:
            pass

    # Tuples sammeln (ts, value)
    if isinstance(data, dict):
        tuples = data.get("tuples", [])
    elif isinstance(data, list):
        tuples = []
        for section in data:
            tuples.extend(section.get("tuples", []))
    else:
        tuples = []

    tuples = [t for t in tuples if isinstance(t, (list, tuple)) and len(t) >= 2]
    try:
        tuples.sort(key=lambda t: int(t[0]))
    except Exception:
        pass

    # 2) average * dt
    if isinstance(data_obj, dict) and all(k in data_obj for k in ("average", "from", "to")):
        try:
            avg_w = float(data_obj["average"])
            dt_h = (int(data_obj["to"]) - int(data_obj["from"])) / 3_600_000.0
            return (avg_w * dt_h) / 1000.0
        except Exception:
            pass

    # 3) Trapezregel
    if len(tuples) >= 2:
        energy_Wh = 0.0
        prev_ts, prev_p = None, None
        for tup in tuples:
            ts_ms = int(tup[0]); p_w = float(tup[1])
            if prev_ts is not None:
                dt_h = (ts_ms - prev_ts) / 3_600_000.0
                energy_Wh += 0.5 * (prev_p + p_w) * dt_h
            prev_ts, prev_p = ts_ms, p_w
        return energy_Wh / 1000.0

    return 0.0


# =========================
# 3) Preisreihe (minütlich) zwischen jetzt und nächstem 05:00 CH
# =========================
def next_5_local(now_local: datetime) -> datetime:
    tz = ch_tz()
    today_5 = now_local.replace(hour=5, minute=0, second=0, microsecond=0)
    if now_local < today_5:
        end_local = today_5
    else:
        end_local = (now_local + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)
    # Bei DST-Sprüngen kann 05:00 „springen“ – absichern:
    return tz.fromutc(end_local.astimezone(timezone.utc).replace(tzinfo=timezone.utc)).astimezone(tz)


def get_price_series_minutely(from_local: datetime, to_local: datetime) -> List[Tuple[int, float]]:
    """
    Liefert [(ts_ms_utc, price), …] im Minutentakt durch Vorwärts-Halten
    der letzten bekannten Preisprobe (geeignet für 15-min Slots).
    """
    tz = ch_tz()
    from_utc = from_local.astimezone(timezone.utc)
    to_utc = to_local.astimezone(timezone.utc)

    payload = get_vals_between(UUIDS["Price"], str(int(from_utc.timestamp() * 1000)), str(int(to_utc.timestamp() * 1000)))
    sections = _normalize_sections(payload)
    if not sections:
        return []

    # Raw tuples zusammenführen
    raw: List[Tuple[int, float]] = []
    for s in sections:
        for t in _iter_section_tuples(s):
            try:
                ts = int(t[0])
                val = float(t[1])
                raw.append((ts, val))
            except Exception:
                continue
    raw.sort(key=lambda x: x[0])

    if not raw:
        return []

    # Minutengitter bauen & Preis "halten"
    start_ms = int(from_utc.timestamp() * 1000)
    end_ms = int(to_utc.timestamp() * 1000)
    minute = 60_000

    series: List[Tuple[int, float]] = []
    idx = 0
    current_val = raw[0][1]

    for ts in range(start_ms, end_ms, minute):
        while idx + 1 < len(raw) and raw[idx + 1][0] <= ts:
            idx += 1
            current_val = raw[idx][1]
        series.append((ts, current_val))

    return series


# =========================
# 4) Freigabe-Fenster berechnen & schreiben
# =========================
def plan_and_write(from_local: datetime, to_local: datetime, minutes_needed: int) -> None:
    """
    - Holt minütliche Preise [from, to)
    - Wählt 'minutes_needed' günstigste Minuten
    - Schreibt 1 für gewählte Minuten, sonst 0
    - Gibt Stundenmittel (lokale Stunden) zur Kontrolle aus
    """
    tz = ch_tz()
    prices = get_price_series_minutely(from_local, to_local)
    if not prices:
        print("⚠️  Keine Preisdaten im gewünschten Fenster – es wird überall 0 geschrieben.")
        minutes_needed = 0

    # Minutenliste [ (ts_ms, price) ]
    # Anzahl verfügbarer Minuten:
    total_minutes = int((to_local - from_local).total_seconds() // 60)
    # Sicherheitskürzung auf verfügbare Länge
    minutes_needed = max(0, min(minutes_needed, total_minutes))

    # Günstigste Minuten wählen
    if minutes_needed > 0:
        sorted_by_price = sorted(prices, key=lambda x: (x[1], x[0]))
        chosen_set = set(ts for ts, _ in sorted_by_price[:minutes_needed])
    else:
        chosen_set = set()

    # Bereich vorab löschen (saubere Planung)
    from_ms = int(from_local.astimezone(timezone.utc).timestamp() * 1000)
    to_ms = int(to_local.astimezone(timezone.utc).timestamp() * 1000) - 1
    try:
        delete_range(UUIDS["Freigabe_EMob"], from_ms, to_ms)
    except Exception as e:
        print(f"Warnung: Konnte alten Freigabe-Bereich nicht löschen: {e}")

    # Schreiben (minütlich)
    written = 0
    for ts_ms, _price in prices:
        val = 1 if ts_ms in chosen_set else 0
        try:
            post_point(UUIDS["Freigabe_EMob"], ts_ms, val)
            written += 1
        except Exception as e:
            print(f"Warnung: POST @ {ts_ms} fehlgeschlagen: {e}")

    print(f"Freigabe geschrieben (Minuten): {written} – davon aktiv: {len(chosen_set)}")

    # Stundenmittel (lokale Stunden) berechnen & ausgeben
    # Baue eine Map hour_start_local -> (sum, count)
    hourly: Dict[datetime, Tuple[int, int]] = {}
    minute = 60_000
    for ts_ms, _price in prices:
        val = 1 if ts_ms in chosen_set else 0
        dt_loc = datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).astimezone(tz)
        hour_key = dt_loc.replace(minute=0, second=0, microsecond=0)
        s, c = hourly.get(hour_key, (0, 0))
        hourly[hour_key] = (s + val, c + 1)

    print("\n=== Stundenmittel Freigabe_EMob (lokal) ===")
    for h in sorted(hourly.keys()):
        s, c = hourly[h]
        avg = s / c if c else 0.0
        print(f"{h.strftime('%Y-%m-%d %H:%M %Z')}  ->  {avg:.3f}")


# =========================
# CLI / Main
# =========================
def main():
    global DEBUG, TRACE_ENERGY

    parser = argparse.ArgumentParser(description="Freigabe E-Mob nach günstigsten Minuten bis 05:00 lokal planen.")
    parser.add_argument("--debug", action="store_true", help="Debug-Ausgaben")
    parser.add_argument("--trace-energy", action="store_true", help="Trapez-Integration debuggen")
    parser.add_argument("--max-kwh", type=float, default=MAX_LADUNG_KWH, help="Ziel-Ladeenergie [kWh]")
    parser.add_argument("--kw", type=float, default=LADELEISTUNG_KW, help="Ladeleistung [kW]")
    parser.add_argument("--lookback", type=int, default=MAX_LOOKBACK_MIN, help="Lookback für letzten 1-Zustand (Min)")
    args = parser.parse_args()

    DEBUG = args.debug
    TRACE_ENERGY = args.trace_energy

    tz = ch_tz()
    now_local = datetime.now(tz)

    # 1) Zeitpunkt der letzten "1" auf Cable_State
    last_ts = find_last_ts_equal(UUIDS["Cable_State"], target_value=1, lookback_min=args.lookback)
    if last_ts is None:
        print("⚠️  Kein letzter Einsteck-Zeitpunkt gefunden – setze Freigabe komplett auf 0 bis 05:00.")
        from_local = now_local.replace(second=0, microsecond=0)
        to_local = next_5_local(now_local)
        plan_and_write(from_local, to_local, minutes_needed=0)
        return

    last_dt_utc = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc)
    print(f"Letzte '1' auf Cable_State: {fmt_ts(last_ts)}")

    # 2) Energie seit last_ts
    kwh_since = energy_kwh_from_power_between(UUIDS["Emob_Cons"], last_ts, to="now")
    print(f"Energie seit letzter Ladung: {kwh_since:.3f} kWh")

    # 3) Fehlende Energie & Ladezeit (auf 15min aufrunden)
    kwh_min = args.max_kwh - kwh_since
    print(f"Ziel Max_Ladung: {args.max_kwh:.3f} kWh  ->  Fehlend: {kwh_min:.3f} kWh")

    from_local = now_local.replace(second=0, microsecond=0)
    to_local = next_5_local(now_local)

    if kwh_min <= 0:
        print("Bereits ≥ Zielenergie geladen – schreibe überall 0 bis 05:00.")
        plan_and_write(from_local, to_local, minutes_needed=0)
        return

    minutes_raw = (kwh_min / args.kw) * 60.0
    minutes_need = ceil_to_step_minutes(minutes_raw, step=RUND_MINUTEN)
    print(f"Benötigte Ladezeit: roh={minutes_raw:.1f} min  ->  gerundet={minutes_need} min (Schritt {RUND_MINUTEN})")

    # 4) Preise holen, günstigste Minuten wählen & schreiben
    plan_and_write(from_local, to_local, minutes_needed=minutes_need)


if __name__ == "__main__":
    main()
