
import requests
import json
import pprint
import datetime
import logging

#######################################################################################################
# Format URLs

VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
#UUID = {
 #   "COP_o_venti": "312ec8e0-52e7-11e9-ac6d-4f4dd87fd97b",
  #  "COP_m_venti": "3a89b8a0-52e7-11e9-b184-73ec439c39c9",
  #  "WP_th": "9399ca80-910c-11e9-ac0f-31ff5bbdf885",
  #  "WP_el": "92096720-35ae-11e9-a74c-534de753ada9",
  #  "Venti": "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
#}

###########################################################################################################

sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'
logging.info("1")

#def get_vals(uuid, duration="-0min"):
 #   req = requests.get(VZ_GET_URL.format(uuid, duration))
  #  return req.json()

#def write_vals(uuid, val):
 #   poststring = VZ_POST_URL.format(uuid, val)
 #   logging.info("Poststring {}".format(poststring))
 #   postreq = requests.post(poststring)
 #   logging.info("Ok? {}".format(postreq.ok))
 
def readTempSensor(sensor1) :
    """Aus dem Systembus lese ich die Temperatur der DS18B20 aus."""
    f = open(sensor1, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
logging.info("2")
 
def readTempLines(sensor1) :
    lines = readTempSensor(sensor1)
    temperaturStr = lines[1].find('t=')
    # Ich überprüfe ob die Temperatur gefunden wurde.
    if temperaturStr != -1 :
        tempData = lines[1][temperaturStr+2:]
        tempCelsius = float(tempData) / 1000.0
        # Rückgabe als Array - [0] tempCelsius => Celsius...
        print= tempCelsius   
    
    logging.info("********************************")
    
#def main():    
 #   write_vals(UUID["COP_o_venti"], cop_o_venti)
  #  write_vals(UUID["COP_m_venti"], cop_m_venti)
   
#if __name__ == "__main__":
#main()






 


