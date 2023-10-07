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
    "Aussentemp": "308e0d90-6521-11ee-8b08-a34757253caf",
    "Volumenstrom": "e4179ff0-1e25-11e9-a9d1-7bc1d2c119b6",
    "RL_WP": "05a40bc0-1e26-11e9-aebb-51a6700848c1",
    "VL_WP": "a9d47be0-2ec6-11e9-8ccd-33ffc3253237",
    "BWW_unten": "b27589b0-1cab-11e9-a06d-43024133319c",
    "Puffer_oben": "88b7c280-1cab-11e9-938e-fb5dc04c61d4",
    "T_SOLL_BWW": "48cfb7f0-2ec7-11e9-8cb6-d3fb38afd2fe",
    "T_SOLL_HK2": "5bb70670-2ec6-11e9-9ef5-b1cdc3699fde",
    "T_SOLL_HK1": "dc9651b0-2ec5-11e9-8946-93157542391a",
    "Betriebszustand": "a15ab220-1d5a-11e9-9dd4-57fe91d5c03b"
}

REGISTER = {
    "Aussentemp" : 506,
    "T_VL_HK1_ist" : 507, 
    "T_VL_HK1_soll" : 509, 
    "T_VL_HK2_ist": 510, 
    "T_VL_HK2_soll" : 511,
    "T_VL_WP_ist": 542,
    "T_RL_WP_ist" : 541,
    "Volumenstrom" : 520,
    "T_WW_ist": 521,
    "T_WW_soll": 522,
    "Betriebsart": 1500   
}

IP_ISG = "192.168.178.36"

CLIENT = ModbusTcpClient(IP_ISG)
CLIENT.connect()
############################################################################################################

def get_vals(uuid, duration="-0min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    #logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    #logging.info("Ok? {}".format(postreq.ok))
  
#Vorlage read input registers
T_outdoor = (CLIENT.read_input_registers(REGISTER["Aussentemp"], count=1, unit=1).getRegister(0))/10
T_vl_wp_ist = (CLIENT.read_input_registers(REGISTER["T_VL_WP_ist"], count=1, unit=1).getRegister(0))/10
T_rl_wp_ist = (CLIENT.read_input_registers(REGISTER["T_RL_WP_ist"], count=1, unit=1).getRegister(0))/10
T_vl_hk1_ist = (CLIENT.read_input_registers(REGISTER["T_VL_HK1_ist"], count=1, unit=1).getRegister(0))/10
T_vl_hk1_soll = (CLIENT.read_input_registers(REGISTER["T_VL_HK1_soll"], count=1, unit=1).getRegister(0))/10
T_vl_hk2_ist = (CLIENT.read_input_registers(REGISTER["T_VL_HK2_ist"], count=1, unit=1).getRegister(0))/10
T_vl_hk2_soll = (CLIENT.read_input_registers(REGISTER["T_VL_HK2_soll"], count=1, unit=1).getRegister(0))/10
T_ww_ist = (CLIENT.read_input_registers(REGISTER["T_WW_ist"], count=1, unit=1).getRegister(0))/10
T_ww_soll = (CLIENT.read_input_registers(REGISTER["T_WW_soll"], count=1, unit=1).getRegister(0))/10
Volumenstrom = (CLIENT.read_input_registers(REGISTER["Volumenstrom"], count=1, unit=1).getRegister(0))/100000*60
P_WP_therm = Volumenstrom * 1.16 * (T_vl_wp_ist - T_rl_wp_ist)

print(f"T_outdoor= {T_outdoor} ")
print(f"T_vl_wp_ist = {T_vl_wp_ist}")
print(f"T_rl_wp_ist = {T_rl_wp_ist}")
print(f"T_vl_hk1_ist = {T_vl_hk1_ist}")
print(f"T_vl_hk1_soll = {T_vl_hk1_soll}")
print(f"T_vl_hk2_ist = {T_vl_hk2_ist}")
print(f"T_vl_hk2_soll = {T_vl_hk2_soll}")
print(f"T_WW_ist= {T_ww_ist}")
print(f"T_WW_soll= {T_ww_soll}")
print(f"Volumenstrom = {Volumenstrom}")
print(f"P_WP_therm = {P_WP_therm}")

#Vorlage read holding registers
#value_2 = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)
#print("Aussentemperatur= " + value_2)

#Auslesen Betriebszustand aus ISG und Schreiben auf vz
betriebszustand = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)

if betriebszustand == 1:
    print("Betriebszustand:", "Bereitschaftsbetrieb")
elif betriebszustand == 2:
    print("Betriebszustand:", "Programmbetrieb")
elif betriebszustand == 3:
    print("Betriebszustand:", "Komfortbetrieb")
elif betriebszustand == 4:
    print("Betriebszustand:", "Eco-Betrieb")
elif betriebszustand == 5:
    print("Betriebszustand:", "Warmwasserbetrieb")    
    
write_vals(UUID["Betriebszustand"], betriebszustand)
write_vals(UUID["Aussentemp"], T_outdoor)

    



