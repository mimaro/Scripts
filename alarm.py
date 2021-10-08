import requests
import json
import pprint
import datetime
import logging
#import pytz

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

def get_vals(uuid, duration="-0min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    #return(json.loads(req.content))
    return req.json()

WP_check = get_vals(UUID["T_Puffer"], duration="-0min")["data"]["minimum"]
PV_check = get_vals(UUID["PV_Prod"], duration="-0min")["data"]["average"]

print(WP_check)
print(PV_check)
