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

########################################################################################################


#######################################################################################################
# Configuration
UUID = {
    "P_WP_PV_min_Forecast": "2ef42c20-9abb-11f0-9cfd-ad07953daec6",
    "P_el_WP_Forecast": "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "T_Aussen_Forecast": "c56767e0-97c1-11f0-96ab-41d2e85d0d5f"
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

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)

    p_pv_wp_min = get_vals(UUID["P_WP_PV_min_Forecast"], duration="now&to=+720min")["data"]["average"]
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="0min")["data"]["average"]
    
    hour_wp_betrieb = p_el_wp_bed / p_pv_wp_min

    
    logging.info("PV Potenzial heute: {}".format(p_pv_wp_min))
    logging.info("Durschnittlicher Leistungsbedarf WP: {}".format(p_el_wp_bed))
    logging.info("Betriebsstunden heute: {}".format(hour_wp_betrieb))
   

    

    
    
    
    ###############################################################################

        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
