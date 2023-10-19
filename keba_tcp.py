import requests
import json
import pprint
import datetime
import logging
import pytz
import time
import struct
from pymodbus.client.sync import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

#######################################################################################################
# Configuration
UUID = {
    "P_Home_Bilanz": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "P_Home_Verbrauch": "85ffa8d0-683e-11ee-9486-113294e4804d",
    "P_PV_Anlage": "0ece9080-6732-11ee-92bb-d5c31bcb9442",
    "P_Warmepumpe": "1b029800-6732-11ee-ae2e-9715cbeba615",
    "P_Aktiv": "6cb255a0-6e5f-11ee-b899-c791d8058d25",
    "I_Lade": "6e768290-6e5e-11ee-bd91-fd7700aa25ee",
    "Switch": "d9d09d00-6e5e-11ee-8a40-53ee17720f6a",
    "Power_F": "ac06a530-6e5f-11ee-b968-65b0d8af2151",
    
}

server_ip = "192.168.178.59"
server_port = 502
unit_id = 255
charge_state= 1000
char_curr_1 = 1008
active_p = 1020
vol_ph = 1040
switch = 1550


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
    # Create a Modbus TCP client
    client = ModbusTcpClient(server_ip, port=server_port)

    # Connect to the Modbus device
    client.connect()
   
    # Read a single register (function code 3 - Read Holding Registers)
    char_state_unpars = client.read_holding_registers(charge_state, 2, unit=1)
    char_state_pars = BinaryPayloadDecoder.fromRegisters(char_state_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    char_state_val = char_state_pars.decode_32bit_uint()


    switch_unpars = client.read_holding_registers(switch, 4, unit=1)
    switch_pars = BinaryPayloadDecoder.fromRegisters(switch_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    switch_val = char_state_pars.decode_32bit_uint()
    
    print(f"Charge State: {char_state_val}")
    print(f"Switch State: {switch_val}")
       
    #write_vals(UUID["F_Schnell"], val_home)

      









#--------------
    
    # Create a Modbus TCP client
    #client = ModbusTcpClient(modbus_host, port=modbus_port)

    # Connect to the Modbus device
    #client.connect()


    
    #try:
        # Read the registers as a block
        #res_pv = client.read_input_registers(ser_num, count=8, unit=unit_id)
        #res_bil = client.read_input_registers(reg_bil, count=2, unit=unit_id)
        #res_wp = client.read_input_registers(reg_wp, count=2, unit=unit_id)

        #print(res_pv)
        # Extract the values from the response
        #val_pv = res_pv.registers
        #val_bil = res_bil.registers
        #val_wp = res_wp.registers

        # Combine the two registers into a single byte string
        #byte_string_pv = struct.pack('>HH', val_pv[0], val_pv[1])
        #byte_string_bil = struct.pack('>HH', val_bil[0], val_bil[1])
        #byte_string_wp = struct.pack('>HH', val_wp[0], val_wp[1])
        
        # Unpack the byte string as a signed integer (big-endian)
        #parsed_val_pv = int((struct.unpack('>i', byte_string_pv)[0])/100*-1)
        #if parsed_val_pv <= 0:
        #    parsed_val_pv = 0
        #else:
        #    parsed_val_pv = parsed_val_pv        
        #parsed_val_bil = int((struct.unpack('>i', byte_string_bil)[0])/100)
        #parsed_val_wp = int((struct.unpack('>i', byte_string_wp)[0])/100)
        #val_home = parsed_val_bil+parsed_val_pv
        #if parsed_val_pv <= 0:
        #    val_eiv = 0
        #elif parsed_val_bil > 0:
        #    val_eiv = parsed_val_pv
        #else:
        #    val_eiv = val_home
            
        # Print the parsed integer
        #print(f"Parsed Integer PV: {parsed_val_pv}")
        #print(f"Parsed Integer Bil: {parsed_val_bil}")
        #print(f"Parsed Integer WP: {parsed_val_wp}")
        #print(f"Value Home: {val_home}")
        #print(f"Value EIV: {val_eiv}")
        
   

    #write_vals(UUID["P_Home_Bilanz"], parsed_val_bil)
    #write_vals(UUID["P_Home_Verbrauch"], val_home)
    #write_vals(UUID["P_PV_Anlage"], parsed_val_pv)
    #write_vals(UUID["P_Warmepumpe"], parsed_val_wp)    
    #write_vals(UUID["P_EIV"], val_eiv) 
     
if __name__ == "__main__":
    main()
    
