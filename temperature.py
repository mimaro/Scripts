#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time
import requests
import json
import pprint
import datetime
import logging
import sys
 
# Systempfad zum den Sensor, weitere Systempfade könnten über ein Array
# oder weiteren Variablen hier hinzugefügt werden.
# 28-02161f5a48ee müsst ihr durch die eures Sensors ersetzen!

VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"

UUID = {
    "Puffer_mitte": "63917860-3542-11ea-adc8-b388fcd48c7a",
    "Puffer_unten": "68026710-3542-11ea-8d35-bdb641e3ce2b"
}

sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'
sensor2 = '/sys/bus/w1/devices/28-02159245ba37/w1_slave'

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

print (temp_1)
print (temp_2)

def main():
    logging.info("********************************")
    logging.info("Temp_schreiben")
    write_vals(UUID["Puffer_mitte"], temp_1)
    write_vals(UUID["Puffer_unten"], temp_2)
   
if __name__ == "__main__":
    main()


