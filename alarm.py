import requests
import json
import pprint
import datetime
import logging
import pytz

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"

#######################################################################################################
# UUID's

UUID = {
  "T_Puffer": "88b7c280-1cab-11e9-938e-fb5dc04c61d4",
  "PV_Prod": "101ca060-50a3-11e9-a591-cf9db01e4ddd"
  
}

#######################################################################################################


WP_check = get_vals(UUID["T_Puffer"], duration="-1min")["data"]["average"]
PV_check = get_vals(UUID["PV_Prod"], duration="-1min")["data"]["average"]
