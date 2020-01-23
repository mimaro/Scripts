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
    "Bilanz_8a": "9b251460-35ae-11e9-ba29-959207ffefe4",
    "Ueberschuss_8a": "4969e720-3e17-11ea-b1b1-bdbc58c0d681"
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
    logging.info("Ueberschuss")
    balance_8a = get_vals(UUID["Bilanz_8a"])["data"]["tuples"][0][1]
    if  balance_8a <= 0:
        ueberschuss_8a = balance_8a
        
    else:
        ueberschuss_8a = 0
    write_vals(UUID["Ueberschuss_8a"], ueberschuss_8a) 

 
if __name__ == "__main__":
    main()
