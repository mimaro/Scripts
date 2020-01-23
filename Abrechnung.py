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
#v = Verbrauch


#######################################################################################################
# Configuration
UUID = {
    "Bilanz_8a": "9b251460-35ae-11e9-ba29-959207ffefe4",
    "Bilanz_8b": "1e4b1530-4fc9-11e9-b832-cf5186ec2738", 
    "Bilanz_8c": "213946b0-4fc9-11e9-aacc-758bb6712b5f",
    "Bilanz_ZEV: "
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
    balance_8b = get_vals(UUID["Bilanz_8b"])["data"]["tuples"][0][1]
    balance_8c = get_vals(UUID["Bilanz_8c"])["data"]["tuples"][0][1]
    balance_zev = get_vals(UUID["Bilanz_ZEV"])["data"]["tuples"][0][1]
    
    #Aufteilen Bilanz nach Bezug & Rückspeisung
    if  balance_8a >= 0:
        v_8a = balance_8a
        r_8a = 0
    else:
        v_8a = 0
        r_8a = balance_8a

    if  balance_8b >= 0:
        v_8b = balance_8b
        r_8b = 0
    else:
        v_8b = 0
        r_8b = balance_8b    
     
    if  balance_8c >= 0:
        v_8c = balance_8c
        r_8c = 0
    else:
        v_8c = 0
        r_8c = balance_8c
    
    if  balance_zev >= 0:
        v_zev = balance_zev
        r_zev = 0
    else:
        v_zev = 0
        r_zev = balance_zev
    
    #Aufteilen Energie auf Verbraucher
    b_n_8a = v_8a/(v_8a+v_8b+v_8c)*v_zev
    b_n_8b = v_8b/(v_8a+v_8b+v_8c)*v_zev
    b_n_8c = v_8c/(v_8a+v_8b+v_8c)*v_zev
    b_zev_8a = v_8a - b_n_8a
    b_zev_8b = v_8b - b_n_8b
    b_zev_8c = v_8c - b_n_8c
    r_zev_8a = r_8a/(r_8a + r_8b + r_8c)*(b_zev_8a + b_zev_8b + b_zev_8c) * -1
    r_zev_8b = r_8b/(r_8a + r_8b + r_8c)*(b_zev_8a + b_zev_8b + b_zev_8c) * -1
    r_zev_8c = r_8c/(r_8a + r_8b + r_8c)*(b_zev_8a + b_zev_8b + b_zev_8c) * -1
    r_n_8a = r_8a/(r_8a + r_8b + r_8c) * r_zev
    r_n_8b = r_8b/(r_8a + r_8b + r_8c) * r_zev
    r_n_8c = r_8b/(r_8a + r_8b + r_8c) * r_zev
    
    #Schreibe Netzbezug, Netzrückspeisung in Abhängigkeit HT / NT
    if t_ht = 1
        write_vals(UUID["R_N_HT_8a"], r_n_8a) 
        write_vals(UUID["R_N_NT_8a"], 0) 
        #write_vals(UUID["R_N_HT_8b"], r_n_8b) 
        #write_vals(UUID["R_N_NT_8b"], 0) 
        #write_vals(UUID["R_N_HT_8c"], r_n_8c) 
        #write_vals(UUID["R_N_NT_8c"], 0)        
        write_vals(UUID["B_N_HT_8a"], b_n_8a) 
        write_vals(UUID["B_N_NT_8a"], 0) 
        write_vals(UUID["B_N_HT_8b"], b_n_8b) 
        write_vals(UUID["B_N_NT_8b"], 0) 
        write_vals(UUID["B_N_HT_8c"], b_n_8c) 
        write_vals(UUID["B_N_NT_8c"], 0) 
            
    else
        write_vals(UUID["R_N_HT_8a"], 0) 
        write_vals(UUID["R_N_NT_8a"], r_n_8a) 
        #write_vals(UUID["R_N_HT_8b"], 0) 
        #write_vals(UUID["R_N_NT_8b"], r_n_8b) 
        #write_vals(UUID["R_N_HT_8c"], 0) 
        #write_vals(UUID["R_N_NT_8c"], r_n_8c) 
        write_vals(UUID["B_N_HT_8a"], 0) 
        write_vals(UUID["B_N_NT_8a"], b_n_8a) 
        write_vals(UUID["B_N_HT_8b"], 0) 
        write_vals(UUID["B_N_NT_8b"], b_n_8b) 
        write_vals(UUID["B_N_HT_8c"], 0) 
        write_vals(UUID["B_N_NT_8c"], b_n_8c)   
    
    #Schreibe Bezug, Rückspeisung ZEV
    write_vals(UUID["R_ZEV_8a"], r_zev_8a) 
    #write_vals(UUID["R_ZEV_8b"], r_zev_8b) 
    #write_vals(UUID["R_ZEV_8c"], r_zev_8c) 
    #write_vals(UUID["B_ZEV_8a"], b_zev_8a)
    write_vals(UUID["B_ZEV_8b"], b_zev_8b) 
    write_vals(UUID["B_ZEV_8c"], b_zev_8c) 

    
if __name__ == "__main__":
    main()
