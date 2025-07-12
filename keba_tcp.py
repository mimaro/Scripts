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
from gpiozero import Button

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
    "Charge_State": "84d69ec0-6e76-11ee-9931-11a6e3c1cc33",
    "I_Lade_max": "5d090380-6e79-11ee-80be-0b05d0846b56",
    "V_act": "3cd2a490-6e7a-11ee-8790-ab29c7762bfa",
    "I_opt": "d45b7370-6e8c-11ee-b809-49218e061c3c",
    "I_bil": "b95b68e0-6e8e-11ee-b0f1-f53999b676d0",
    "Error": "a23a3510-6ea6-11ee-a52a-650ae6b78585"
}

#Network KEBA
server_ip_keba = "192.168.178.61"
server_port_keba = 502
unit_id_keba = 255

#Network SEL
server_ip_sel = "192.168.178.40"
server_port_sel = 502 #alt 1502

#Register KEBA
charge_state= 1000
error_code = 1006
char_curr_1 = 1008
active_p = 1020
vol_ph = 1040
switch = 1550
power_f = 1046
i_max = 1100
char_curr_v = 1040
set_curr = 5004
failsafe_curr = 1600
failsafe_timeout = 1602
set_fail_curr = 5016
set_fail_time = 5018
set_fail = 5020

#Register SEL
reg_bil = 10

# Max / Min Values
keba_max_i = 32
keba_min_i = 10
bil_offset = 0 

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
    curr_i_val = curr_i_pars.decode_32bit_uint()/1000

    # Read active power
    act_p_unpars = client_keba.read_holding_registers(active_p, 2, unit=1)
    act_p_pars = BinaryPayloadDecoder.fromRegisters(act_p_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    act_p_val = act_p_pars.decode_32bit_uint()/1000

    # Read active power factor
    power_f_unpars = client_keba.read_holding_registers(power_f, 2, unit=1)
    power_f_pars = BinaryPayloadDecoder.fromRegisters(power_f_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    power_f_val = power_f_pars.decode_32bit_uint()/1000

    # Read active current max
    curr_i_max_unpars = client_keba.read_holding_registers(i_max, 2, unit=1)
    curr_i_max_pars = BinaryPayloadDecoder.fromRegisters(curr_i_max_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    curr_i_max_val = curr_i_max_pars.decode_32bit_uint()/1000

    # Read active voltage phase 1
    curr_v_unpars = client_keba.read_holding_registers(char_curr_v, 2, unit=1)
    curr_v_pars = BinaryPayloadDecoder.fromRegisters(curr_v_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    curr_v_val = curr_v_pars.decode_32bit_uint()

    if curr_v_val == 0:
        curr_v_val = 230
    else:
        curr_v_val = curr_v_val
    
    # Read error Code
    error_unpars = client_keba.read_holding_registers(error_code, 2, unit=1)
    error_pars = BinaryPayloadDecoder.fromRegisters(error_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    error_val = error_pars.decode_32bit_uint()

    # Read Failsafe Current
    fail_c_unpars = client_keba.read_holding_registers(failsafe_curr, 2, unit=1)
    fail_c_pars = BinaryPayloadDecoder.fromRegisters(fail_c_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    fail_c_val = fail_c_pars.decode_32bit_uint()

    # Read Failsafe Timeout
    fail_t_unpars = client_keba.read_holding_registers(failsafe_timeout, 2, unit=1)
    fail_t_pars = BinaryPayloadDecoder.fromRegisters(fail_t_unpars.registers, byteorder=Endian.Big, wordorder=Endian.Big)
    fail_t_val = fail_t_pars.decode_32bit_uint()
    
    # Read Wagenrain SEL Bilanz
    #try:
    #    res_bil = client_sel.read_input_registers(reg_bil, count=2, unit=1)
    #    if res_bil.isError():
    #        raise Exception("Modbus error response")
    #    val_bil = res_bil.registers
    #    byte_string_bil = struct.pack('>HH', val_bil[0], val_bil[1])     
    #    parsed_val_bil = int((struct.unpack('>i', byte_string_bil)[0])/100) - 500
    #except Exception as e:
    #    print(f"Fehler beim Lesen von SEL Modbus: {e}")
    #    parsed_val_bil = 0  # Fallback-Wert bei Fehler
    
    res_bil = client_sel.read_input_registers(reg_bil, count=2, unit=1)
    val_bil = res_bil.registers
    byte_string_bil = struct.pack('>HH', val_bil[0], val_bil[1])     
    parsed_val_bil = int((struct.unpack('>i', byte_string_bil)[0])/100)-500

    # Berechne Bilanz Wagenrain in A
    val_bil_i = ((parsed_val_bil-bil_offset) / (curr_v_val))*-1
    
    # Berechne optimaler Ladestrom
    i_balance = get_vals(UUID["I_opt"], duration="-0min")["data"]["average"]
    print(f"Old I opt: {i_balance}")
    print(f"actual bilance: {val_bil_i}")

    if val_bil_i > 0:  # Bezug von Netz
        i_balance_new = i_balance + val_bil_i/3
    else: # Überschuss ins Netz
        i_balance_new = i_balance + val_bil_i/5
    print(f"New I opt: {i_balance_new}")

    if i_balance_new < keba_min_i:
        i_opt = keba_min_i 
    elif i_balance_new > keba_max_i:
        i_opt = keba_max_i
    else:
        i_opt = int(i_balance_new)

    # Prüfe Position Wahlschalter Schnellladung / Optimierung
    switch = Button(2)
    switch_state = 0

    if switch.is_pressed:
        switch_state = 1
    else:
        switch_state = 0

    # Prüfe ob Anlage in Betrieb 
    if char_state_val < 3:
        i_opt = 10
    
    # Schreibe auf KEBA
    if switch_state == 0:
        client_keba.write_register(set_curr, i_opt*1000, unit=1)
        write_vals(UUID["I_opt"], i_opt)
        print(f"Actual Set Ampere: {i_opt}")
    else:
        client_keba.write_register(set_curr, 32000, unit=1)
        write_vals(UUID["I_opt"], 32)
        print(f"Actual Set Ampere: 32 ")

    # Schreibe Failsafe Register KEBA
    client_keba.write_register(set_fail_curr, 10000, unit=1)
    client_keba.write_register(set_fail_time, 300, unit=1)
    client_keba.write_register(set_fail, 1, unit=1)

    # Schreibe UUID's vz
    write_vals(UUID["Charge_State"], char_state_val)
    write_vals(UUID["I_Lade"], curr_i_val)
    write_vals(UUID["P_Aktiv"], act_p_val)
    write_vals(UUID["Power_F"], power_f_val)
    write_vals(UUID["I_Lade_max"], curr_i_max_val)
    write_vals(UUID["V_act"], curr_v_val)
    write_vals(UUID["I_bil"], val_bil_i)
    write_vals(UUID["Error"], error_val)
    write_vals(UUID["Switch"], switch_state)

    # Schreibe Rückmeldung Terminal
    print(f"Charge State: {char_state_val}")
    print(f"Switch State: {switch_state}")
    print(f"Actual Charging Current 1: {curr_i_val}")
    print(f"Actual max. Charging Current: {curr_i_max_val}")
    print(f"Actual Charging Power: {act_p_val}")
    print(f"Actual Power Factor: {power_f_val}")
    print(f"Actual Voltage: {curr_v_val}")
    print(f"Actual Bilance Watt: {parsed_val_bil}")
    print(f"Actual Bilance Ampere: {val_bil_i}")
    print(f"Actual Error Code: {error_val}")
    print(f"Failsafe Current: {fail_c_val}")
    print(f"Failsafe timeout: {fail_t_val}")
       
    client_keba.close()
    client_sel.close()

if __name__ == "__main__":
    main()
    
