#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import json
import datetime
import logging
import pytz
import time
import math
from collections import deque

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
#######################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "Tarif_Kosten": "a1547420-8c87-11f0-ab9a-bd73b64c1942",
    "Forecast_COP":  "31877e20-9aaa-11f0-8759-733431a03535",
    "P_WP_Max":    "46e21920-9ab9-11f0-9359-d3451ca32acb",
    "Freigabe_WP_Nacht":      "f76b26f0-a9fd-11f0-a7d7-5958c376a670"
}
#######################################################################################################

p_prod = 0
    
    p_therm_zukunft = get_vals(UUID["P_Therm_Zukunft"], duration="0 min")["data"]["average"]/1000
    p_therm_prod = get_vals(UUID["P_Therm_Prod"], duration="-1440 min&to=now")["data"]["consumption"]/1000

    p_therm_bil = p_therm_zukunft - p_therm_prod 

    if p_therm_bil < 0:
        p_prod = 0
    else:
        p_prod = 1
    
    write_vals(UUID["P_Therm_Bil_Freig"], p_prod) 
    
    logging.info("P thermisch Zukunft: {}".format(p_therm_zukunft))
    logging.info("P thermisch Produziert: {}".format(p_therm_prod))
    logging.info("P thermisch Bilanz: {}".format(p_therm_bil))
    logging.info("P thermisch Freigabe: {}".format(p_prod))

    logging.info("********************************")

if __name__ == "__main__":
    main()
