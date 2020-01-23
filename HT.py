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

#r_n = Rückspeisung Netz
#r_zev = Rückspeisung ZEV
#b_zev = Bezug ZEV
#b_n = Bezug Netz
#ht = Hochtarif
#nt = Niedertarif
#v = Verbrauch


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
    logging.info("********************************")
    logging.info("Erstelle Abrechnung")
  
    
    #Definition Hoch- / Niedertarif
    #tz = pytz.UTC
   
   #now = datetime.datetime.now(tz=tz)
    
    
    
    from datetime import date
    from datetime import time
    day = date.today()
    time = time.now()
    print (day)
    print (time)
   
   
    
   
   #write_vals(UUID["Tarifumschaltung"], r_n_8a) 
       

    
if __name__ == "__main__":
    main()
