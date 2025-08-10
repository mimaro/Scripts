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
# Mit diesem Script werden die an das raspberri pi angeschlossenen Temperatursensoren ausgelesen und die Daten auf vz geladen

##############################################################

VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

UUID = {
    "Puffer_mitte": "6832c0e0-6523-11ee-9722-2d954a0be504",
    "Puffer_unten": "50dfa7a0-6523-11ee-abd2-81d57ce6290d",
    "BWW_mitte": "b6206620-6522-11ee-a462-53c502141b13",
    "BWW_oben": "adf0da80-6522-11ee-82a3-4fe8ca3dfa5c",
    "HG_VL": "37f6a120-6523-11ee-94a0-554d4aba0692",
    "HG_RL": "44562980-6523-11ee-96bc-7b0affe66da4",
    "P_therm": "1d74a950-36ce-11ea-9",
    "T_Raum": "716e8d00-6523-11ee-a6d5-958aeed3d121"
}

sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'
sensor2 = '/sys/bus/w1/devices/28-02159245ba37/w1_slave'
sensor3 = '/sys/bus/w1/devices/28-0302977901be/w1_slave'
sensor4 = '/sys/bus/w1/devices/28-030297796ad5/w1_slave'
sensor5 = '/sys/bus/w1/devices/28-03029779113a/w1_slave'
sensor6 = '/sys/bus/w1/devices/28-030297791325/w1_slave'
sensor7 = '/sys/bus/w1/devices/28-02199245a854/w1_slave'

Offset_RT = 0.3

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
temp_4 =  str(readTempLines(sensor4)[0]-4.2)
temp_5 =  str(readTempLines(sensor5)[0]+1.4) 
temp_6 =  str(readTempLines(sensor6)[0]+1.4) 
temp_7 =  str(readTempLines(sensor7)[0]+Offset_RT) 

write_vals(UUID["Puffer_mitte"], temp_1)
write_vals(UUID["Puffer_unten"], temp_2)
write_vals(UUID["BWW_mitte"], temp_3)
write_vals(UUID["BWW_oben"], temp_4)
write_vals(UUID["HG_VL"], temp_5)
write_vals(UUID["HG_RL"], temp_6)
write_vals(UUID["T_Raum"], temp_7)

print (temp_1)
print (temp_2)
print (temp_3)
print (temp_4)
print (temp_5)
print (temp_6)
print (temp_7)

#P_therm_HG = str(temp_5)-str(temp_6)*1.16*1.3
#write_vals(UUID["P_therm"], P_therm_HG)
   



