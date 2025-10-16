#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import datetime
import logging
import pytz
import time
import math
from collections import defaultdict

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
#######################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "Tarif_Kosten":        "a1547420-8c87-11f0-ab9a-bd73b64c1942",
    "Forecast_COP":        "31877e20-9aaa-11f0-8759-733431a03535",
    "P_WP_Max":            "46e21920-9ab9-11f0-9359-d3451ca32acb",
    "E_WP_Max":            "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "E_WP":                "a9017680-73dc-11ee-9767-9f1216ff8467",
    "Freigabe_WP_Nacht":   "3bacbde0-aa05-11f0-a053-6bf3625dc510"
}
#######################################################################################################

def get_vals(uuid, duration="-0min"):
    """Daten von vz lesen (JSON)."""
    req = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    req.raise_for_status()
    return req.json()

def write_vals(uuid, val):
    """Daten ohne expliziten Zeitstempel auf vz schreiben (Serverzeit)."""
    ival = int(val)  # sicherstellen: Integer
    url = VZ_POST_URL.format(uuid, ival)
    postreq = requests.post(url, timeout=10)
    if not postreq.ok:
        logging.error("POST failed (server time): %s %s", postreq.status_code, postreq.text)
    else:
        logging.debug("POST ok (server time): %s", postreq.text)
    return postreq.ok

def write_vals_at(uuid, val, ts_epoch_sec):
    """
    Daten mit explizitem Zeitstempel auf vz schreiben.
    WICHTIG: Volkszähler erwartet ts i.d.R. in MILLISEKUNDEN!
    """
    ival = int(val)  # sicherstellen: Integer (0/1)
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

# ---------- Zeitstempel-Helper (robust gegen ms/sek) ----------

def _normalize_epoch_seconds(ts_any) -> int:
    """Nimmt Zeitstempel in Sek./ms (int/float/str) und liefert Epoch-Sekunden (int)."""
    t = float(ts_any)
    if abs(t) > 1e12:  # Heuristik: ms
        t = t / 1000.0
    return int(t)

def _from_epoch_seconds(ts_sec: int, tz) -> datetime.datetime:
    """Epoch-Sekunden -> Aware datetime in Ziel-TZ (ohne platform time_t Limits)."""
    epoch_utc = datetime.datetime(1970, 1, 1, tzinfo=pytz.UTC)
    dt_utc = epoch_utc + datetime.timedelta(seconds=int(ts_sec))
    return dt_utc.astimezone(tz)

def to_hour_start(ts_any, tz) -> int:
    """Zeitstempel (sek/ms) auf Stundenanfang runden und als Epoch-Sekunden zurückgeben."""
    ts_sec = _normalize_epoch_seconds(ts_any)
    dt = _from_epoch_seconds(ts_sec, tz)
    dt_hour = dt.replace(minute=0, second=0, microsecond=0)
    return int(dt_hour.timestamp())

# --------------------------------------------------------------

def main():
    logging.basicConfig(level=logging.INFO)  # für mehr Details: logging.DEBUG
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)
    logging.info("Swiss time: {}".format(now.isoformat()))
    logging.info("*****************************")

    ###############################
    # Berechne verbleibende Betriebszeit (hour_wp)

    e_wp      = get_vals(UUID["E_WP"],      duration="-720min&to=now")["data"]["consumption"]
    e_wp_max  = get_vals(UUID["E_WP_Max"],  duration="-720min")["data"]["average"]
    p_wp_avg  = get_vals(UUID["P_WP_Max"],  duration="now&to=+720min")["data"]["average"]

    e_wp_bil  = e_wp_max - e_wp
    # Schutz vor 0/negativ/None
    if not p_wp_avg or p_wp_avg <= 0:
        logging.warning("p_wp_avg ist ungültig (<=0). Setze hour_wp=0.")
        hour_wp = 0.0
    else:
        hour_wp = max(0.0, e_wp_bil / p_wp_avg)

    logging.info("Prognose Verbrauch (E_WP_Max): {}".format(e_wp_max))
    logging.info("Bisheriger Verbrauch (E_WP): {}".format(e_wp))
    logging.info("Thermische Bilanz: {}".format(e_wp_bil))
    logging.info("Durschnittliche Leistungsaufnahme (P_WP_Max): {}".format(p_wp_avg))  
    logging.info("Verbleibende Betriebszeit (hour_wp): {:.2f} h".format(hour_wp))

    ##############################
    # Berechne günstigsten Produktionsmoment Nacht:
    # tarif/cop nach identischen Zeitstempeln, dann stundenweise mitteln, 12h betrachten

    # Rohdaten (nächste 12 Stunden)
    tarif = get_vals(UUID["Tarif_Kosten"],  duration="now&to=+720min")["data"]
    cop   = get_vals(UUID["Forecast_COP"],  duration="now&to=+720min")["data"]

    tuples_tarif = tarif.get("tuples", []) or []
    tuples_cop   = cop.get("tuples",   []) or []

    # Dicts: exakt gleiche Zeitstempel -> Werte
    tarif_by_ts = {}
    for t in tuples_tarif:
        if not t or len(t) < 2 or t[1] is None:
            continue
        ts = _normalize_epoch_seconds(t[0])
        try:
            tarif_by_ts[ts] = float(t[1])
        except:
            continue

    cop_by_ts = {}
    for t in tuples_cop:
        if not t or len(t) < 2 or t[1] is None:
            continue
        ts = _normalize_epoch_seconds(t[0])
        try:
            cop_by_ts[ts] = float(t[1])
        except:
            continue

    # Intersektion identischer Zeitstempel
    common_ts = sorted(set(tarif_by_ts.keys()) & set(cop_by_ts.keys()))

    # Division pro identischem Zeitstempel
    ratio_by_ts = {}
    for ts in common_ts:
        cop_val = cop_by_ts.get(ts, None)
        tarif_val = tarif_by_ts.get(ts, None)
        if cop_val is None or tarif_val is None:
            continue
        if cop_val <= 0:
            # Division durch 0/negativ vermeiden
            continue
        ratio_by_ts[ts] = tarif_val / cop_val

    # Stundenfenster definieren (12h ab vollem Stundenbeginn)
    start_hour_dt = now.replace(minute=0, second=0, microsecond=0)
    end_hour_dt   = start_hour_dt + datetime.timedelta(hours=12)
    next12_hours  = [int((start_hour_dt + datetime.timedelta(hours=i)).timestamp()) for i in range(12)]
    last_hour_end = int(end_hour_dt.timestamp())

    # *** Wichtig: vor dem Schreiben alle zukünftigen Werte im Zielbereich löschen ***
    logging.info("Lösche vorhandene zukünftige Werte [%s, %s] ...",
                 start_hour_dt.isoformat(), end_hour_dt.isoformat())
    delete_ok = delete_range(UUID["Freigabe_WP_Nacht"], start_hour_dt.timestamp(), end_hour_dt.timestamp())
    if not delete_ok:
        logging.warning("Löschen des Zielbereichs fehlgeschlagen – schreibe trotzdem weiter.")

    if not ratio_by_ts:
        logging.warning("Keine gültigen tarif/cop-Paare für die nächsten 12h gefunden. Schreibe 0 für alle Stunden.")
        # 0 für die nächsten 12 Stunden schreiben (explizit int) – ts in ms
        for h in next12_hours:
            ok = write_vals_at(UUID["Freigabe_WP_Nacht"], 0, h)
            logging.info(f"Freigabe_WP_Nacht {_from_epoch_seconds(h, tz).isoformat()} -> 0 (ok={ok})")
        logging.info("********************************")
        return

    # ratio_by_ts auf die nächsten 12 Stunden beschränken
    ratio_by_ts_12h = {ts: v for ts, v in ratio_by_ts.items() if next12_hours[0] <= ts < last_hour_end}

    # Stündliche Aggregation (Durchschnitt je Stunde)
    sums = defaultdict(float)
    counts = defaultdict(int)
    for ts, r in ratio_by_ts_12h.items():
        h = to_hour_start(ts, tz)
        sums[h] += r
        counts[h] += 1
    hourly_ratio = {}
    for h in next12_hours:
        if counts[h] > 0:
            hourly_ratio[h] = sums[h] / counts[h]
        else:
            hourly_ratio[h] = float("inf")  # keine Daten in der Stunde -> extrem teuer

    # Werte für die nächsten 12 Stunden in der Konsole ausgeben
    logging.info("Tarif/COP (stündlicher Mittelwert) für die nächsten 12 Stunden:")
    for h in next12_hours:
        dt = _from_epoch_seconds(h, tz)
        val = hourly_ratio[h]
        s = "keine Daten" if math.isinf(val) else f"{val:.6f}"
        logging.info(f"  {dt.isoformat()} -> {s}")

    # hour_wp Stunden mit den niedrigsten Werten auswählen
    n_hours = max(0, int(round(hour_wp)))  # als Anzahl ganze Stunden

    # Erzeuge sortierbare Liste (h, val), unendliche Werte kommen ans Ende
    sortable = [(h, hourly_ratio[h]) for h in next12_hours]
    sortable.sort(key=lambda x: (math.isinf(x[1]), x[1]))  # erst echte Zahlen aufsteigend, dann inf

    selected_hours = set()
    if n_hours <= 0:
        selected_hours = set()
    elif n_hours >= len(next12_hours):
        selected_hours = set(next12_hours)
    else:
        cutoff_val = sortable[n_hours - 1][1]
        for h, v in sortable:
            # alle Stunden <= cutoff (inkl. Gleichstand)
            if v <= cutoff_val:
                selected_hours.add(h)

    # Schreiben: ausgewählte Stunden -> 1, andere -> 0 (immer Integer) – ts in ms
    for h in next12_hours:
        val = 1 if (h in selected_hours and not math.isinf(hourly_ratio[h])) else 0
        ok = write_vals_at(UUID["Freigabe_WP_Nacht"], val, h)  # h in Sekunden; Funktion konvertiert zu ms
        dt = _from_epoch_seconds(h, tz)
        logging.info(f"Freigabe_WP_Nacht {dt.isoformat()} -> {int(val)} (ok={ok})")

    logging.info("********************************")

if __name__ == "__main__":
    main()
