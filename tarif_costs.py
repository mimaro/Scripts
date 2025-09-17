import requests
import json
import pprint
import datetime
import logging
import pytz
import time
from datetime import datetime, timedelta

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
SUNSET_URL = 'https://api.sunrise-sunset.org/json?lat=47.386479&lng=8.252473&formatted=0' 

########################################################################################################



#######################################################################################################
# Configuration
UUID = {
    "Brutto_Energie": "85ffa8d0-683e-11ee-9486-113294e4804d",
    "Netto_Energie": "8d8af7c0-8c8a-11f0-9d28-a9c875202312",
    "Preis_dyn": "a1547420-8c87-11f0-ab9a-bd73b64c1942",
    "Kosten_b_d": "72161320-8c87-11f0-873f-79e6590634b2",
    "Kosten_b_s": "42e29fa0-8c87-11f0-a699-831fc5906f38",
    "Kosten_n_d": "18f74440-8c8c-11f0-948b-013fcbd37465",
    "Kosten_n_s": "132713a0-8c8c-11f0-96f2-dfda5706e0e8",
    "Kosten_b_s_kum": "b4540e10-8ceb-11f0-b3fc-35adf2b97e3c",
    "Kosten_b_d_kum":  "bc2da4a0-8ceb-11f0-9f6d-095b9044f5b8",
    "Kosten_n_s_kum":  "c9a41ad0-8ceb-11f0-9adc-c72a0562776f",
    "Kosten_n_d_kum": "c17d6230-8ceb-11f0-a44e-950dce954c9a",
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb"
    
}




###########################################################################################################

def get_vals(uuid, duration="-0min"):
    # Daten von vz lesen. 
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    return req.json()

def write_vals(uuid, val):
    # Daten auf vz schreiben.
    poststring = VZ_POST_URL.format(uuid, val)
    #logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    #logging.info("Ok? {}".format(postreq.ok))

def get_data(uuid, duration="-15min"):
    url = VZ_GET_URL.format(uuid, duration)
    r = requests.get(url)
    r.raise_for_status()
    return r.json()


def main():

    #Energie exkl PV letzte 15 Minuten Abfragen
    brutto_energie = get_vals(UUID["Brutto_Energie"], duration="-15min")["data"]["consumption"]/60
    
    #Energie inkl PV letzte 15 Minuten Abfragen
    netto_energie = get_vals(UUID["Netto_Energie"], duration="-15min")["data"]["consumption"]/60
  
    preis_stat = 27.129
    preis_dyn = get_vals(UUID["Preis_dyn"], duration="-15min")["data"]["average"]

    print(f" Preis dyn: {preis_dyn} Rp./kWh")
    print(f" Preis stat: {preis_stat} Rp./kWh")
    print(f" Brutto Energie: {brutto_energie} kWh")
    print(F" Netto Energie: {netto_energie} kWh")

    kosten_b_d = brutto_energie * preis_dyn/100
    kosten_b_s = brutto_energie * preis_stat/100
    kosten_n_d = netto_energie * preis_dyn/100
    kosten_n_s = netto_energie * preis_stat/100

    print(f" Kosten bd: {kosten_b_d} CHF")
    print(f" Kosten bs: {kosten_b_s} CHF")
    print(f" Kosten nd: {kosten_n_d} CHF")
    print(f" Kosten ns: {kosten_n_s} CHF")
    
    kosten_b_d_kum = get_vals(UUID["Kosten_b_d_kum"])["data"]["tuples"][0][1] #+ kosten_b_d
    kosten_b_s_kum = get_vals(UUID["Kosten_b_s_kum"])["data"]["tuples"][0][1] #+ kosten_b_s
    kosten_n_d_kum = get_vals(UUID["Kosten_n_d_kum"])["data"]["tuples"][0][1] #+ kosten_n_d
    kosten_n_s_kum = get_vals(UUID["Kosten_n_s_kum"])["data"]["tuples"][0][1] #+ kosten_n_s

    print(f" Kosten bd kum: {kosten_b_d_kum} CHF")
    print(f" Kosten bs kum: {kosten_b_s_kum} CHF")
    print(f" Kosten nd kum: {kosten_n_d_kum} CHF")
    print(f" Kosten ns kum: {kosten_n_s_kum} CHF")
    
    kosten_b_d_kum = kosten_b_d_kum + kosten_b_d
    kosten_b_s_kum = kosten_b_s_kum + kosten_b_s
    kosten_n_d_kum = kosten_n_d_kum + kosten_n_d
    kosten_n_s_kum = kosten_n_s_kum + kosten_n_s



    print(f" Kosten bd kum+: {kosten_b_d_kum} CHF")
    print(f" Kosten bs kum+: {kosten_b_s_kum} CHF")
    print(f" Kosten nd kum+: {kosten_n_d_kum} CHF")
    print(f" Kosten ns kum+: {kosten_n_s_kum} CHF")

    
    write_vals(UUID["Kosten_b_d_kum"], kosten_b_d_kum)
    write_vals(UUID["Kosten_b_s_kum"], kosten_b_s_kum)
    write_vals(UUID["Kosten_n_d_kum"], kosten_n_d_kum)
    write_vals(UUID["Kosten_n_s_kum"], kosten_n_s_kum)

    freigabe_emob = 0
    if preis_dyn < preis_stat:
        freigabe_emob = 1
    else:
        freigabe_emob = 0

    print(f"Freigabe Tarif E-Mobilität: {freigabe_emob}")
    write_vals(UUID["Freigabe_EMob"], freigabe_emob)
    

    loops = 0
    while loops < 2:
        start = time.time()
    
        # deine Berechnung + write_vals
        write_vals(UUID["Kosten_b_d"], kosten_b_d)
        write_vals(UUID["Kosten_b_s"], kosten_b_s)
        write_vals(UUID["Kosten_n_d"], kosten_n_d)
        write_vals(UUID["Kosten_n_s"], kosten_n_s)
    
        print(f"Loop {loops+1} abgeschlossen")
    
        loops += 1  # Zähler erhöhen
    
        # Restzeit bis zur vollen Minute schlafen
        elapsed = time.time() - start
        time.sleep(max(0, 890 - elapsed)) #890
    
    print("Fertig: 13 Loops ausgeführt")


if __name__ == "__main__":
    main()
