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
    "P_Aktiv": "6cb255a0-6e5f-11ee-b899-c791d8058d25",
    "I_Lade": "6e768290-6e5e-11ee-bd91-fd7700aa25ee",
    "Switch": "d9d09d00-6e5e-11ee-8a40-53ee17720f6a",
    "Power_F": "ac06a530-6e5f-11ee-b968-65b0d8af2151",
    "Charge_State": "84d69ec0-6e76-11ee-9931-11a6e3c1cc33w",
    "I_Lade_max": "5d090380-6e79-11ee-80be-0b05d0846b56",
    "V_act": "3cd2a490-6e7a-11ee-8790-ab29c7762bfa"
}

#Network KEBA
server_ip_keba = "192.168.178.59"
server_port_keba = 502
unit_id_keba = 255

#Network SEL
server_ip_sel = "192.168.178.59"
server_port_sel = 502
unit_id_sel = 255

#Register KEBA
charge_state= 1000
char_curr_1 = 1008
active_p = 1020
vol_ph = 1040
switch = 1550
power_f = 1046
i_max = 1100
char_curr_v = 1040

#Register SEL



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
    client_keba = ModbusTcpClient(server_ip_keba, port=server_port_keba)
    client_sel = ModbusTcpClient(server_ip_sel, port=server_port_sel)

    # Connect to the Modbus device
    client_keba.connect()
    client_sel.connect()
   
    # Read Charge State
    char_state_unpars = client_keba.read_holding_registers(charge_state, 2, unit=1)
    char_state_pars = BinaryPayloadDecoder.fromRegisters(char_state_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    char_state_val = char_state_pars.decode_32bit_uint()

    # Read current phase 1
    curr_i_unpars = client_keba.read_holding_registers(char_curr_1, 2, unit=1)
    curr_i_pars = BinaryPayloadDecoder.fromRegisters(curr_i_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    curr_i_val = curr_i_pars.decode_32bit_uint()

    # Read active power
    act_p_unpars = client_keba.read_holding_registers(active_p, 2, unit=1)
    act_p_pars = BinaryPayloadDecoder.fromRegisters(act_p_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    act_p_val = act_p_pars.decode_32bit_uint()

    # Read active power factor
    power_f_unpars = client_keba.read_holding_registers(power_f, 2, unit=1)
    power_f_pars = BinaryPayloadDecoder.fromRegisters(power_f_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    power_f_val = power_f_pars.decode_32bit_uint()

     # Read active current max
    curr_i_max_unpars = client_keba.read_holding_registers(i_max, 2, unit=1)
    curr_i_max_pars = BinaryPayloadDecoder.fromRegisters(curr_i_max_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    curr_i_max_val = curr_i_max_pars.decode_32bit_uint()

     # Read active voltage phase 1
    curr_v_unpars = client_keba.read_holding_registers(char_curr_v, 2, unit=1)
    curr_v_pars = BinaryPayloadDecoder.fromRegisters(curr_v_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    curr_v_val = curr_v_pars.decode_32bit_uint()
    
    #switch_unpars = client.read_holding_registers(switch, 4, unit=1)
    #print(switch_unpars)
    #switch_pars = BinaryPayloadDecoder.fromRegisters(switch_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    #switch_val = char_state_pars.decode_32bit_uint()
    
    print(f"Charge State: {char_state_val}")
    print(f"Actual Charging Current 1: {curr_i_val}")
    print(f"Actual max. Charging Current: {curr_i_max_val}")
    print(f"Actual Charging Power: {act_p_val}")
    print(f"Actual Power Factor: {power_f_val}")
    print(f"Actual Voltage: {curr_v_val}")
    

    #print(f"Switch State: {switch_val}")
       
    write_vals(UUID["Charge_State"], char_state_val)
    write_vals(UUID["I_Lade"], curr_i_val)
    write_vals(UUID["P_Aktiv"], act_p_val)
    write_vals(UUID["Power_F"], power_f_val)
    write_vals(UUID["I_Lade_max"], power_f_val)
    write_vals(UUID["V_act"], curr_v_val)
      


    client_keba.close()
    client_sel.close()






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
    
