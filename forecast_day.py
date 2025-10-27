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

# Mindest-PV-Leistung in Watt, ab der die WP laufen darf.
# Durch einfaches Ändern dieses Werts (z.B. 400, 800, ...) steuerst du die Freigabelogik.
PV_MIN_THRESHOLD_W = 500.0
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
    if not postreq.ok:
        logging.error("POST failed (server time): %s %s", postreq.status_code, postreq.text)
    else:
        logging.debug("POST ok (server time): %s", postreq.text)
    return postreq.ok

def write_vals_at(uuid, val, ts_epoch_sec):
    """
    Daten mit explizitem Zeitstempel auf VZ schreiben.
    WICHTIG: Volkszähler erwartet ts i.d.R. in MILLISEKUNDEN!
    """
    ival = int(val)  # sicherstellen: Integer 0/1
    ts_ms = int(ts_epoch_sec * 1000)  # Sekunden -> Millisekunden
    url = VZ_POST_URL.format(uuid, ival) + f"&ts={ts_ms}"
    postreq = requests.post(url, timeout=10)
    if not postreq.ok:
        logging.error("POST failed: %s %s", postreq.status_code, postreq.text)
    else:
        logging.debug("POST ok: %s", postreq.text)
    return postreq.ok

def delete_range(uuid, from_epoch_sec, to_epoch_sec):
    """
    Löscht alle Werte im Bereich [from, to] (inklusive) beim gegebenen Kanal.
    Erwartet Sekunden, API benötigt Millisekunden.
    """
    f_ms = int(from_epoch_sec * 1000)
    t_ms = int(to_epoch_sec * 1000)
    url = f"http://192.168.178.49/middleware.php/data/{uuid}.json?operation=delete&from={f_ms}&to={t_ms}"
    r = requests.post(url, timeout=10)
    if not r.ok:
        logging.error("DELETE failed: %s %s", r.status_code, r.text)
    else:
        logging.debug("DELETE ok: %s", r.text)
    return r.ok

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
    logging.basicConfig(level=logging.INFO)  # für mehr Details: logging.DEBUG
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)

    # Abfragen durchschnittliche Aufnahmeleistung WP (PV-Minutenleistung) für die nächsten 15h (+900 min)
    data_wp = get_vals(UUID["P_WP_PV_min_Forecast"], duration="now&to=+900min")["data"]
    tuples_wp = data_wp.get("tuples", [])

    # Mittelwert nur über Werte, die >= PV_MIN_THRESHOLD_W sind
    values_over_threshold = [
        t[1] for t in tuples_wp
        if len(t) > 1 and t[1] is not None and float(t[1]) >= PV_MIN_THRESHOLD_W
    ]
    if values_over_threshold:
        p_pv_wp_min = sum(values_over_threshold) / len(values_over_threshold)
    else:
        p_pv_wp_min = None  # kein sinnvolles PV-Potenzial vorhanden oberhalb der Schwelle

    # Abfragen elektrischer Energiebedarf WP (Tagesdurchschnitt / Vorhersage)
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="0min")["data"]["average"]

    # Stundenfenster definieren (15h ab vollem Stundenbeginn)
    start_hour_dt = now.replace(minute=0, second=0, microsecond=0)
    end_hour_dt   = start_hour_dt + datetime.timedelta(hours=15)
    next15_hours  = [int((start_hour_dt + datetime.timedelta(hours=i)).timestamp()) for i in range(15)]

    # *** WICHTIG: Vor dem Schreiben alle zukünftigen Werte im Zielbereich löschen ***
    logging.info("Lösche vorhandene zukünftige Werte [%s, %s] ...",
                 start_hour_dt.isoformat(), end_hour_dt.isoformat())
    delete_ok = delete_range(UUID["Freigabe_WP_Opt"], start_hour_dt.timestamp(), end_hour_dt.timestamp())
    if not delete_ok:
        logging.warning("Löschen des Zielbereichs fehlgeschlagen – schreibe trotzdem weiter.")

    # Falls kein PV-Potenzial oberhalb der Schwelle vorhanden ist -> überall 0 schreiben
    if not p_pv_wp_min or p_pv_wp_min <= 0:
        logging.warning(
            "Kein PV-Potenzial >= %.1f W gefunden. Setze Freigabe für alle Stunden in den nächsten 15h auf 0.",
            PV_MIN_THRESHOLD_W
        )
        # Debug-Ausgabe der PV-Prognose je Stunde trotzdem ausgeben
        wp_by_hour_debug = build_hourly_dict(tuples_wp, tz, agg="last")
        for h in next15_hours:
            dt = _from_epoch_seconds(h, tz)
            pv_watt = wp_by_hour_debug.get(h, None)
            logging.info(
                "Stunde %s | PV-Forecast: %s W -> Freigabe 0 (kein ausreichendes Potenzial)",
                dt.isoformat(),
                f"{pv_watt:.1f}" if pv_watt is not None else "n/a"
            )

        for h in next15_hours:
            ok = write_vals_at(UUID["Freigabe_WP_Opt"], 0, h)  # ts->ms inside
            logging.info(
                "Freigabe_WP_Opt %s -> 0 (ok=%s)",
                _from_epoch_seconds(h, tz).isoformat(), ok
            )
        logging.info("********************************")
        return

    # Berechnung Betriebsstunden am Tag (Anzahl Stunden)
    hour_wp_betrieb = p_el_wp_bed / p_pv_wp_min
    n_betriebsstunden = max(0, int(round(hour_wp_betrieb)))

    # Abfragen Aussentemperaturen nächste 15 h
    data_temp = get_vals(UUID["T_Aussen_Forecast"], duration="now&to=+900min")["data"]
    tuples_temp = data_temp.get("tuples", [])

    logging.info("PV Potenzial heute (>= %.1f W): %s", PV_MIN_THRESHOLD_W, p_pv_wp_min)
    logging.info("Durschnittlicher Leistungsbedarf WP: {}".format(p_el_wp_bed))
    logging.info("Betriebsstunden (berechnet): {:.2f} -> {} h".format(hour_wp_betrieb, n_betriebsstunden))

    # 1) Stunden (nächste 15h) bestimmen, in denen PV-Prognose >= PV_MIN_THRESHOLD_W ist
    wp_by_hour   = build_hourly_dict(tuples_wp,   tz, agg="last")  # {hour_epoch: value}
    temp_by_hour = build_hourly_dict(tuples_temp, tz, agg="last")  # {hour_epoch: temperature}

    eligible_hours = [
        h for h in next15_hours
        if wp_by_hour.get(h, float("-inf")) >= PV_MIN_THRESHOLD_W
    ]

    # Debug: PV Forecast je Stunde + Eligibility + Temperatur
    logging.info("----- Stunden-Check PV-Forecast / Temp / Eligibility -----")
    for h in next15_hours:
        dt = _from_epoch_seconds(h, tz)
        pv_watt = wp_by_hour.get(h, None)
        temp_degC = temp_by_hour.get(h, None)
        eligible = (h in eligible_hours)
        logging.info(
            "Stunde %s | PV-Forecast: %s W | T_außen: %s °C | PV>=%.0fW? %s",
            dt.isoformat(),
            f"{pv_watt:.1f}" if pv_watt is not None else "n/a",
            f"{temp_degC:.1f}" if temp_degC is not None else "n/a",
            PV_MIN_THRESHOLD_W,
            "JA" if eligible else "nein"
        )

    # 2) Innerhalb dieser Stunden die wärmsten N (N = n_betriebsstunden) suchen
    selected_hot_hours = set()
    if n_betriebsstunden == 0:
        selected_hot_hours = set()
    elif n_betriebsstunden >= len(eligible_hours):
        selected_hot_hours = set(eligible_hours)
    else:
        sortable = []
        for h in eligible_hours:
            temp = temp_by_hour.get(h, float("-inf"))  # fehlende Temps ans Ende
            sortable.append((h, temp))
        sortable.sort(key=lambda x: x[1], reverse=True)
        cutoff_temp = sortable[n_betriebsstunden - 1][1]
        for h, t in sortable:
            if t >= cutoff_temp:
                selected_hot_hours.add(h)

    # 3) Für alle Stunden in den nächsten 15h 1/0 setzen und mit Zeitstempel schreiben (ts in ms)
    for h in next15_hours:
        val = 1 if h in selected_hot_hours else 0
        dt = _from_epoch_seconds(h, tz)
        pv_watt = wp_by_hour.get(h, None)

        logging.info(
            "Schreibe Stunde %s | PV-Forecast: %s W | Freigabe -> %d",
            dt.isoformat(),
            f"{pv_watt:.1f}" if pv_watt is not None else "n/a",
            val
        )

        ok = write_vals_at(UUID["Freigabe_WP_Opt"], val, h)  # h in Sekunden; Funktion konvertiert zu ms
        logging.info(
            "Freigabe_WP_Opt %s -> %d (ok=%s)",
            dt.isoformat(), val, ok
        )

    logging.info("********************************")

if __name__ == "__main__":
    main()
