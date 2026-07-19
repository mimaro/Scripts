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
    "WR_Limit": "abba6be0-8380-11f1-85b4-c593342e551b"
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


#def write_vals(uuid, val):
#    poststring = VZ_POST_URL.format(uuid, val)
#    #logging.info("Poststring {}".format(poststring))
#    postreq = requests.post(poststring)
#    #logging.info("Ok? {}".format(postreq.ok))

#Vorlage read input registers
#raw_value = CLIENT.read_input_registers(REGISTER["Aussentemp"], count=1, unit=1).getRegister(0)
#signed_value = raw_value if raw_value < 32768 else raw_value - 65536
#T_outdoor = signed_value / 10

#if T_outdoor > 100:
#    T_outdoor = get_vals(UUID["Aussentemp"], duration="-5min")["data"]["average"]
#    Error = 1
#else:
#T_outdoor = T_outdoor
#T_vl_wp_ist = (CLIENT.read_input_registers(REGISTER["T_VL_WP_ist"], count=1, unit=1).getRegister(0))/10

CLIENT.write_register(REGISTER["WR_LIMIT"], 5000)
    
write_vals(UUID["WR_Limit"], 50)


CLIENT.close()
  


