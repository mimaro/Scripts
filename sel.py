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
    "P_PV_Anlage": 0,
    "P_Wagenrain_8a": 10,
    "P_Wärmepumpe": 20
}

SEL_IP = "192.168.178.40"
SEL_PORT = 1502

CLIENT = ModbusTcpClient(SEL_IP,SEL_PORT)
CLIENT.connect()

modbus_host = "192.168.178.40"
modbus_port = 1502
unit_id = 1
register_address= 0
reg_wagenrain = 10
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
        # Read the register
        response = client.read_input_registers(register_address, count=20, unit=unit_id)

    # Check if the response is valid
        if response.isError():
            print(f"Modbus Error: {response.get_exception_code()}")
        else:
            # Extract the values from the response
            values = response.registers

            # Print the values
            print(f"Register {register_address}: {values}")
    
    except Exception as e:
        print(f"An error occurred: {e}")

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
    

   
    # Close the Modbus connection    
    client.close()
    
    
    
    
    
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

