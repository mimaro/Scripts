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
    "Volumenstrom": "41084bd0-6522-11ee-920f-d32bfefe5b1f",
    "RL_WP": "7c634270-6522-11ee-b368-f7dd1ec956fb",
    "VL_WP": "a2b81400-6522-11ee-bd47-039fc6f8c20c",
    "BWW_unten": "c19c6e00-6522-11ee-9a6c-b7d9e43c93c8",
    "T_ist_Heizgruppe": "d9ad7d10-6522-11ee-bcaa-e7b07cee865b",
    "Puffer_oben": "59bd6680-6523-11ee-b354-998ee384c361",
    "T_SOLL_BWW": "82392af0-6523-11ee-876f-d3acf6a8c4a0",
    "T_SOLL_HK2": "911a3ea0-6523-11ee-8114-1fa309bb814a",
    "T_SOLL_HK1": "a2197880-6523-11ee-88a3-950f5e8f1efc",
    "Betriebszustand": "b8b10bd0-6523-11ee-910d-a13553f16887",
    "P_WP_Therm": "69630320-6522-11ee-9e09-ebb553e47b70",
    "P_WP_Therm_WW": "8cfcadb0-73dc-11ee-b8cf-3975a73c8c72",
    "P_WP_Therm_RW": "89a4f3c0-73dc-11ee-8979-a74a73d32bc5"
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
P_WP_therm = Volumenstrom * 1.16 * (T_vl_wp_ist - T_rl_wp_ist) * 1000

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
write_vals(UUID["VL_WP"], T_vl_wp_ist)
write_vals(UUID["RL_WP"], T_rl_wp_ist)
write_vals(UUID["Volumenstrom"], Volumenstrom)
write_vals(UUID["BWW_unten"], T_ww_ist)
write_vals(UUID["T_ist_Heizgruppe"], T_vl_hk2_ist)
write_vals(UUID["Puffer_oben"], T_vl_hk1_ist)
write_vals(UUID["T_SOLL_BWW"], T_ww_soll)
write_vals(UUID["T_SOLL_HK2"], T_vl_hk2_soll)
write_vals(UUID["T_SOLL_HK1"], T_vl_hk1_soll)
write_vals(UUID["P_WP_Therm"], P_WP_therm)

if betriebszustand == 5:
    write_vals(UUID["P_WP_Therm_WW"], P_WP_therm)
    write_vals(UUID["P_WP_Therm_RW"], 0)
else:
    write_vals(UUID["P_WP_Therm_WW"], 0)
    write_vals(UUID["P_WP_Therm_RW"], P_WP_therm)
  



