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
    "t_Sperrung_Nacht": "e2bc2ee0-52de-11e9-a86c-1d6437911028",
    "t_Verzoegerung_Tag": "f60ca430-4a61-11e9-8fa1-47cb405220bd",
    "WP_Freigabe": "232bec80-7a2a-11ea-b704-0de0b4780fba",
    "Freigabe_WP": "90212900-d972-11e9-910d-078a5d14d2c9",
    "Sperrung_WP": "dd2e3400-d973-11e9-b9c6-038d9113070b",
    "Freigabe_normalbetrieb": "fc610770-d9fb-11e9-8d49-5d7c9d433358",
    "PV_Produktion": "101ca060-50a3-11e9-a591-cf9db01e4ddd", 
    "WP_Verbrauch": "92096720-35ae-11e9-a74c-534de753ada9",
    "T_Raum_EG": "d8320a80-5314-11ea-8deb-5944d31b0b3c",
    "T_Raum_OG": "70d65570-4a61-11e9-b638-fb0f3e7a4677",
    "WW_Temp_oben": "e207c010-3630-11ea-8ccb-fdd7c2918630"
}

# t-sperrung Nacht löschen, WP Freigabe, ladestation, WP Verbrauch löschen ==> Reserven

# Parameter Freigabe Heizbetrieb
FREIGABE_NORMAL_TEMP = 15

#Parameter Freigabe Komfortbetrieb
FREIGABE_WARM_P = -700
FREIGABE_KALT_P = -1000
FREIGABE_WARM_TEMP = 15
FREIGABE_KALT_TEMP = -10
SPERRUNG_HYST = 400 # Hysterese zur Sperrung Komfortbetrieb

#Parameter Absenk- und Komfortbetrieb
HK1_min = 5 # Tempvorgabe für Absenkbetrieb Pufferspeicher 
HK2_min = 20 # Tempvorgabe für Absenkbetrieb Heizgruppe
HK1_max = 32 # Tempvorgabe für Komfortbetrieb Pufferspeicher
HK2_max = 28 # Tempvorgabe für Komfortbetrieb Heizgruppe

# Parameter Freigabe Raumtemperaturen
#T_min_Nacht = 21 # Minimaltemp für EG Nacht
T_max_Tag = 22.5 # Maximaltemp OG für Sperrung WP
T_min_Tag = 21 # Minimale Raumtemp EG zur Freigabe WP
#T_HK1_Nacht = 5 # Tempvorgabe für Absenkbetrieb nur mit Umwälzpumpe
#T_HK2_Nacht = 5 #Tempvorgabe für Absenkbetrieb nur mit Umwälzpumpe

#Parameter WW-Ladung
ww_start = datetime.time(12, 0)
ww_stop = datetime.time(14, 0)
ww_max = 44 #Diese Temperatur muss erreicht werden damit WW-Betrieb beendet wird (VL-Temp WP)

REGISTER = {
    "Komfort_HK1": 1501,
    "Eco_HK1": 1502,
    "Steigung_HK1": 1503,
    "Komfort_HK2": 1504,
    "Eco_HK2": 1505,
    "Steigung_HK2": 1506, 
    "Betriebsart": 1500,
    "WW_Temp": 521
}

IP_ISG = "192.168.178.36"

CLIENT = ModbusTcpClient(IP_ISG)
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

def main():
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    tz = pytz.timezone('Europe/Zurich')
    now = datetime.datetime.now(tz=tz)
    logging.info("Swiss time: {}".format(now))
    logging.info("*****************************")
    
    logging.info(f"---------- Prüfung Freigabe / Sperrung Heizgrenze ----------") 
    b_freigabe_normal = 0
    
    # Abfrage aktuelle Aussentemperatur
    t_now = get_vals(UUID["T_outdoor"])["data"]["tuples"][0][1]
    
    # Abfragen 24h Aussentemperatur und ggf. Freigabe Heizgrenze
    t_roll_avg_24 = get_vals(
        UUID["T_outdoor"], duration="-1440min")["data"]["average"]
    if t_roll_avg_24 < FREIGABE_NORMAL_TEMP:
        b_freigabe_normal = 1
    write_vals(UUID["Freigabe_normalbetrieb"], b_freigabe_normal)
    
    #logging.info("Aktuelle Aussentemperatur: {}".format(t_now))
    logging.info("24h Aussentemperatur ({}°C) < Heizgrenze ({}°C): {}".format(t_roll_avg_24,FREIGABE_NORMAL_TEMP,b_freigabe_normal))
     
    logging.info(f"---------- Prüfung Freigabe / Sperrung Sonderbetrieb ----------") 
    b_freigabe_wp = 0
    b_sperrung_wp = 0
    
    #Abfragen aktuelle Energiebilanz zur Prüfung Freigabe Sonderbetrieb
    power_balance = get_vals(
        UUID["PV_Produktion"], duration="-15min")["data"]["average"]
    p_net = power_balance 
    #logging.info("PV-Produktion Einschaltschwelle (15min): {}".format(p_net))
    
    #Abfragen aktuelle Energiebilanz zur Prüfung Sperrung Sonderbetrieb
    power_balance2 = get_vals(
        UUID["PV_Produktion"], duration="-45min")["data"]["average"]
    p_net2 = power_balance2 
    #logging.info("PV-Produktion Ausschaltschwelle (45min): {}".format(p_net2))
    
    # Aktuelle Einschaltschwelle Sonderbetrieb    
    p_freigabe_now = -(FREIGABE_WARM_P + (t_now - FREIGABE_WARM_TEMP) * 
        (FREIGABE_WARM_P - FREIGABE_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP))
    #logging.info("Freigabe_Leistung: {}".format(p_freigabe_now))
    
    # Aktuelle Ausschaltschwelle Sonderbetrieb
    p_sperrung_now = p_freigabe_now-SPERRUNG_HYST
    #logging.info("Sperrung_Leistung: {}".format(p_sperrung_now))
    
    if p_net > p_freigabe_now: #Freigabe WP auf Grund von PV-Leistung
        b_freigabe_wp = 1
    if p_net2 < p_sperrung_now: #Sperrung WP auf Grund von PV-Leistung
        b_sperrung_wp = 1
    
    write_vals(UUID["Freigabe_WP"], b_freigabe_wp) # Aktiv wenn ausreichend PV Leistung vorhanden
    write_vals(UUID["Sperrung_WP"], b_sperrung_wp) # Aktiv wenn zu wenig PV Leistung vorhanden
    logging.info("15 min PV-Leistung ({} W) > Einschaltschwelle ({} W): {}".format(p_net,p_freigabe_now,b_freigabe_wp))
    logging.info("45 min PV-Leistung ({} W) < Ausschaltschwelle ({}) W: {}".format(p_net2,p_sperrung_now,b_sperrung_wp))    
        
    logging.info(f"---------- Prüfung Freigabe / Sperrung Raumtemperaturen ----------") 
    #T_Freigabe_Nacht = 0
    T_Freigabe_max = 0
    T_Freigabe_min = 0
    
    #Abfragen aktuelle Raumtemperaturen EG & OG
    RT_akt_EG = get_vals(UUID["T_Raum_EG"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-30min")["data"]["average"] 
    
    RT_akt_OG = get_vals(UUID["T_Raum_OG"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-30min")["data"]["average"] 
    
    #logging.info("Aktuelle Raumtemp EG: {}".format(RT_akt_EG))
    #logging.info("Aktueller Raumtemp OG: {}".format(RT_akt_OG))
    
    # Definition Betriebsfreigaben
    if RT_akt_EG > T_min_Tag: #Sperrung WP wenn Raumtemp EG zu hoch
        T_Freigabe_min = 1
    if RT_akt_OG > T_max_Tag: #Sperrung WP wenn Raumtemp OG zu hoch
        T_Freigabe_max = 1
    #if RT_akt_EG > T_min_Nacht: #Sperren WP Nacht wenn Raumtemp im EG zu hoch
    #    T_Freigabe_Nacht = 1
        
    write_vals(UUID["t_Verzoegerung_Tag"], T_Freigabe_min) # 1 wenn RT EG > 21.5°C 
    write_vals(UUID["t_Sperrung_Tag"], T_Freigabe_max) # 1 wenn RT OG > 22.5°C
    #write_vals(UUID["t_Sperrung_Nacht"], T_Freigabe_Nacht) # 1 wenn RT EG > 21°C
   
    logging.info("Raumtemp EG ({}°C) > Einschaltschwelle ({}°C): {}".format(RT_akt_EG,T_min_Tag,T_Freigabe_min))
    logging.info("Raumtemp OG ({}°C) > Ausschaltschwelle ({}°C): {}".format(RT_akt_OG,T_max_Tag,T_Freigabe_max))
    #logging.info("Temp EG zu hoch {}°C: {}".format(T_min_Nacht,T_Freigabe_Nacht))
        
    logging.info(f"---------- Prüfung Freigabe / Sperrung Warmwasserbetrieb ----------") 
    ww_time = 0
    Ww_max = 1
    
    #Formatierung Freigabezeiten Warmwasser
    Ww_start = datetime.time(hour=int(ww_start.hour), minute=int((ww_start.hour - int(ww_start.hour))*60)) # Freigabezeit Warmwasser
    Ww_stop = datetime.time(hour=int(ww_stop.hour), minute=int((ww_stop.hour - int(ww_stop.hour))*60)) # Freigabezeit Warmwasser
    
    #Auslesen aktuelle Warmwassertemperatur
    #ww_temp = (CLIENT.read_input_registers(REGISTER["WW_Temp"], count=1, unit = 1)).getRegister(0) / 10   
        
    ww_temp = get_vals(
        UUID["WW_Temp_oben"], duration="-1min")["data"]["average"]
    
    logging.info("Aktuelle WW-Speichertemp: {}".format(ww_temp))
    
    if ww_temp > ww_max:
        Ww_max = 0
    
    if now.time() > Ww_start and now.time() < Ww_stop:
        ww_time = 1
    
    logging.info("Ist-Wert WW-Temp ({}°C) < Soll-Wert WW-Temp ({}°C): {}".format(ww_temp,ww_max,Ww_max))
    logging.info("Aktuelle Uhrzeit ({}) in Zeitfenster ({} - {} Uhr): {}".format(now.time(),ww_start,ww_stop,ww_time))
   
     
    logging.info(f"---------- Schreiben Betriebsfälle ----------") 
    # Freigabe Programmbetrieb für Erzeugung Warmwasser während Zeitfenster bis max. Vorlauftemperatur erreicht ist. 
    if (ww_time ans Ww_max):
        logging.info(f"WW-Betrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(5))
    
    #Anlage in Bereitschaft schalten wenn Raumtemperatur EG über 21°C und nicht ausreichend PV Leistung vorhanden oder Raumtemp OG zu hoch.
    elif (T_Freigabe_min and b_freigabe_wp == 0 or T_Freigabe_max):
        logging.info(f"Bereitschaftsbetrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(1))
    
    #Freigabe Sonderbetrieb wenn Heizgrenze erreicht und ausreichend PV-Leistung vorhanden 
    elif (b_freigabe_normal & b_freigabe_wp):
        logging.info(f"Komfortbetrieb")
        CLIENT.write_register(REGISTER["Betriebsart"], int(3))
        CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_max*10))    
        CLIENT.write_register(REGISTER["Komfort_HK2"], int(HK2_max*10))  
         
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv aber zu warm im Raum (==> Es läuft nur Umwälzpumpe)
#     elif (b_freigabe_normal & T_Freigabe_Nacht):
#         logging.info(f" ==> Absenkbetrieb nur Umwälzpumpe")
#         CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv
#         CLIENT.write_register(REGISTER["Eco_HK2"], int(T_HK2_Nacht*10))   
#         CLIENT.write_register(REGISTER["Eco_HK1"], int(T_HK1_Nacht*10))
        
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv und zu wenig PV-Leistung
    elif (b_freigabe_normal & b_sperrung_wp):
        logging.info(f" Absenkbetrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv.
        CLIENT.write_register(REGISTER["Eco_HK2"], int(HK2_min*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(HK1_min*10))
    
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
