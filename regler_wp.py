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
    "t_Sperrung_Tag": "e7e6d7e0-d973-11e9-841d-0597e49a80a1",
    "t_Sperrung_Nacht": "a15ab220-1d5a-11e9-9dd4-57fe91d5c03b",
    "t_Verzoegerung_Tag": "f60ca430-4a61-11e9-8fa1-47cb405220bd",
    "WP_Freigabe": "232bec80-7a2a-11ea-b704-0de0b4780fba",
    "Freigabe_excess": "90212900-d972-11e9-910d-078a5d14d2c9",
    "Sperrung_excess": "dd2e3400-d973-11e9-b9c6-038d9113070b",
    "Freigabe_normalbetrieb": "fc610770-d9fb-11e9-8d49-5d7c9d433358",
    "PV_Produktion": "101ca060-50a3-11e9-a591-cf9db01e4ddd",
    "Bilanz_avg_aus": "ad5c8090-3698-11ea-8ad7-7f796afef9a1", 
    "Bilanz_avg_ein": "a4f39770-3698-11ea-b87e-9f684e384f0b",
    "WP_Verbrauch": "92096720-35ae-11e9-a74c-534de753ada9",
    "T_Raum": "d8320a80-5314-11ea-8deb-5944d31b0b3c"
}


# Freigabewert für Sonderbetrieb nach Heizgrenze
FREIGABE_NORMAL_TEMP = 14

#Freigabewerte für Sonderbetrieb nach Leistung
FREIGABE_WARM_P = -600
FREIGABE_KALT_P = -800
FREIGABE_WARM_TEMP = 15
FREIGABE_KALT_TEMP = -10
SPERRUNG_WARM_P = FREIGABE_WARM_P + 100
SPERRUNG_KALT_P = FREIGABE_KALT_P + 100

#Freigabewerte für Sonderbetrieb nach Zeit
FREIGABE_WARM_T = 14
FREIGABE_KALT_T = -10
UHRZEIT_WARM = datetime.time(7, 0)
UHRZEIT_KALT = datetime.time(7, 0)

#Sollwerte für Sonderbetrieb ein (aktuell keine Funktion)
#SB_EIN_HK1_T = 30
#SB_EIN_HK1_ST = 0.40
#SB_EIN_HK2_T = 24
#SB_EIN_HK2_ST = 0.40

#Sollwerte für Sonderbetrieb aus (aktuell keine Funktion)
#SB_AUS_HK1_T = 22
#SB_AUS_HK1_ST = 0.40
#SB_AUS_HK2_T = 22
#SB_AUS_HK2_ST = 0.40

#Sollwerte für Nachtabsenkung über raspi
AB_aus = datetime.time(5, 0)
AB_ein = datetime.time(21, 0)
AB_AUS_HK1_T = 5
AB_AUS_HK2_T = 20
AB_EIN_HK1_T = 5
AB_EIN_HK2_T = 20

#Sollwerte für Regulierung HK1 nach PV-Produktion & Temp
PV_max = 2000
HK1_min = 19 #Muss mit ECO-Wert von HK1 in Servicewelt übereinstimmen
HK2_min = 19
HK1_max = 25
HK2_max = 25
HK1_Diff_max = HK1_max - HK1_min
HK2_Diff_max = HK2_max - HK2_min 
AT_Diff_max = 14

# Freigabe WP aufgrund Raumtemp Nacht
T_min_Nacht = 21
T_max_Tag = 25
T_verz_Tag = 22
T_HK1_Nacht = 5
T_HK2_Nacht = 5


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
    return req.json()

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    logging.info("Ok? {}".format(postreq.ok))

def get_freigabezeit_12h_temp(t_roll_avg):
    u_w = UHRZEIT_WARM.hour + UHRZEIT_WARM.minute / 60
    u_k = UHRZEIT_KALT.hour + UHRZEIT_KALT.minute / 60
    f_time = u_w + (t_roll_avg - FREIGABE_WARM_T) * (
        (u_w - u_k) / (FREIGABE_WARM_T - FREIGABE_KALT_T))
    logging.info("Decimal Unlocktime: {}".format(f_time))
    f_time_12h_temp = datetime.time(
        hour=int(f_time), minute=int((f_time - int(f_time))*60))
    logging.info("DMS Unlocktime: {}".format(f_time_12h_temp))
    return(f_time_12h_temp)

def get_freigabezeit_excess(t_now):
    p_unlock_now = -(FREIGABE_WARM_P + (t_now - FREIGABE_WARM_TEMP) * (
        (FREIGABE_WARM_P - FREIGABE_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP)))
    logging.info("Freigabe_Leistung: {}".format(p_unlock_now))
    return p_unlock_now

def get_sperrleistung(t_now):
    p_lock_now = -(SPERRUNG_WARM_P + (t_now - FREIGABE_WARM_TEMP) * (
        (SPERRUNG_WARM_P - SPERRUNG_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP)))
    logging.info("Sperrung_Leistung: {}".format(p_lock_now))
    return p_lock_now

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
        UUID["PV_Produktion"], duration="-5min")["data"]["average"]
    #p_charge = get_vals(UUID["Charge_station"],
    #                    duration="-5min")["data"]["average"]
    #p_wp = get_vals(UUID["WP_Verbrauch"],
    #                    duration="-5min")["data"]["average"]
    p_net = power_balance 
    print("Aktuelle Bilanz p_net =",p_net)
    
    #Ausschaltsignal Sonderbetrieb 
    power_balance2 = get_vals(
        UUID["PV_Produktion"], duration="-45min")["data"]["average"]
    #p_charge2 = get_vals(UUID["Charge_station"],
    #                    duration="-30min")["data"]["average"]
    p_net2 = power_balance2 
    print("Aktuelle Bilanz p_net2=",p_net2)
        
    logging.info("Start Freigabe Zeit & Normalbetrieb")  
    f_time_12h_temp = get_freigabezeit_12h_temp(t_roll_avg_12)
    if now.time() > f_time_12h_temp:
        b_freigabe_12h_temp = 1
    if t_roll_avg_24 < FREIGABE_NORMAL_TEMP:
        b_freigabe_normal = 1
    logging.info("Freigabe Zeit Status: {}".format(b_freigabe_12h_temp))
    logging.info("Freigabe Normalbetrieb Status:{}".format(b_freigabe_normal))
    #write_vals(UUID["Freigabe_sonderbetrieb"], b_freigabe_12h_temp)
    write_vals(UUID["Freigabe_normalbetrieb"], b_freigabe_normal)
    logging.info("Ende Freigabe Zeit & Normalbetrieb")
    
    #Abrufen aktuelle Leistung Wärmepumpe
    wp_freigabe = 0
    wp_consumption = get_vals(
       UUID["WP_Verbrauch"], duration="-5min")["data"]["average"]
    if wp_consumption < 100:
        wp_freigabe = 1
    
    
    #Generiere Freigabe-sperrsignal Leistung & Raumttemperatur
    logging.info("Start Freigabe Leistung")
    
    RT_akt = get_vals(UUID["T_Raum"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-15min")["data"]["average"] 
      
    p_freigabe_now = get_freigabezeit_excess(t_now)
    p_sperrung_now = get_sperrleistung(t_now)
    
    T_Freigabe_Nacht = 0
    T_Freigabe_Tag = 0
    T_Verzoegerung_Tag = 0
    
    if RT_akt > T_verz_Tag: #Verzögerung WP Freigabe Tag wenn RT noch zu hoch
        T_Verzoegerung_Tag = 1
    if RT_akt > T_max_Tag: #Sperrung WP auf Grund zu hoher RT am Tag
        T_Freigabe_Tag = 1
    if p_net > p_freigabe_now: #Freigabe WP auf Grund von PV-Leistung
        b_freigabe_excess = 1
    if p_net2 < p_sperrung_now: #Sperrung WP auf Grund von PV-Leistung
        b_sperrung_excess = 1
    if RT_akt > T_min_Nacht: #Sperren WP auf Grund zu hoher RT in Nacht
        T_Freigabe_Nacht = 1
    logging.info("Freigabe Leistung: {}".format(b_freigabe_excess))
    logging.info("Sperrung Leistung: {}".format(b_sperrung_excess))
    logging.info("Verzögerung: {}".format(T_Verzoegerung_Tag))
    logging.info("WP_Leistung: {}".format(wp_freigabe))
    logging.info("Freigabe Tag: {}".format(T_Freigabe_Tag))
    logging.info("Freigabe Nacht: {}".format(T_Freigabe_Nacht))
    
    write_vals(UUID["Freigabe_excess"], b_freigabe_excess)
    write_vals(UUID["Sperrung_excess"], b_sperrung_excess)
    write_vals(UUID["t_Sperrung_Tag"], T_Freigabe_Tag)
    write_vals(UUID["t_Sperrung_Nacht"], T_Freigabe_Nacht)
    write_vals(UUID["t_Verzoegerung_Tag"], T_Verzoegerung_Tag)
    write_vals(UUID["WP_Freigabe"], wp_freigabe)
    write_vals(UUID["Bilanz_avg_aus"], p_net2)
    write_vals(UUID["Bilanz_avg_ein"], p_net)
   
    # Wenn RT in der Nacht über Soll-Wert liegt ist WP Raumtemp Eco HK1 & HK2 tief. 
            
    Freigabe = 0
    Sperrung = 0

   #Modbus Werte in für Sonderbetrieb ein schreiben 
    logging.info(f" ----------------------  Modbus Werte für Sonderbetrieb ein schreiben") 
    if (b_freigabe_normal & b_freigabe_12h_temp & b_freigabe_excess):
   # if True:
        #CLIENT.write_register(REGISTER["Komfort_HK1"], int(SB_EIN_HK1_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK1"], int(SB_EIN_HK1_ST*100))
        #CLIENT.write_register(REGISTER["Komfort_HK2"], int(SB_EIN_HK2_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK2"], int(SB_EIN_HK2_ST*100))
        CLIENT.write_register(REGISTER["Betriebsart"], int(3))
        #CLIENT.write_register(REGISTER["SG1"], int(1))
        #CLIENT.write_register(REGISTER["SG2"], int(1))
        Freigabe = 1
        logging.info("Sonderbetrieb ein: {}".format(Freigabe))
      
    #Modbus Werte für Sonderbetrieb aus schreiben
    logging.info(f" ----------------------  Modbus Werte für Sonderbetrieb aus schreiben") 
    if (T_Verzoegerung_Tag & wp_freigabe or T_Freigabe_Tag or b_sperrung_excess ):
        #CLIENT.write_register(REGISTER["Komfort_HK1"], int(SB_AUS_HK1_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK1"], int(SB_AUS_HK1_ST*100))
        #CLIENT.write_register(REGISTER["Komfort_HK2"], int(SB_AUS_HK2_T*10))
        #CLIENT.write_register(REGISTER["Steigung_HK2"], int(SB_AUS_HK2_ST*100))
        CLIENT.write_register(REGISTER["Betriebsart"], int(2))
        CLIENT.write_register(REGISTER["Eco_HK2"], int(HK2_min*10)) 
        #CLIENT.write_register(REGISTER["SG1"], int(0))
        #CLIENT.write_register(REGISTER["SG2"], int(0))
        Sperrung = 1
        logging.info("Sonderbetrieb aus: {}".format(Sperrung))
    
    if (T_Freigabe_Nacht):
        CLIENT.write_register(REGISTER["Eco_HK2"], int(T_HK2_Nacht*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(T_HK1_Nacht*10))       
            
            
 #Nachtabsenkung über Raspi
 #   if now.time() > AB_aus:
 #       b_absenk_aus = 1
 #   if now.time() < AB_ein:
 #       b_absenk_ein = 1
 #       
 #   if  (b_absenk_aus & b_absenk_ein):
 #       CLIENT.write_register(REGISTER["Eco_HK1"], int(AB_AUS_HK1_T*10))
 #       CLIENT.write_register(REGISTER["Eco_HK2"], int(AB_AUS_HK2_T*10))
 #           
 #   else:
 #      CLIENT.write_register(REGISTER["Eco_HK1"], int(AB_EIN_HK1_T*10))
 #      CLIENT.write_register(REGISTER["Eco_HK2"], int(AB_EIN_HK2_T*10))   

  #Schreiben Soll-Temp HK1 in Abhängigkeit von PV-Leistung 
    logging.info(f" ----------------------  Temp HK 1 & 2 in Abhängigkeit von PV Leistung.") 
    
    PV_Aktuell = get_vals(UUID["PV_Produktion"],
                        duration="-30min")["data"]["average"]
    t_roll_avg_12_24 = get_vals(
        UUID["T_outdoor"], duration="-1444min+720min")["data"]["average"]
    logging.info("T_12_24: {}".format(t_roll_avg_12_24))  
    logging.info("PV_Aktuell: {}".format(PV_Aktuell))   
    if  (PV_Aktuell/PV_max) > 1:
        PV_Faktor = 1
    else:
        PV_Faktor = PV_Aktuell/PV_max
    logging.info("PV_Faktor: {}".format(PV_Faktor))
        
    if  ((FREIGABE_NORMAL_TEMP - t_roll_avg_12_24)/AT_Diff_max) > 1:
        Temp_Faktor = 1   
    else:
        Temp_Faktor = (FREIGABE_NORMAL_TEMP-t_roll_avg_12)/AT_Diff_max
    logging.info("Temp_Faktor: {}".format(Temp_Faktor))  
     
    HK1_aktuell = HK1_min + HK1_Diff_max * PV_Faktor
    HK2_aktuell = HK2_min + HK2_Diff_max * PV_Faktor
    logging.info("HK1_aktuell: {}".format(HK1_aktuell))  
    logging.info("HK2_aktuell: {}".format(HK2_aktuell))  
        
    CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_aktuell*10))    
    CLIENT.write_register(REGISTER["Komfort_HK2"], int(HK2_aktuell*10))     
   
    
     # Sperrung WP wegen Raumtemp (Tag & Nacht)
    #logging.info(f" ----------------------  Sperrung WP wegen Raumtemp. Tag & Nacht.") 
    #RT_akt = get_vals(UUID["T_Raum"],
                        #duration="-15min")["data"]["average"] 
        
    
    
    #T_Freigabe_Tag = 0
    #elif RT_akt > T_max_Tag:
         #T_Freigabe_Tag = 1
    #logging.info("Sperrung Leistung Temp Tag: {}".format(T_Freigabe_Tag))        
    #if (T_Freigabe_Tag):
         #CLIENT.write_register(REGISTER["Eco_HK1"], int(T_HK1_Nacht*10))  
         #CLIENT.write_register(REGISTER["Eco_HK2"], int(T_HK2_Nacht*10))
    
    # Aktueller Betriebszustand WP auslesen. 
        
    #Betrieb = CLIENT.read_holding_registers(REGISTER["Betriebsart"], count=0)
    #print(Betrieb)
    #logging.info("Betriebszustand: {}".format(Betrieb)) 
    #write_vals(UUID["Betrieb_Z"], Betrieb)
    
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
