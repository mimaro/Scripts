import requests
import json
import pprint
import datetime
import logging
import pytz
from pymodbus.client.sync import ModbusTcpClient
#from pymodbus.constants import Endian
#from pymodbus.payload import BinaryPayloadDecoder
#from pymodbus.payload import BinaryPayloadBuilder

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "WR_Limit": "abba6be0-8380-11f1-85b4-c593342e551b",
    "Bilanz": "e3fc7a80-6731-11ee-8571-5bf96a498b43"
}

REGISTER = {
    "WR_LIMIT" : 502   
}

IP_ISG = "192.168.178.20"

CLIENT = ModbusTcpClient(IP_ISG)
CLIENT.connect()
Error = 0
############################################################################################################

def get_vals(uuid, duration="-0min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()


def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    print("POST:", poststring)
    try:
        postreq = requests.post(poststring, timeout=10)
        print("Status:", postreq.status_code)
        print("OK?:", postreq.ok)
        print("Antworttext:", postreq.text[:500])  # erste 500 Zeichen
    except Exception as e:
        print("Exception beim POST:", e)



    logging.info(f"----------------WR-Limitierung--------------------")



    
    CLIENT.write_register(REGISTER["WR_LIMIT"], 5000)
    
    write_vals(UUID["WR_Limit"], 50)


    CLIENT.close()
  
 logging.info("********************************")
    


