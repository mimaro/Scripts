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
    "COP_Forecast": "31877e20-9aaa-11f0-8759-733431a03535",
    "WP_el_Max": 	"46e21920-9ab9-11f0-9359-d3451ca32acb"

    
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

    opt_solar = 0 

    p_pv_wp_min = get_vals(UUID["P_WP_PV_min_Forecast"], duration="now&to=+720min")["data"]["consumption"]/1000
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="+720min&to=+2160min")["data"]["consumption"]/1000
    wp_el_max_tag = get_vals(UUID["P_PV_Forecast"], duration="now&to=+720min")["data"]["average"]
    
    cop_tag = get_vals(UUID["COP_Forecast"], duration="now&to=+720min")["data"]["average"]
    cop_nacht = get_vals(UUID["COP_Forecast"], duration="+720min&to=+1440min")["data"]["average"]


    
    logging.info("PV Produktion heute: {}".format(p_pv_wp_min))
    logging.info("El. Bedarf WP morgen: {}".format(p_el_wp_bed))
    logging.info("Max el WP Leistung Tag: {}".format(wp_el_max_tag))
    logging.info("COP Tag: {}".format(cop_tag))
    logging.info("COP Nacht: {}".format(cop_nacht))

    

    
    
    
    ###############################################################################

        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
