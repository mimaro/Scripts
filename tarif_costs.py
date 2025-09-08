import requests
import json
import pprint
import datetime
import logging
import pytz
import time
from datetime import datetime, timedelta

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
SUNSET_URL = 'https://api.sunrise-sunset.org/json?lat=47.386479&lng=8.252473&formatted=0' 

########################################################################################################



#######################################################################################################
# Configuration
UUID = {
    "Brutto_Energie": "85ffa8d0-683e-11ee-9486-113294e4804d",
    "Netto_Energie": "8d8af7c0-8c8a-11f0-9d28-a9c875202312",
    "Preis_dyn": "a1547420-8c87-11f0-ab9a-bd73b64c1942",
    "Kosten_b_d": "72161320-8c87-11f0-873f-79e6590634b2",
    "Kosten_b_e": "42e29fa0-8c87-11f0-a699-831fc5906f38",
    "Kosten_n_d": "18f74440-8c8c-11f0-948b-013fcbd37465",
    "Kosten_n_e": "132713a0-8c8c-11f0-96f2-dfda5706e0e8",
    
}




###########################################################################################################

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

def get_data(uuid, duration="-15min"):
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url)
    r.raise_for_status()
    return r.json()

def get_last_quarter(uuid):
    now = datetime.now()

    # Minute auf das letzte Viertel runden
    minute_block = (now.minute // 15) * 15
    block_start = now.replace(minute=minute_block, second=0, microsecond=0)
    block_end = block_start + timedelta(minutes=15)

    # Unix-Timestamps
    start_ts = int(block_start.timestamp())
    end_ts = int(block_end.timestamp())

    return get_data(uuid, start=start_ts, end=end_ts)

def main():

    #Energie exkl PV letzte 15 Minuten Abfragen
    brutto_energie = get_last_quarter(UUID["Brutto_Energie"]),["data"]["consumption"]/60


    #Energie inkl PV letzte 15 Minuten Abfragen
    netto_energie = get_vals(UUID["Netto_Energie"], duration="-15min")["data"]["consumption"]/60

    preis_einh = 27.129
    preis_dyn = get_vals(UUID["Preis_dyn"], duration="-15min")["data"]["average"]

    print(preis_dyn)
    print(preis_einh)
    print(brutto_energie)
    print(netto_energie)

    kosten_b_d = brutto_energie * preis_dyn/100
    kosten_b_e = brutto_energie * preis_einh/100
    kosten_n_d = netto_energie * preis_dyn/100
    kosten_n_e = netto_energie * preis_einh/100

    print(kosten_b_d)
    print(kosten_b_e)
    print(kosten_n_d)
    print(kosten_n_e)

    write_vals(UUID["Kosten_b_d"], (kosten_b_d))
    write_vals(UUID["Kosten_b_e"], (kosten_b_e))
    write_vals(UUID["Kosten_n_d"], (kosten_n_d))
    write_vals(UUID["Kosten_n_e"], (kosten_n_e))


if __name__ == "__main__":
    main()
