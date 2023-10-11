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
    "P_Wagenrain_8a": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "P_PV-Anlage": "0ece9080-6732-11ee-92bb-d5c31bcb9442",
    "P_Wärmepumpe": "1b029800-6732-11ee-ae2e-9715cbeba615"
}

modbus_host = "192.168.178.40"
modbus_port = 1502
unit_id = 1
reg_pv= 0
reg_home = 10
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
        res_home = client.read_input_registers(reg_home, count=2, unit=unit_id)
        res_wp = client.read_input_registers(reg_wp, count=2, unit=unit_id)

        # Extract the values from the response
        val_pv = res_pv.registers
        val_home = res_home.registers
        val_wp = res_wp.registers

        # Combine the two registers into a single byte string
        byte_string_pv = struct.pack('>HH', val_pv[0], val_pv[1])
        byte_string_home = struct.pack('>HH', val_home[0], val_home[1])
        byte_string_wp = struct.pack('>HH', val_wp[0], val_wp[1])
        
        # Unpack the byte string as a signed integer (big-endian)
        parsed_val_pv = (struct.unpack('>i', byte_string_pv)[0])/100*-1
        parsed_val_home = (struct.unpack('>i', byte_string_home)[0])/100
        parsed_val_wp = (struct.unpack('>i', byte_string_wp)[0])/100
        
        # Print the parsed integer
        print(f"Parsed Integer PV: {parsed_val_pv}")
        print(f"Parsed Integer Home: {parsed_val_home}")
        print(f"Parsed Integer WP: {parsed_val_wp}")
   

    finally:
        # Close the Modbus connection
        client.close()


    

    
    #response_pv = client.read_input_registers(reg_pv, count=2, unit=unit_id).registers
    #response_wagenrain = client.read_input_registers(reg_wagenrain, count=2, unit=unit_id).registers
    #response_wp = client.read_input_registers(reg_wp, count=2, unit=unit_id).registers
        
        
    # Print the values
    #print(f"Register {reg_pv}: {response_pv}")
    #print(f"Register {reg_wagenrain}: {response_wagenrain}")
    #print(f"Register {reg_wp}: {response_wp}")
    

    
    
    
    
    #read input registers
    #p_pv_anlage = CLIENT.read_input_registers(REGISTER["P_PV_Anlage"], count=2, unit=1,).getRegister(1)
    #p_pv_anlage = CLIENT.read_input_registers(REGISTER["P_PV_Anlage"], count=22, unit=1, slave=1).getRegister(6)
    #print(p_pv_anlage)

    #Vorlage read holding registers
    #p_pv_anlage_2 = CLIENT.read_holding_registers(REGISTER["P_PV_Anlage"], count=22, unit= 1, slave=1).getRegister(6)
    #print(p_pv_anlage_2)

    #Auslesen Betriebszustand aus ISG und Schreiben auf vz
    #betriebszustand = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)
 
if __name__ == "__main__":
    main()
    
    #write_vals(UUID["Betriebszustand"], betriebszustand)

