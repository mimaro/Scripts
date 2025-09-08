import requests
import json
import pprint
import datetime
import logging
import pytz
import time
from pymodbus.client.sync import ModbusTcpClient
from collections import deque

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
    "Netto_Energie": "e3fc7a80-6731-11ee-8571-5bf96a498b43"
    
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

def main():

    #Energie exkl PV letzte 15 Minuten Abfragen
    brutto_energie = get_vals(UUID["Brutto_Energie"], duration="-15min")["data"]["consumption"]

    #Energie inkl PV letzte 15 Minuten Abfragen
    netto_energie = get_data(UUID["Netto_Energie"], duration="-15min")["data"]

    energie = 0
    for ts, p, _ in netto_energie:
        if p > 0:
            energie += p / 60

    
    
    print(brutto_energie)
    print(netto_energie)



    
if __name__ == "__main__":
    main()
