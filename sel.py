import requests
import json
import pprint
import datetime
import logging
import pytz
import time
import struct
from pymodbus.client.sync import ModbusTcpClient

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
    "P_Wärmepumpe": "1b029800-6732-11ee-ae2e-9715cbeba615",
    "P_EIV": "96d53fc0-683f-11ee-bd3d-c5441b8ec095"
}

modbus_host = "192.168.178.40"
modbus_port = 1502
unit_id = 1
reg_pv= 0
reg_bil = 10
reg_wp = 20
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
    client = ModbusTcpClient(modbus_host, port=modbus_port)

    # Connect to the Modbus device
    client.connect()

    try:
        # Read the registers as a block
        res_pv = client.read_input_registers(reg_pv, count=2, unit=unit_id)
        res_bil = client.read_input_registers(reg_bil, count=2, unit=unit_id)
        res_wp = client.read_input_registers(reg_wp, count=2, unit=unit_id)

        # Extract the values from the response
        val_pv = res_pv.registers
        val_bil = res_bil.registers
        val_wp = res_wp.registers

        # Combine the two registers into a single byte string
        byte_string_pv = struct.pack('>HH', val_pv[0], val_pv[1])
        byte_string_bil = struct.pack('>HH', val_bil[0], val_bil[1])
        byte_string_wp = struct.pack('>HH', val_wp[0], val_wp[1])
        
        # Unpack the byte string as a signed integer (big-endian)
        parsed_val_pv = int((struct.unpack('>i', byte_string_pv)[0])/100*-1)
        parsed_val_bil = int((struct.unpack('>i', byte_string_bil)[0])/100)
        parsed_val_wp = int((struct.unpack('>i', byte_string_wp)[0])/100)
        val_home = parsed_val_bil+parsed_val_pv
        if parsed_val_pv <= 0:
            val_eiv = 0
        elif parsed_val_bil > 0:
            val_eiv = parsed_val_pv
        else:
            val_eiv = val_home
            
        # Print the parsed integer
        print(f"Parsed Integer PV: {parsed_val_pv}")
        print(f"Parsed Integer Bil: {parsed_val_bil}")
        print(f"Parsed Integer WP: {parsed_val_wp}")
        print(f"Value Home: {val_home}")
        print(f"Value EIV: {val_eiv}")
        
    finally:
        # Close the Modbus connection
        client.close()

    write_vals(UUID["P_Home_Bilanz"], parsed_val_bil)
    write_vals(UUID["P_Home_Verbrauch"], val_home)
    write_vals(UUID["P_PV_Anlage"], parsed_val_pv)
    write_vals(UUID["P_Wärmepumpe"], parsed_val_wp)    
    write_vals(UUID["P_EIV"], val_eiv) 
     
if __name__ == "__main__":
    main()
    


