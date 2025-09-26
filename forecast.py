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
    "P_PV_Forecast": "abcf6600-97c1-11f0-9348-db517d4efb8f",
    "P_el_WP_Forecast": "58cbc600-9aaa-11f0-8a74-894e01bd6bb7",
    "COP_Forecast": "31877e20-9aaa-11f0-8759-733431a03535"

    
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

    p_pv_prod = get_vals(UUID["P_PV_Forecast"], duration="now&to=+720min")["data"]["consumption"]/1000
    p_el_wp_bed = get_vals(UUID["P_el_WP_Forecast"], duration="+720min&to=+2160min")["data"]["consumption"]/1000


    

    
    ###############################################################################

        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
