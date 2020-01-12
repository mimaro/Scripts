#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time 
import sys

def LeseAktuelleTemperatur(/sys/bus/w1/devices):

# 1-wire Slave Datei lesen
file = open(/sys/bus/w1/devices)
filecontent = file.read()
file.close()

# Temperaturwerte auslesen und konvertieren
stringvalue = filecontent.split(„\n“)[1].split(“ „)[9]
temperature = float(stringvalue[2:]) / 1000

# Temperatur ausgeben
rueckgabewert = ‚%6.2f‘ % temperature
return(rueckgabewert)

Lauf = 0
Durchlauf = 120
WartenSek = 30
filename = time.strftime(„%Y%m%d.%m“)

while Lauf <= Durchlauf:

timestamp = time.strftime(„%d.%m.%Y %H:%M:%S“)

# Temperatur 1 messen
temperatur = LeseAktuelleTemperatur(‚/sys/bus/w1/devices/28-021492459fbf/w1_slave‘)
print „1 – „, timestamp, „: „, temperatur, „°C“
