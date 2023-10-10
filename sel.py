import requests
import json
import pprint
import datetime
import logging
import pytz
import time
from pymodbus.client.sync import ModbusTcpClient

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

#######################################################################################################
# Configuration
UUID = {
    "P_Wagenrain_8a": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "P_PV-Anlage": "0ece9080-6732-11ee-92bb-d5c31bcb9442",
    "P_Wärmepumpe": "1b029800-6732-11ee-ae2e-9715cbeba615"
}

REGISTER = {
    "P_PV_Anlage": 10,
    "E_PV_Anlage": 1502,
    "P_Wagenrain_8a": 1503,
    "E_Wagenrain_8a": 1504,
    "P_Wärmepumpe": 1505,
    "E_Wärmepumpe": 1506
}

SEL_IP = "192.168.178.40"
SEL_PORT = 1502

CLIENT = ModbusTcpClient(SEL_IP,SEL_PORT)
CLIENT.connect()
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
   
  
#Vorlage read input registers
#p_pv_anlage = CLIENT.read_input_registers(REGISTER["P_PV_Anlage"]).getRegister(0)
p_pv_anlage = CLIENT.read_input_registers(REGISTER["P_PV_Anlage"], count=1, unit=1).getRegister(3)
print(p_pv_anlage)

#print(f"T_outdoor= {T_outdoor} ")

#Vorlage read holding registers
#p_pv_anlage_2 = CLIENT.read_holding_registers(0, count=1, unit= 1).getRegister(0)
#print(p_pv_anlage_2)

#Auslesen Betriebszustand aus ISG und Schreiben auf vz
#betriebszustand = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)
 
    
#write_vals(UUID["Betriebszustand"], betriebszustand)

