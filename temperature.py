#!/usr/bin/python3
# -*- coding: utf-8 -*-
import time, sys

sensor1 = '/sys/bus/w1/devices/28-021492459fbf/w1_slave'

def   readTemp(sensor1):
      t_s_1 = readtemp(sensor1)

print (t_s_1)
