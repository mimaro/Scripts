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
    "COP_m_venti": "3a89b8a0-52e7-11e9-b184-73ec439c39c9",
    "WP_th": "9399ca80-910c-11e9-ac0f-31ff5bbdf885",
    "WP_el": "92096720-35ae-11e9-a74c-534de753ada9",
    "Venti": "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
}

###########################################################################################################

def get_vals(uuid, duration="-0min"):
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
    wp_therm = get_vals(UUID["WP_th"])["data"]["tuples"][0][1]
    wp_el = get_vals(UUID["WP_el"])["data"]["tuples"][0][1]
    venti = get_vals(UUID["Venti"])["data"]["tuples"][0][1]
    cop_o_venti = wp_therm / wp_el
    cop_m_venti = wp_therm / (wp_el + venti)
    
if  cop_o_venti > 10 or cop_o_venti < 0 or cop_m_venti > 10 or cop_m_venti < 0:
    write_vals(UUID["COP_o_venti"], 0)
    write_vals(UUID["COP_m_venti"], 0)
    
else:
    write_vals(UUID["COP_o_venti"], cop_o_venti)
    write_vals(UUID["COP_m_venti"], cop_m_venti)
   
if __name__ == "__main__":
    main()