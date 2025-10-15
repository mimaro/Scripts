#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import datetime
import logging
import pytz
import time
import math
from collections import deque

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
#######################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "P_WP_PV_min_Forecast": "2ef42c20-9abb-11f0-9cfd-ad07953daec6",
    "P_el_WP_Forecast":     "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "T_Aussen_Forecast":    "c56767e0-97c1-11f0-96ab-41d2e85d0d5f",
    "Freigabe_WP_Opt":      "f76b26f0-a9fd-11f0-a7d7-5958c376a670"
}
#######################################################################################################

def get_vals(uuid, duration="-0min"):
    """Daten von VZ lesen (JSON)."""
    req = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    req.raise_for_status()
    return req.json()

def write_vals(uuid, val):
    """Daten ohne expliziten Zeitstempel auf VZ schreiben (Serverzeit) – immer als Integer."""
    ival = int(val)
    poststring = VZ_POST_URL.format(uuid, ival)
    postreq = requests.post(poststring, timeout=10)
    return postreq.ok

def write_vals_at(uuid, val, ts_epoch_sec):
    """
    Daten mit explizitem Zeitstempel (Sekunden seit Epoch) auf VZ schreiben.
    Wert wird explizit als Integer übertragen.
    """
    ival = int(val)
    tse = int(ts_epoch_sec)
    poststring = VZ_POST_URL.format(uuid, ival) + f"&ts={tse}"
    postreq = requests.post(poststring, timeout=10)
    return postreq.ok

# ------------------------- Zeitstempel-Helfer (Fix für ms vs. s) -------------------------

def _normalize_epoch_seconds(ts_any) -> int:
    """
    Nimmt Zeitstempel in Sek. oder ms (int/float/str) entgegen und liefert Sekunden (int) zurück.
    """
    t = float(ts_any)
    # Heuristik: > 1e12 => Millisekunden
    if abs(t) > 1e12:
        t = t / 1000.0
    return int(t)

def _from_epoch_seconds(ts_sec: int, tz) -> datetime.datetime:
    """
    Epoch-Sekunden -> Aware datetime in gewünschter TZ (UTC-Epoche -> TZ).
    Vermeidet platform time_t Limits von fromtimestamp.
    """
    epoch_utc = datetime.datetime(1970, 1, 1, tzinfo=pytz.UTC)
    dt_utc = epoch_utc + datetime.timedelta(seconds=int(ts_sec))
    return dt_utc.astimezone(tz)

def to_hour_start(ts_epoch_any, tz):
    """
    Nimmt Sek. oder ms entgegen, normalisiert auf Sekunden, rundet auf Stundenbeginn.
    Rückgabe: Epoch-Sekunden (int) des Stundenanfangs in TZ.
    """
    ts_sec = _normalize_epoch_seconds(ts_epoch_any)
    dt = _from_epoch_seconds(ts_sec, tz)
    dt_hour = dt.replace(minute=0, second=0, microsecond=0)
    return int(dt_hour.timestamp())

def build_hourly_dict(tuples, tz, agg="last"):
    """
    Aggregiert Roh-Tuples [ts, value] stundenweise.
    agg: "last" (letzter Wert der Stunde) oder "avg" (Durchschnitt der Stunde)
    Rückgabe: Dict {hour_epoch_sec: value}
    """
    buckets = {}
    sums = {}
    counts = {}
    for t in tuples:
        if not t or len(t) < 2:
            continue
        val = t[1]
        if val is None:
            continue

        ts_sec = _normalize_epoch_seconds(t[0])
        v = float(val)
        h = to_hour_start(ts_sec, tz)

        if agg == "avg":
            sums[h] = sums.get(h, 0.0) + v
            counts[h] = counts.get(h, 0) + 1
            buckets[h] = sums[h] / counts[h]
        else:  # "last"
            buckets[h] = v
    return buckets

# -----------------------------------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)

    test = get_vals(UUID["Freigabe_WP_Opt"], duration="now&to=+900min")["data"]
    tuples_test = test.get("tuples", [])
    print(tuples_test)
    
    # Abfragen durchschnittliche Aufnahmeleistung WP (PV-Minutenleistung) für die nächsten 15h (+900 min)
    data_wp = get_vals(UUID["P_WP_PV_min_Forecast"], duration="now&to=+900min")["data"]
    tuples_wp = data_wp.get("tuples", [])

    values_over10 = [t[1] for t in tuples_wp if len(t) > 1 and t[1] is not None and float(t[1]) > 10.0]
    if values_over10:
        p_pv_wp_min = sum(values_over10) / len(values_over10)
    else:
        p_pv_wp_min = None  # kein sinnvolles PV-Potenzial vorhanden

    # Abfragen elektrischer Energiebedarf WP (Tagesdurchschnitt / Vorhersage)
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="0min")["data"]["average"]

    # Schutz vor Division durch 0/None
    if not p_pv_wp_min or p_pv_wp_min <= 0:
        logging.warning("Kein PV-Potenzial > 10 gefunden. Setze Freigabe für alle Stunden in den nächsten 15h auf 0.")
        start_hour = now.replace(minute=0, second=0, microsecond=0)
        for i in range(15):
            ts_hour = start_hour + datetime.timedelta(hours=i)
            ok = write_vals_at(UUID["Freigabe_WP_Opt"], int(0), ts_hour.timestamp())
            logging.info(f"Freigabe_WP_Opt {ts_hour.isoformat()} -> 0 (ok={ok})")
        logging.info("********************************")
        return

    # Berechnung Betriebsstunden am Tag (Anzahl Stunden)
    hour_wp_betrieb = p_el_wp_bed / p_pv_wp_min
    n_betriebsstunden = max(0, int(round(hour_wp_betrieb)))

    # Abfragen Aussentemperaturen nächste 15 h
    data_temp = get_vals(UUID["T_Aussen_Forecast"], duration="now&to=+900min")["data"]
    tuples_temp = data_temp.get("tuples", [])

    logging.info("PV Potenzial heute: {}".format(p_pv_wp_min))
    logging.info("Durschnittlicher Leistungsbedarf WP: {}".format(p_el_wp_bed))
    logging.info("Betriebsstunden (berechnet): {:.2f} -> {} h".format(hour_wp_betrieb, n_betriebsstunden))

    # 1) Stunden (nächste 15h) bestimmen, in denen PV-Prognose > 10 ist
    wp_by_hour   = build_hourly_dict(tuples_wp,   tz, agg="last")  # {hour_epoch: value}
    temp_by_hour = build_hourly_dict(tuples_temp, tz, agg="last")  # {hour_epoch: temperature}

    start_hour_dt = now.replace(minute=0, second=0, microsecond=0)
    next15_hours = [int((start_hour_dt + datetime.timedelta(hours=i)).timestamp()) for i in range(15)]

    eligible_hours = [h for h in next15_hours if wp_by_hour.get(h, float("-inf")) > 10.0]

    # 2) Innerhalb dieser Stunden die wärmsten N (N = n_betriebsstunden) suchen
    selected_hot_hours = set()

    if n_betriebsstunden == 0:
        selected_hot_hours = set()
    elif n_betriebsstunden >= len(eligible_hours):
        # Sonderfall: mehr benötigte Stunden als verfügbar -> alle Stunden mit PV>10 werden 1 (andere 0)
        selected_hot_hours = set(eligible_hours)
    else:
        # nach Temperatur sortieren (absteigend)
        sortable = []
        for h in eligible_hours:
            temp = temp_by_hour.get(h, float("-inf"))  # fehlende Temps ans Ende
            sortable.append((h, temp))
        sortable.sort(key=lambda x: x[1], reverse=True)

        # Temperaturgrenze am Cut ermitteln (Gleichstände komplett einschließen)
        cutoff_temp = sortable[n_betriebsstunden - 1][1]
        for h, t in sortable:
            if t >= cutoff_temp:
                selected_hot_hours.add(h)

    # 3) Für alle Stunden in den nächsten 15h 1/0 setzen und mit Zeitstempel schreiben (immer Integer)
    for h in next15_hours:
        val = 1 if h in selected_hot_hours else 0
        ival = int(val)
        ok = write_vals_at(UUID["Freigabe_WP_Opt"], ival, h)
        dt = _from_epoch_seconds(h, tz)
        logging.info(f"Freigabe_WP_Opt {dt.isoformat()} -> {ival} (ok={ok})")

    logging.info("********************************")

if __name__ == "__main__":
    main()
