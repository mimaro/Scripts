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

#r_n = Rückspeisung Netz
#r_zev = Rückspeisung ZEV
#b_zev = Bezug ZEV
#b_n = Bezug Netz
#ht = Hochtarif
#nt = Niedertarif

#######################################################################################################
# Configuration
UUID = {
    "Bilanz_8a": "9b251460-35ae-11e9-ba29-959207ffefe4",
    "Bilanz_8b": "1e4b1530-4fc9-11e9-b832-cf5186ec2738", 
    "Bilanz_8c": "213946b0-4fc9-11e9-aacc-758bb6712b5f",
    "R_ZEV_8a": "
    "B_ZEV_8b": "
    "B_ZEV_8c: "
    "R_N_HT_8a": "
    "R_N_NT_8a": "
    "B_N_HT_8a": "
    "B_N_NT_8a": "
    "B_N_HT_8b": "
    "B_N_NT_8b": "
    "B_N_HT_8c": "
    "B_N_NT_8c": "
    
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
    logging.info("Erstelle Abrechnung")
    balance_8a = get_vals(UUID["Bilanz_8a"])["data"]["tuples"][0][1]
    #balance_8b = get_vals(UUID["Bilanz_8b"])["data"]["tuples"][0][1]
    #balance_8c = get_vals(UUID["Bilanz_8c"])["data"]["tuples"][0][1]#
    
    if  balance_8a > 0:
        v_8a = balance_8a
    else:
   

        ueberschuss_8a = 0
    
    
    #Schreibe Netzbezug, Netzrückspeisung in Abhängigkeit HT / NT
    if t_ht = 1
        write_vals(UUID["R_N_HT_8a"], ueberschuss_8a) 
        write_vals(UUID["R_N_NT_8a"], 0) 
        write_vals(UUID["B_N_HT_8a"], ueberschuss_8a) 
        write_vals(UUID["B_N_NT_8a"], 0) 
        write_vals(UUID["B_N_HT_8b"], ueberschuss_8a) 
        write_vals(UUID["B_N_NT_8b"], 0) 
        write_vals(UUID["B_N_HT_8c"], ueberschuss_8a) 
        write_vals(UUID["B_N_NT_8c"], 0) 
            
    else
        write_vals(UUID["R_N_HT_8a"], 0) 
        write_vals(UUID["R_N_NT_8a"], ueberschuss_8a) 
        write_vals(UUID["B_N_HT_8a"], 0) 
        write_vals(UUID["B_N_NT_8a"], ueberschuss_8a) 
        write_vals(UUID["B_N_HT_8b"], 0) 
        write_vals(UUID["B_N_NT_8b"], ueberschuss_8a) 
        write_vals(UUID["B_N_HT_8c"], 0) 
        write_vals(UUID["B_N_NT_8c"], ueberschuss_8a)   
    
    #Schreibe Bezug, Rückspeisung ZEV
    write_vals(UUID["R_ZEV_8a"], ueberschuss_8a) 
    write_vals(UUID["B_ZEV_8b"], ueberschuss_8a) 
    write_vals(UUID["B_ZEV_8c"], ueberschuss_8a) 

    
if __name__ == "__main__":
    main()
