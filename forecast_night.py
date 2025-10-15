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
    "Tarif_Kosten": "a1547420-8c87-11f0-ab9a-bd73b64c1942",
    "Forecast_COP":  "31877e20-9aaa-11f0-8759-733431a03535",
    "P_WP_Max": "46e21920-9ab9-11f0-9359-d3451ca32acb",
    "E_WP_Max": "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "E_WP": "a9017680-73dc-11ee-9767-9f1216ff8467",
    "Freigabe_WP_Nacht": "3bacbde0-aa05-11f0-a053-6bf3625dc510"
}
#######################################################################################################

def get_vals(uuid, duration="-0min"):
    # Daten von vz lesen. 
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()

def write_vals(uuid, val):
    # Daten auf vz schreiben.
    poststring = VZ_POST_URL.format(uuid, val)
    #logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    #logging.info("Ok? {}".format(postreq.ok))

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)
    logging.info("Swiss time: {}".format(now))
    logging.info("*****************************")

    e_wp = get_vals(UUID["E_WP_Max"], duration="-720min")["data"]["consumption"]
    e_wp_max = get_vals(UUID["E_WP_Max"], duration="-720min")["data"]["average"]

    e_wp_bil = e_wp_max - e_wp







    
    logging.info("Thermische Bilanz: {}".format(w_wp_bil))
  

    logging.info("********************************")

if __name__ == "__main__":
    main()
