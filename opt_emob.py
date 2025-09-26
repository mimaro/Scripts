#!/usr/bin/env python3
import re
import requests
from datetime import datetime, timedelta, timezone
import json
import argparse
from typing import Any, Iterable, List, Tuple, Optional, Dict
import statistics
import math

# Neu: DST-sichere Zeitzone
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
VZ_POST_URL = BASE_URL + "/data/{}.json"                        # POST mit params

UUIDS = {
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State":   "58163cf0-95ff-11f0-b79d-252564addda6",
    "Emob_Cons":     "6cb255a0-6e5f-11ee-b899-c791d8058d25",   # Leistungs-/Energiekanal
    "Energy_Price":  "a1547420-8c87-11f0-ab9a-bd73b64c1942",   # CHF/kWh
}

MAX_MINUTES = 4320      # 72h Lookback für die Suche nach dem letzten 1er
TARGET_VALUE = 1
VALUE_COLUMN_INDEX = 1  # primäre Spalte (1 oder 2)
AUTO_FALLBACK_TO_OTHER_COLUMN = True
DEBUG = False
TRACE_ENERGY = False

Max_Ladung = 20  # maximale Ladeenergie in kWh

LOCAL_TZ = "Europe/Zurich"

# =========================
# Debug/Helper
# =========================
def _d(msg: str):
    if DEBUG:
        print(msg)

def fmt_ts(ms: int) -> str:
    try:
        dt = datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z")
    except Exception:
        return str(ms)

def _summary_stats(vals: List[float]) -> str:
    if not vals:
        return "n=0"
    try:
        q = statistics.quantiles(vals, n=4)
        return f"n={len(vals)}, min={min(vals):.3f}, p25={q[0]:.3f}, median={statistics.median(vals):.3f}, p75={q[-1]:.3f}, max={max(vals):.3f}, mean={statistics.fmean(vals):.3f}"
    except Exception:
        return f"n={len(vals)}, min={min(vals):.3f}, max={max(vals):.3f}, mean≈{sum(vals)/len(vals):.3f}"

def tz_loc():
    return ZoneInfo(LOCAL_TZ) if ZoneInfo else timezone.utc

def now_local():
    return datetime.now(tz_loc())

def next_morning_05_local(now_dt: datetime) -> datetime:
    """Nächstes 05:00 lokaler Zeit (heute 05:00 wenn wir davor sind, sonst morgen 05:00)."""
    if now_dt.hour < 5 or (now_dt.hour == 4 and now_dt.minute < 60):
        end = now_dt.replace(hour=5, minute=0, second=0, microsecond=0)
    else:
        end = (now_dt + timedelta(days=1)).replace(hour=5, minute=0, second=0, microsecond=0)
    return end

def to_utc_ms(dt_local: datetime) -> int:
    return int(dt_local.astimezone(timezone.utc).timestamp() * 1000)

def floor_to_minute(dt: datetime) -> datetime:
    return dt.replace(second=0, microsecond=0)

def align_to_quarter(dt: datetime) -> datetime:
    m = (dt.minute // 15) * 15
    return dt.replace(minute=m, second=0, microsecond=0)

def ceil_minutes_to_quarter(mins: int) -> int:
    return int(math.ceil(mins / 15.0) * 15)

# =========================
# HTTP
# =========================
def _get_json(url: str) -> Any:
    r = requests.get(url, timeout=10, headers={"Accept": "application/json"})
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

def post_point(uuid: str, ts_ms: int, value: int | float):
    params = {"operation": "add", "ts": str(int(ts_ms)), "value": str(value)}
    r = requests.post(VZ_POST_URL.format(uuid), params=params, timeout=10)
    if not r.ok:
        raise RuntimeError(f"POST failed {uuid}@{ts_ms}: {r.status_code} {r.text[:200]}")

# =========================
# Payload-Normalisierung
# =========================
def _normalize_sections(payload: Any):
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

def _debug_payload_shape(payload: Any, label: str):
    _d(f"[DEBUG] {label} type: {type(payload).__name__}")
    if isinstance(payload, dict):
        _d(f"[DEBUG] {label} keys: {list(payload.keys())}")
    elif isinstance(payload, list):
        _d(f"[DEBUG] {label} len: {len(payload)}; first type: {type(payload[0]).__name__ if payload else 'n/a'}")
    head = json.dumps(payload, ensure_ascii=False)[:600]
    _d(f"[DEBUG] {label} head: {head}{'...' if len(head)==600 else ''}")

def _debug_sample(sections, col_idx, label):
    recent = []
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > col_idx:
                recent.append((t[0], t[col_idx]))
    recent = recent[-10:]
    _d(f"[DEBUG] {label} – Spalte {col_idx}, letzte Punkte (ts_ms, val):")
    for ts, v in recent:
        _d(f"    {ts} ({fmt_ts(int(ts))}), {v}")

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
# Letzten Zeitpunkt finden, an dem target==1 war
# =========================
def find_last_ts_equal(uuid: str, target_value: int, lookback_min: int) -> Optional[int]:
    payload = get_vals(uuid, f"-{lookback_min}min")
    _debug_payload_shape(payload, "state-payload")
    sections = _normalize_sections(payload)
    _d(f"[DEBUG] sections erkannt: {len(sections)}")
    if sections:
        _d(f"[DEBUG] first section keys: {list(sections[0].keys())}")

    n, tmin, tmax = _sections_time_range(sections)
    if n:
        _d(f"[DEBUG] State-Zeitbereich: n={n}, first={tmin} ({fmt_ts(tmin)}), last={tmax} ({fmt_ts(tmax)})")

    if not sections:
        _d("[DEBUG] Keine sections/tuples gefunden.")
        return None

    last_ts_ms = None

    # Primärspalte
    _debug_sample(sections, VALUE_COLUMN_INDEX, "Primärversuch")
    for section in sections:
        for t in _iter_section_tuples(section):
            if len(t) > VALUE_COLUMN_INDEX and _cast_to_int(t[VALUE_COLUMN_INDEX]) == target_value:
                try:
                    ts_ms = int(t[0])
                    last_ts_ms = ts_ms if last_ts_ms is None or ts_ms > last_ts_ms else last_ts_ms
                except Exception:
                    pass

    # Fallback-Spalte
    if last_ts_ms is None and AUTO_FALLBACK_TO_OTHER_COLUMN and VALUE_COLUMN_INDEX in (1, 2):
        other = 2 if VALUE_COLUMN_INDEX == 1 else 1
        _debug_sample(sections, other, "Fallbackversuch")
        for section in sections:
            for t in _iter_section_tuples(section):
                if len(t) > other and _cast_to_int(t[other]) == target_value:
                    try:
                        ts_ms = int(t[0])
                        last_ts_ms = ts_ms if last_ts_ms is None or ts_ms > last_ts_ms else last_ts_ms
                    except Exception:
                        pass

    if last_ts_ms is None:
        _d("[DEBUG] kein Target-Wert innerhalb des Fensters gefunden")
        return None

    _d(f"[DEBUG] letzter Treffer target=={target_value}: {last_ts_ms} ({fmt_ts(last_ts_ms)})")
    return last_ts_ms

# =========================
# Energie: from=last_ts  bis to=now
# =========================
def _energy_debug_overview(tuples: List[list]):
    if not DEBUG:
        return
    if not tuples:
        _d("[DEBUG] ENERGY: keine Datenpunkte erhalten.")
        return
    ts = [int(t[0]) for t in tuples]
    p  = [float(t[1]) for t in tuples if len(t) >= 2]
    dts = [ (ts[i]-ts[i-1])/1000.0 for i in range(1, len(ts)) ]  # s
    _d(f"[DEBUG] ENERGY: tuples={len(tuples)}, range={fmt_ts(min(ts))} .. {fmt_ts(max(ts))}")
    _d(f"[DEBUG] ENERGY: Δt(s) stats -> {_summary_stats(dts)}")
    _d(f"[DEBUG] ENERGY: P(W) stats  -> {_summary_stats(p)} (all_zero={all(v==0 for v in p)})")
    _d("[DEBUG] ENERGY: letzte 5 Punkte (ts, iso, W):")
    for t in tuples[-5:]:
        try:
            _d(f"    {t[0]}  {fmt_ts(int(t[0]))}  {float(t[1])}")
        except Exception:
            _d(f"    {t}")

def energy_kwh_from_power_between(uuid: str, from_ts_ms: int, to: str = "now") -> float:
    if from_ts_ms is None:
        _d("[DEBUG] ENERGY: from_ts_ms=None -> 0 kWh")
        return 0.0

    payload = get_vals_between(uuid, str(int(from_ts_ms)), to)
    _debug_payload_shape(payload, "energy-payload")

    data = payload.get("data", [])
    data_obj = data if isinstance(data, dict) else (data[0] if isinstance(data, list) and data else {})

    # 1) consumption (Wh)
    if isinstance(data_obj, dict) and data_obj.get("consumption") is not None:
        try:
            cons_wh = float(data_obj["consumption"])
            return cons_wh / 1000.0
        except Exception:
            pass

    # Tuples einsammeln
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
    _energy_debug_overview(tuples)

    # 2) average * (to-from)
    if isinstance(data_obj, dict) and all(k in data_obj for k in ("average", "from", "to")):
        try:
            avg_w = float(data_obj["average"])
            dt_h  = (int(data_obj["to"]) - int(data_obj["from"])) / 3_600_000.0
            return (avg_w * dt_h) / 1000.0
        except Exception:
            pass

    # 3) Trapezregel
    if len(tuples) >= 2:
        energy_Wh = 0.0
        prev_ts = None
        prev_p  = None
        for tup in tuples:
            ts_ms = int(tup[0]); p_w = float(tup[1])
            if prev_ts is not None:
                dt_h = (ts_ms - prev_ts) / 3_600_000.0
                energy_Wh += 0.5 * (prev_p + p_w) * dt_h
            prev_ts, prev_p = ts_ms, p_w
        return energy_Wh / 1000.0

    return 0.0

# =========================
# Preisdaten holen und Slots wählen
# =========================
def load_price_tuples(uuid: str, start_ms: int, end_ms: int) -> List[Tuple[int, float]]:
    """Liest Preis-Tuples [ts_ms, value] aufsteigend sortiert, im Fenster [start,end]."""
    payload = get_vals_between(uuid, str(start_ms), str(end_ms))
    _debug_payload_shape(payload, "price-payload")
    sections = _normalize_sections(payload)
    out: List[Tuple[int, float]] = []
    for s in sections:
        for t in _iter_section_tuples(s):
            try:
                ts = int(t[0]); val = float(t[1])
                if start_ms <= ts < end_ms:
                    out.append((ts, val))
            except Exception:
                pass
    out.sort(key=lambda x: x[0])
    return out

def build_minute_prices_from_step_series(tuples_ts_val: List[Tuple[int, float]],
                                         start_ms: int, end_ms: int) -> Dict[int, float]:
    """
    Aus einer Schrittserie (ts,val) ein Minutenraster erstellen:
    Preis zu jeder Minute = letzter bekannter Wert (step-hold).
    """
    # Sicherstellen, dass wir immer einen Startwert haben
    series = list(tuples_ts_val)
    if not series or series[0][0] > start_ms:
        # vorherigen Wert holen (optional): hier lassen wir 'None' bis zum ersten Punkt
        pass
    # Cursor über die Serie laufen lassen
    minute_prices: Dict[int, float] = {}
    idx = 0
    current_val: Optional[float] = None
    for t in range(start_ms, end_ms, 60_000):
        while idx + 1 < len(series) and series[idx + 1][0] <= t:
            idx += 1
        if series:
            if series[idx][0] <= t:
                current_val = series[idx][1]
        if current_val is not None:
            minute_prices[t] = current_val
        else:
            # falls noch kein Preis: überspringen (nicht auswählen)
            minute_prices[t] = float("inf")
    return minute_prices

def pick_cheapest_quarters(minute_prices: Dict[int, float], required_minutes: int
                           ) -> set[int]:
    """
    Gruppiert Minuten in 15-Minuten-Slots (lokal aus TS ableitbar – TS ist UTC ms),
    bildet Slot-Durchschnitt und wählt die günstigsten N Slots
    (N = required_minutes / 15). Liefert die Menge der Slot-Startzeiten (UTC ms).
    """
    # Slot-Start = t auf nächste 15-Minuten-Grenze abrunden
    slots: Dict[int, List[float]] = {}
    for t_ms, price in minute_prices.items():
        # lokale Zeit nur zur Anzeige nötig – hier genügt UTC-Raster, da Slots 15-Minuten fest sind
        dt_utc = datetime.fromtimestamp(t_ms / 1000.0, tz=timezone.utc)
        slot_minute = (dt_utc.minute // 15) * 15
        slot_start = dt_utc.replace(minute=slot_minute, second=0, microsecond=0)
        slot_ms = int(slot_start.timestamp() * 1000)
        slots.setdefault(slot_ms, []).append(price)

    # Slot-Kosten (Durchschnitt)
    slot_avg: List[Tuple[int, float]] = []
    for s_ms, plist in slots.items():
        # 'inf' Preise rauswerfen
        vals = [p for p in plist if math.isfinite(p)]
        avg = (sum(vals) / len(vals)) if vals else float("inf")
        slot_avg.append((s_ms, avg))

    slot_avg.sort(key=lambda x: (x[1], x[0]))  # billigste zuerst

    n_slots = ceil_minutes_to_quarter(required_minutes) // 15
    chosen = {s for s, _ in slot_avg[:n_slots]}
    return chosen

# =========================
# CLI / Main
# =========================
def main():
    parser = argparse.ArgumentParser(description="Energie seit letztem target==1 (from=letzter 1er, to=now) + Ladefreigabe planen.")
    parser.add_argument("--target", type=int, default=TARGET_VALUE, help="Zielwert (Default: 1)")
    parser.add_argument("--state-uuid", type=str, default=UUIDS["Cable_State"], help="UUID des State-Kanals (Default: Cable_State)")
    parser.add_argument("--energy-uuid", type=str, default=UUIDS["Emob_Cons"], help="UUID des Leistungs-/Energiekanals (Default: Emob_Cons)")
    parser.add_argument("--lookback", type=int, default=MAX_MINUTES, help="Suchfenster in Minuten für target==1 (Default: 4320)")
    parser.add_argument("--debug", action="store_true", help="Debug-Ausgaben")
    parser.add_argument("--trace-energy", action="store_true", help="Trapez-Trace")
    parser.add_argument("--show-ts", action="store_true", help="Startzeitpunkt ISO und ms ausgeben")
    args = parser.parse_args()

    global DEBUG, TRACE_ENERGY
    DEBUG = args.debug
    TRACE_ENERGY = args.trace_energy

    # 1) Letzten Zeitpunkt ermitteln, an dem der State target==1 war
    last_ts = find_last_ts_equal(args.state_uuid, args.target, args.lookback)
    if last_ts is None:
        # Kompatible Ausgabe wie zuvor
        print("0")
        print("-0min")
        if args.show_ts:
            print("n/a")
        print("0")
        print("0.000 kWh")
        _d("[DEBUG] Abbruch: kein Startzeitpunkt gefunden.")
        return

    # 2) "Seit wann" (Minuten & -<min>min)
    last_dt = datetime.fromtimestamp(last_ts / 1000.0, tz=timezone.utc)
    now_utc = datetime.now(timezone.utc)
    diff_min = int((now_utc - last_dt).total_seconds() // 60)
    if diff_min < 0:
        diff_min = 0

    print(str(diff_min))
    print(f"-{diff_min}min")

    if args.show_ts:
        print(fmt_ts(last_ts))

    # 3) Energie von last_ts bis now über Emob_Cons
    kwh = energy_kwh_from_power_between(args.energy_uuid, last_ts, to="now")

    # 4) Roh-Timestamp (ms)
    print(str(last_ts))

    # 5) Endergebnis
    print(f"{kwh:.3f} kWh")

    ##########
    # Ladefreigabe
    ##########
    tz = tz_loc()
    now_loc = floor_to_minute(now_local())
    end_loc = next_morning_05_local(now_loc)
    start_ms = to_utc_ms(now_loc)
    end_ms   = to_utc_ms(end_loc)

    # Bedarf (kWh) und Ladezeit (auf 15-min aufrunden)
    kwh_min = Max_Ladung - kwh
    ladezeit_h = kwh_min / 7.0
    required_minutes = 0 if kwh_min <= 0 else ceil_minutes_to_quarter(int(math.ceil(ladezeit_h * 60.0)))

    print("\n===== Ladeplanung (Freigabe_EMob) =====")
    print(f"Jetzt (lokal): {now_loc.isoformat(' ', timespec='minutes')}")
    print(f"Fenster bis  : {end_loc.isoformat(' ', timespec='minutes')}")
    print(f"Max_Ladung   : {Max_Ladung:.3f} kWh, bereits geladen: {kwh:.3f} kWh → kwh_min={kwh_min:.3f} kWh")
    print(f"Benötigte Ladezeit (auf 15 min gerundet): {required_minutes} min")

    # Wenn kein Bedarf: alles 0 bis 05:00
    if required_minutes <= 0:
        print("Kein Ladebedarf → setze 0 für alle Minuten bis 05:00.")
        # Schreiben & Stundenmittel ausgeben
        hourly_bins: Dict[datetime, List[int]] = {}
        t = now_loc
        while t < end_loc:
            ts_ms = to_utc_ms(t)
            try:
                post_point(UUIDS["Freigabe_EMob"], ts_ms, 0)
            except Exception as e:
                _d(f"[WARN] write 0 @ {t}: {e}")
            hour_key = t.replace(minute=0, second=0, microsecond=0)
            hourly_bins.setdefault(hour_key, []).append(0)
            t += timedelta(minutes=1)
        print("\n— Stundenmittel Freigabe (lokal) —")
        for hk in sorted(hourly_bins.keys()):
            vals = hourly_bins[hk]
            avg = (sum(vals) / len(vals)) if vals else 0.0
            print(f"{hk.isoformat(' ', timespec='minutes')}  →  {avg:.3f}")
        return

    # Preise laden (von jetzt bis 05:00)
    price_tuples = load_price_tuples(UUIDS["Energy_Price"], start_ms, end_ms)
    if not price_tuples:
        print("⚠️  Keine Preisdaten erhalten – keine Freigabe gesetzt.")
        return

    # Minutenpreise (step-hold)
    minute_prices = build_minute_prices_from_step_series(price_tuples, start_ms, end_ms)

    # Günstigste 15-Minuten-Slots wählen
    chosen_slots = pick_cheapest_quarters(minute_prices, required_minutes)

    # Freigabe-Minuten (1 in gewählten Slots, sonst 0) schreiben
    hourly_bins: Dict[datetime, List[int]] = {}
    t = now_loc
    while t < end_loc:
        # Slot-Start (UTC) des aktuellen Minutenpunkts
        dt_utc = t.astimezone(timezone.utc)
        slot_min = (dt_utc.minute // 15) * 15
        slot_start_utc = dt_utc.replace(minute=slot_min, second=0, microsecond=0)
        slot_ms = int(slot_start_utc.timestamp() * 1000)

        val = 1 if slot_ms in chosen_slots else 0
        ts_ms = to_utc_ms(t)

        try:
            post_point(UUIDS["Freigabe_EMob"], ts_ms, val)
        except Exception as e:
            _d(f"[WARN] write {val} @ {t}: {e}")

        hour_key = t.replace(minute=0, second=0, microsecond=0)
        hourly_bins.setdefault(hour_key, []).append(val)

        t += timedelta(minutes=1)

    # Kontrolle: Stundenmittel ausgeben
    print("\n— Stundenmittel Freigabe (lokal) —")
    for hk in sorted(hourly_bins.keys()):
        vals = hourly_bins[hk]
        avg = (sum(vals) / len(vals)) if vals else 0.0
        print(f"{hk.isoformat(' ', timespec='minutes')}  →  {avg:.3f}")

if __name__ == "__main__":
    main()
