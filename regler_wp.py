import requests
import json
import pprint
import datetime
import logging
import pytz
from pymodbus.client.sync import ModbusTcpClient

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
UUID = {
    "T_outdoor": "8f471ab0-1cab-11e9-8fa4-3b374d3c10ca",
    "Power_balance": "9b251460-35ae-11e9-ba29-959207ffefe4",
    "Charge_station": "8270f520-6690-11e9-9272-4dde30159c8f",
    "Freigabe_sonderbetrieb": "e7e6d7e0-d973-11e9-841d-0597e49a80a1",
    "Freigabe_excess": "90212900-d972-11e9-910d-078a5d14d2c9",
    "Sperrung_excess": "dd2e3400-d973-11e9-b9c6-038d9113070b",
    "Freigabe_normalbetrieb": "fc610770-d9fb-11e9-8d49-5d7c9d433358",
    "PV_Produktion": "101ca060-50a3-11e9-a591-cf9db01e4ddd",
}


# Freigabewert für Sonderbetrieb nach Heizgrenze
FREIGABE_NORMAL_TEMP = 14

#Freigabewerte für Sonderbetrieb nach Leistung
FREIGABE_WARM_P = 600
FREIGABE_KALT_P = 1400
FREIGABE_WARM_TEMP = 15
FREIGABE_KALT_TEMP = -10
SPERRUNG_SONDERBETRIEB = 100

#Freigabewerte für Sonderbetrieb nach Zeit
UHRZEIT_WARM = datetime.time(10, 0)
UHRZEIT_KALT = datetime.time(6, 0)

#Sollwerte für Sonderbetrieb ein (aktuell keine Funktion)
SB_EIN_HK1_T = 30
SB_EIN_HK1_ST = 0.40
SB_EIN_HK2_T = 24
SB_EIN_HK2_ST = 0.40

#Sollwerte für Sonderbetrieb aus (aktuell keine Funktion)
SB_AUS_HK1_T = 22
SB_AUS_HK1_ST = 0.40
SB_AUS_HK2_T = 22
SB_AUS_HK2_ST = 0.40

#Sollwerte für Nachtabsenkung über raspi
AB_aus = datetime.time(5, 0)
AB_ein = datetime.time(21, 0)
AB_AUS_HK1_T = 22
AB_AUS_HK2_T = 22
AB_EIN_HK1_T = 20
AB_EIN_HK2_T = 20

#Sollwerte für Regulierung HK1 nach PV-Produktion
PV_max = 2000
PV_min = 0
HK1_min = 22 #Muss mit ECO-Wert von HK1 in Servicewelt übereinstimmen
HK1_max = 30
HK1_Diff_max = 8 

REGISTER = {
    "Komfort_HK1": 1501,
    "Eco_HK1": 1502,
    "Steigung_HK1": 1503,
    "Komfort_HK2": 1504,
    "Eco_HK2": 1505,
    "Steigung_HK2": 1506, 
    "Betriebsart": 1500,
    "SG1": 4001,
    "SG2": 4002,
}

IP_ISG = "192.168.178.36"

CLIENT = ModbusTcpClient(IP_ISG)
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

def get_freigabezeit_12h_temp(t_roll_avg):
    u_w = UHRZEIT_WARM.hour + UHRZEIT_WARM.minute / 60
    u_k = UHRZEIT_KALT.hour + UHRZEIT_KALT.minute / 60
    f_time = u_w + (t_roll_avg - FREIGABE_WARM_TEMP) * (
        (u_w - u_k) / (FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP))
    logging.info("Decimal Unlocktime: {}".format(f_time))
    f_time_12h_temp = datetime.time(
        hour=int(f_time), minute=int((f_time - int(f_time))*60))
    logging.info("DMS Unlocktime: {}".format(f_time_12h_temp))
    return(f_time_12h_temp)

def get_freigabezeit_excess(t_now):
    p_unlock_now = -(FREIGABE_WARM_P + (t_now - FREIGABE_WARM_TEMP) * (
        (FREIGABE_WARM_P - FREIGABE_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP)))
    logging.info("Freigabe Leistung: {}".format(p_unlock_now))
    return p_unlock_now

def main():
    tz = pytz.UTC
    b_freigabe_12h_temp = 0
    b_freigabe_excess = 0
    b_sperrung_excess = 0
    b_freigabe_normal = 0
    b_absenk_aus = 0
    b_absenk_ein = 0
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    now = datetime.datetime.now(tz=tz)
    logging.info("UTC time: {}".format(now))
    logging.info("*****************************")
    logging.info("Get values from VZ")
    t_now = get_vals(UUID["T_outdoor"])["data"]["tuples"][0][1]
    t_roll_avg_12 = get_vals(
        UUID["T_outdoor"], duration="-720min")["data"]["average"]
    t_roll_avg_24 = get_vals(
        UUID["T_outdoor"], duration="-1440min")["data"]["average"]
    
    #Einschaltsignal Sonderbetrieb
    power_balance = get_vals(
        UUID["Power_balance"], duration="-15min")["data"]["average"]
    p_charge = get_vals(UUID["Charge_station"],
                        duration="-15min")["data"]["average"]
    p_net = power_balance - p_charge
    print("Aktuelle Bilanz =",p_net)
    
    #Ausschaltsignal Sonderbetrieb 
    power_balance2 = get_vals(
        UUID["Power_balance"], duration="-30min")["data"]["average"]
    p_charge2 = get_vals(UUID["Charge_station"],
                        duration="-30min")["data"]["average"]
    p_net2 = power_balance2 - p_charge2
    print("Aktuelle Bilanz =",p_net2)
        
    logging.info("Start Freigabe Zeit & Normalbetrieb")  
    f_time_12h_temp = get_freigabezeit_12h_temp(t_roll_avg_12)
    if now.time() > f_time_12h_temp:
        b_freigabe_12h_temp = 1
    if t_roll_avg_24 < FREIGABE_NORMAL_TEMP:
        b_freigabe_normal = 1
    logging.info("Freigabe Zeit Status: {}".format(b_freigabe_12h_temp))
    logging.info("Freigabe Normalbetrieb Status:{}".format(b_freigabe_normal))
    write_vals(UUID["Freigabe_sonderbetrieb"], b_freigabe_12h_temp)
    write_vals(UUID["Freigabe_normalbetrieb"], b_freigabe_normal)
    logging.info("Ende Freigabe Zeit & Normalbetrieb")
    
    #Generiere Freigabe-sperrsignal Leistung
    logging.info("Start Freigabe Leistung")
    p_freigabe_now = get_freigabezeit_excess(t_now)
    if p_net < p_freigabe_now:
        b_freigabe_excess = 1
    if p_net2 > SPERRUNG_SONDERBETRIEB:
        b_sperrung_excess = 1
    logging.info("Freigabe Leistung: {}".format(b_freigabe_excess))
    logging.info("Sperrung Leistung: {}".format(b_sperrung_excess))
    write_vals(UUID["Freigabe_excess"], b_freigabe_excess)
    write_vals(UUID["Sperrung_excess"], b_sperrung_excess)   
   
   #Modbus Werte in für Sonderbetrieb ein schreiben 
    if (b_freigabe_normal & b_freigabe_12h_temp & b_freigabe_excess):
   # if True:
        #CLIENT.write_register(REGISTER["Komfort_HK1"], int(SB_EIN_HK1_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK1"], int(SB_EIN_HK1_ST*100))
        #CLIENT.write_register(REGISTER["Komfort_HK2"], int(SB_EIN_HK2_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK2"], int(SB_EIN_HK2_ST*100))
        CLIENT.write_register(REGISTER["Betriebsart"], int(3))
        #CLIENT.write_register(REGISTER["SG1"], int(1))
        #CLIENT.write_register(REGISTER["SG2"], int(1))
      
    #Modbus Werte für Sonderbetrieb aus schreiben
    if b_sperrung_excess:
        #CLIENT.write_register(REGISTER["Komfort_HK1"], int(SB_AUS_HK1_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK1"], int(SB_AUS_HK1_ST*100))
        #CLIENT.write_register(REGISTER["Komfort_HK2"], int(SB_AUS_HK2_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK2"], int(SB_AUS_HK2_ST*100))
        CLIENT.write_register(REGISTER["Betriebsart"], int(2))
        #CLIENT.write_register(REGISTER["SG1"], int(0))
        #CLIENT.write_register(REGISTER["SG2"], int(0))
  
 #Nachtabsenkung über Raspi
    if now.time() > AB_aus:
        b_absenk_aus = 1
    if now.time() < AB_ein:
        b_absenk_ein = 1
        
    if  (b_absenk_aus & b_absenk_ein):
        CLIENT.write_register(REGISTER["Eco_HK1"], int(AB_AUS_HK1_T*10))
        CLIENT.write_register(REGISTER["Eco_HK2"], int(AB_AUS_HK2_T*10))
            
    else:
       CLIENT.write_register(REGISTER["Eco_HK1"], int(AB_EIN_HK1_T*10))
       CLIENT.write_register(REGISTER["Eco_HK2"], int(AB_EIN_HK2_T*10))   

  #Schreiben Soll-Temp HK1 in Abhängigkeit von PV-Leistung 
    PV_Aktuell = get_vals(UUID["PV_Produktion"],
                        duration="-15min")["data"]["average"]
        
    PV_Faktor = PV_Aktuell*(PV_min/PV_max)
    logging.info("PV_Faktor: {}".format(PV_Faktor))
    HK1_aktuell = HK1_min + HK1_Diff_max * PV_Faktor
    logging.info("HK1_aktuell: {}".format(HK1_aktuell))  
        
    if HK1_aktuell > HK1_max:   
        CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_max*10))
    
    else:
        CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_aktuell*10))    
        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()