#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time, sys
 
# Systempfad zum den Sensor, weitere Systempfade könnten über ein Array
# oder weiteren Variablen hier hinzugefügt werden.
# 28-02161f5a48ee müsst ihr durch die eures Sensors ersetzen!
sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'
sensor2 = '/sys/bus/w1/devices/28-02159245ba37/w1_slave'

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
        #return [tempCelsius, tempKelvin, tempFahrenheit]

temp_1 =  str(readTempLines(sensor1))
print (temp_1)
       
#print("Temperatur um " + time.strftime('%H:%M:%S') +" drinnen: " + str(readTempLines(sensor1)[0]) + " °C")
#print("Temperatur um " + time.strftime('%H:%M:%S') +" drinnen: " + str(readTempLines(sensor2)[0]) + " °C")
