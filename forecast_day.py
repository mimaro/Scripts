import requests
import json
import pprint
import datetime
import logging
import pytz
import time
import math
# from typing import List, Tuple   # (optional) nur falls du wirklich Typisierungen brauchst
from pymodbus.client.sync import ModbusTcpClient
from collections import deque

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "P_WP_PV_min_Forecast": "2ef42c20-9abb-11f0-9cfd-ad07953daec6",
    "P_el_WP_Forecast": "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "T_Aussen_Forecast": "c56767e0-97c1-11f0-96ab-41d2e85d0d5f",
    "Freigabe_WP_Opt": "f76b26f0-a9fd-11f0-a7d7-5958c376a670"
}
    
###########################################################################################################

def get_vals(uuid, duration="-0min"):
    # Daten von vz lesen. 
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()

def write_vals(uuid, val):
    # (Kompatibilität) Daten ohne Zeitstempel auf vz schreiben – nutzt Serverzeit.
    poststring = VZ_POST_URL.format(uuid, val)
    postreq = requests.post(poststring)

def write_vals_at(uuid, val, ts_epoch):
    """
    Daten mit explizitem Zeitstempel (Sekunden seit Epoch) auf vz schreiben.
    Viele VZ-Installationen akzeptieren &ts=<epoch_seconds> zusätzlich.
    """
    poststring = VZ_POST_URL.format(uuid, val) + f"&ts={int(ts_epoch)}"
    postreq = requests.post(poststring)
    return postreq.ok

def to_hour_start(ts_epoch, tz):
    """Rundet einen Epoch-Zeitstempel auf den jeweiligen Stundenbeginn in der angegebenen TZ."""
    dt = datetime.datetime.fromtimestamp(ts_epoch, tz=tz)
    dt_hour = dt.replace(minute=0, second=0, microsecond=0)
    return int(dt_hour.timestamp())

def build_hourly_dict(tuples, tz, agg="last"):
    """
    Aggregiert Roh-Tuples [ts, value] stundenweise.
    agg: "last" (letzter Wert der Stunde) oder "avg" (Durchschnitt der Stunde)
    """
    buckets = {}
    sums = {}
    counts = {}
    for t in tuples:
        if not t or len(t) < 2 or t[1] is None:
            continue
        ts = int(t[0])
        v  = float(t[1])
        h  = to_hour_start(ts, tz)
        if agg == "avg":
            sums[h] = sums.get(h, 0.0) + v
            counts[h] = counts.get(h, 0) + 1
            buckets[h] = sums[h] / counts[h]
        else:
            # "last": immer den letzten gesehenen Wert der Stunde übernehmen
            buckets[h] = v
    return buckets

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)

    # Abfragen durchschnittliche Aufnahmeleistung WP am Tag (nächste 12h)
    data_wp = get_vals(UUID["P_WP_PV_min_Forecast"], duration="now&to=+720min")["data"]
    tuples_wp = data_wp.get("tuples", [])
    values_over10 = [t[1] for t in tuples_wp if len(t) > 1 and t[1] is not None and t[1] > 10]

    if values_over10:  # Nur wenn es überhaupt Werte > 10 gibt
        p_pv_wp_min = sum(values_over10) / len(values_over10)
    else:
        p_pv_wp_min = None  # kein sinnvolles PV-Potenzial vorhanden

    # Abfragen elektrischer Energiebedarf WP Tag
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="0min")["data"]["average"]

    # Guard: keine Division durch 0 / None
    if not p_pv_wp_min or p_pv_wp_min <= 0:
        logging.warning("Kein PV-Potenzial >10 gefunden. Setze Freigabe für alle Stunden in den nächsten 12h auf 0.")
        # Trotzdem sichere 0en für die nächsten 12h schreiben (zur Transparenz)
        start_hour = now.replace(minute=0, second=0, microsecond=0)
        for i in range(12):
            ts_hour = start_hour + datetime.timedelta(hours=i)
            ok = write_vals_at(UUID["Freigabe_WP_Opt"], 0, ts_hour.timestamp())
            logging.info(f"Freigabe_WP_Opt {ts_hour.isoformat()} -> 0 (ok={ok})")
        logging.info("********************************")
        return

    # Berechnung Betriebsstunden am Tag
    hour_wp_betrieb = p_el_wp_bed / p_pv_wp_min  # Stundenzahl (kann fractional sein)
    # Als ganze Stunden interpretieren – Rundung gemäß Vorgabe "Anzahl der Stunden"
    n_betriebsstunden = max(0, int(round(hour_wp_betrieb)))

    # Abfragen Aussentemperaturen nächste 12 h
    data_temp = get_vals(UUID["T_Aussen_Forecast"], duration="now&to=+720min")["data"]
    tuples_temp = data_temp.get("tuples", [])

    logging.info("PV Potenzial heute: {}".format(p_pv_wp_min))
    logging.info("Durschnittlicher Leistungsbedarf WP: {}".format(p_el_wp_bed))
    logging.info("Betriebsstunden (berechnet): {:.2f} -> {} h".format(hour_wp_betrieb, n_betriebsstunden))

    # 1) Stunden (in den nächsten 12h) bestimmen, in denen PV-Prognose > 10 ist
    wp_by_hour = build_hourly_dict(tuples_wp, tz, agg="last")     # {hour_epoch: value}
    temp_by_hour = build_hourly_dict(tuples_temp, tz, agg="last") # {hour_epoch: temperature}

    start_hour_dt = now.replace(minute=0, second=0, microsecond=0)
    next12_hours = [int((start_hour_dt + datetime.timedelta(hours=i)).timestamp()) for i in range(12)]

    eligible_hours = [h for h in next12_hours if wp_by_hour.get(h, -1) > 10]

    # 2) Innerhalb dieser Stunden die wärmsten N (N = n_betriebsstunden) suchen
    selected_hot_hours = set()

    if n_betriebsstunden == 0:
        # Keine Betriebsstunden -> alles 0
        pass
    elif n_betriebsstunden >= len(eligible_hours):
        # Sonderfall: mehr benötigte Stunden als verfügbar -> alle Stunden mit PV>10 werden 1
        selected_hot_hours = set(eligible_hours)
    else:
        # Normale Auswahl: nach Temperatur sortieren (absteigend)
        # Falls Temperatur für eine Stunde fehlt, -inf, damit diese zuletzt kommt
        sortable = []
        for h in eligible_hours:
            temp = temp_by_hour.get(h, float("-inf"))
            sortable.append((h, temp))
        # Absteigend nach Temperatur
        sortable.sort(key=lambda x: x[1], reverse=True)

        # Temperatur-Grenze am Cut ermitteln, damit "alle Stunden auf welche das zutrifft" (gleiches Max) gewählt werden
        cutoff_temp = sortable[n_betriebsstunden-1][1]
        for h, t in sortable:
            if t >= cutoff_temp:
                selected_hot_hours.add(h)

        # Achtung: Es können dadurch mehr als N werden (bei Gleichstand). Das ist so gewünscht.

    # 3) Für alle Stunden in den nächsten 12h 1/0 setzen und mit Zeitstempel schreiben
    #    - Stunden in selected_hot_hours -> 1
    #    - sonst 0
    #    - Sonderfall (oben) ist bereits in selected_hot_hours abgebildet
    for h in next12_hours:
        val = 1 if h in selected_hot_hours else 0
        ok = write_vals_at(UUID["Freigabe_WP_Opt"], val, h)
        dt = datetime.datetime.fromtimestamp(h, tz)
        logging.info(f"Freigabe_WP_Opt {dt.isoformat()} -> {val} (ok={ok})")

    logging.info("********************************")

if __name__ == "__main__":
    main()
