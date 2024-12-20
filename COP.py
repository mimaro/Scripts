import requests
import json
import pprint
import datetime
import logging

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "COP_o_venti": "0891e8f0-6522-11ee-96f8-f776965c186c",
    "WP_th": "69630320-6522-11ee-9e09-ebb553e47b70",
    "WP_el": "1b029800-6732-11ee-ae2e-9715cbeba615",
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
    wp_therm = get_vals(UUID["WP_th"],duration="-0min")["data"]["average"]
    wp_el = get_vals(UUID["WP_el"], duration = "-0min")["data"]["average"]
    cop_o_venti = wp_therm / wp_el
    if cop_o_venti >= 0:
        if cop_o_venti > 10:
            write_vals(UUID["COP_o_venti"], "0")
        else:
        write_vals(UUID["COP_o_venti"], cop_o_venti)
    else:
        write_vals(UUID["COP_o_venti"], "0")
    print(cop_o_venti)
  
if __name__ == "__main__":
    main()
