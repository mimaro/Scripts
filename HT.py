import requests
import json
import pprint
import datetime
import logging
import pytz

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#Umschaltzeiten Hoch- Niedertarig

HT_ein_Mo_Fr = datetime.time(6, 0)
HT_aus_Mo_Fr = datetime.time(22, 0)
HT_ein_Sa = datetime.time(6, 0)
HT_aus_Sa = datetime.time(13, 0)

#######################################################################################################
# Configuration
UUID = {
    "Tarifschaltung": "b646b7f0-3e2c-11ea-abd8-6121bdf54191"
     
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
    tz = pytz.UTC
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    now = datetime.datetime.now(tz=tz)
    logging.info("UTC time: {}".format(now))
    logging.info("*****************************")
    
    
    #Definition Hoch- / Niedertarif
     
    
    #from datetime import date
    #from datetime import time
    #day = date.today()
    time = now.time()
    #print (day)
    
    if now.time() > HT_ein_Mo_Fr & now.time() < HT_aus_Mo_Fr:
        print ("Hochtarifzeit")
    
    
   
   
        
    
    
   
   #write_vals(UUID["Tarifumschaltung"], r_n_8a) 
       

    
if __name__ == "__main__":
    main()