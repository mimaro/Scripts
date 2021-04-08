import requests
import json
import pprint
import datetime
import logging
import pytz
from pymodbus.client.sync import ModbusTcpClient

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "T_outdoor": "8f471ab0-1cab-11e9-8fa4-3b374d3c10ca"
}


REGISTER = {
    "Komfort_HK1": 1501,
    "Eco_HK1": 1502,
    "Steigung_HK1": 1503,
    "Komfort_HK2": 1504,
    "Eco_HK2": 1505,
    "Steigung_HK2": 1506, 
    "Betriebsart": 1500   
}

IP_ISG = "192.168.178.36"

CLIENT = ModbusTcpClient(IP_ISG)

############################################################################################################

#HK1_Temp = CLIENT.read_input_registers(506, count=1, unit=1)
#print(HK1_Temp)

value_1 = CLIENT.read_holding_registers(1500, count=1, unit=1)
print(value_1)
print response.getRegister(0) # This returns value of only one register
print response.registers[0:] #This returns the response for whole length of register

#CLIENT.write_register(REGISTER["Komfort_HK1"], int(200))
