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
    "T_outdoor": "308e0d90-6521-11ee-8b08-a34757253caf",
    "Power_balance": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "Charge_station": "8270f520-6690-11e9-9272-4dde30159c8f",
    "t_Sperrung_Tag": "3ee81940-6525-11ee-ab8d-95d8fe8c84c1",
    "t_Sperrung_Sonnenuntergang": "48d326e0-6525-11ee-bb62-d9a673cf575c",
    "t_Verzoegerung_Tag": "525c79d0-6525-11ee-a4de-35b9b54b853f",
    "Freigabe_WP": "2dd47740-6525-11ee-8430-33ffcdf1f22e",
    "Sperrung_WP": "35a4c530-6525-11ee-9aab-7be80c763665",
    "Freigabe_normalbetrieb": "1f9b1a00-6525-11ee-a1c0-218fa15dedcf",
    "PV_Produktion": "0ece9080-6732-11ee-92bb-d5c31bcb9442", 
    "WP_Verbrauch": "1b029800-6732-11ee-ae2e-9715cbeba615",
    "T_Raum_EG": "716e8d00-6523-11ee-a6d5-958aeed3d121",
    "T_Raum_OG": "78afd3c0-6523-11ee-980e-9fe998eb4bc6",
    "WW_Temp_mitte": "adf0da80-6522-11ee-82a3-4fe8ca3dfa5c",
    "Puffer_Temp_oben": "59bd6680-6523-11ee-b354-998ee384c361",
    "T_Absenk_F": "65bf3760-6cc2-11ee-a9fc-972ab9d69e77",
    "WW_Time": "24fb6470-7423-11ee-a18e-514019c4b69a",
    "WW_Ein": "54ce3e80-7423-11ee-8ce6-bbd29c465ad6",
    "Steigung_HK": "1ad2ca90-becb-11ef-870c-3f013969b33b",
    "T_Puffer_unten": "6832c0e0-6523-11ee-9722-2d954a0be504",
    "T_VL_HK2": "d9ad7d10-6522-11ee-bcaa-e7b07cee865b",
    "S_FREIGABE_KÜHLEN": "21eb5f90-76ef-11f0-be2d-11efc51999be",
    "T_Raum_OG_puffer": "82ba5d00-77b5-11f0-acfb-7d514a443171",
    "T_Speicher_unten_puffer": "3fa7fe90-77b6-11f0-a27b-15bfbc6c5533",
    "T_Taupunkt": "75ec5620-799b-11f0-8232-61256c1dc79b"
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

