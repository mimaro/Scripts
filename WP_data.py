import requests
import json
import pprint
import datetime
import logging
import pytz
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

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
CLIENT.connect()
############################################################################################################

#HK1_Temp = CLIENT.read_input_registers(506, count=1, unit=1)
#print(HK1_Temp)

result = CLIENT.read_holding_registers(1500, count=1)
t = result.registers
print(t)

#CLIENT.write_register(REGISTER["Komfort_HK1"], int(200))
