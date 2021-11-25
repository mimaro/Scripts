import requests
import json
import pprint
import datetime
import logging

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "COP_o_venti": "312ec8e0-52e7-11e9-ac6d-4f4dd87fd97b",
    "WP_th": "9399ca80-910c-11e9-ac0f-31ff5bbdf885",
    "WP_el": "92096720-35ae-11e9-a74c-534de753ada9",
}

###########################################################################################################

def get_vals(uuid, duration="-5min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    #return(json.loads(req.content))
    return req.json()

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    logging.info("Ok? {}".format(postreq.ok))
    
def main():
    logging.info("********************************")
    logging.info("COP")
    wp_therm = get_vals(UUID["WP_th"],duration="-5min")["data"]["average"]
    wp_el = get_vals(UUID["WP_el"], druation = "-5min")["data"]["average"]
    cop_o_venti = wp_therm / wp_el
    if cop_o_venti >= 0:
        write_vals(UUID["COP_o_venti"], cop_o_venti)
    else:
        write_vals(UUID["COP_o_venti"], "0")
    print(cop_o_venti)
  
if __name__ == "__main__":
    main()
