#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import requests
import json
import pprint
import datetime
import logging
import sys

##############################################################

VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"

UUID = {
    "Puffer_mitte": "63917860-3542-11ea-adc8-b388fcd48c7a",
    "Puffer_unten": "68026710-3542-11ea-8d35-bdb641e3ce2b",
    "BWW_mitte": "e207c010-3630-11ea-8ccb-fdd7c2918630",
    "BWW_oben": "ddf322e0-3630-11ea-94fa-7fc84491c6e5",
    "HG_VL": "cd28ac80-3630-11ea-b83a-3dc3acc4c33d",
    "HG_RL": "d06db0f0-3630-11ea-8cc1-9bd4441efb71",
}

sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'
sensor2 = '/sys/bus/w1/devices/28-02159245ba37/w1_slave'
sensor3 = '/sys/bus/w1/devices/28-0302977901be/w1_slave'
sensor4 = '/sys/bus/w1/devices/28-030297796ad5/w1_slave'
sensor5 = '/sys/bus/w1/devices/28-03029779113a/w1_slave'
sensor6 = '/sys/bus/w1/devices/28-030297791325/w1_slave'

##############################################################

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    logging.info("Ok? {}".format(postreq.ok))

def readTempSensor(sensorName) :
    """Aus dem Systembus lese ich die Temperatur der DS18B20 aus."""
    f = open(sensorName, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def readTempLines(sensorName) :
    lines = readTempSensor(sensorName)
    # Solange nicht die Daten gelesen werden konnten, bin ich hier in einer Endlosschleife
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = readTempSensor(sensorName)
    temperaturStr = lines[1].find('t=')
    # Ich überprüfe ob die Temperatur gefunden wurde.
    if temperaturStr != -1 :
        tempData = lines[1][temperaturStr+2:]
        tempCelsius = float(tempData) / 1000.0
        #tempKelvin = 273 + float(tempData) / 1000
        #tempFahrenheit = float(tempData) / 1000 * 9.0 / 5.0 + 32.0
        # Rückgabe als Array - [0] tempCelsius => Celsius...
        return [tempCelsius]

temp_1 =  str(readTempLines(sensor1)[0])
temp_2 =  str(readTempLines(sensor2)[0])
temp_3 =  str(readTempLines(sensor3)[0])
temp_4 =  str(readTempLines(sensor4)[0])
temp_5 =  str(readTempLines(sensor5)[0]+1) 
temp_6 =  str(readTempLines(sensor6)[0]+1) 

write_vals(UUID["Puffer_mitte"], temp_1)
write_vals(UUID["Puffer_unten"], temp_2)
write_vals(UUID["BWW_mitte"], temp_3)
write_vals(UUID["BWW_oben"], temp_4)
write_vals(UUID["HG_VL"], temp_5)
write_vals(UUID["HG_RL"], temp_6)

#print (temp_1)
#print (temp_2)
#print (temp_3)
#print (temp_4)
#print (temp_5)
#print (temp_6)





