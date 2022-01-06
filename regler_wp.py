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
    "T_Raum_OG": "70d65570-4a61-11e9-b638-fb0f3e7a4677"
}

# Freigabewert für Sonderbetrieb nach Heizgrenze
FREIGABE_NORMAL_TEMP = 15

#Freigabewerte für Sonderbetrieb nach Leistung
FREIGABE_WARM_P = -700
FREIGABE_KALT_P = -1000
FREIGABE_WARM_TEMP = 15
FREIGABE_KALT_TEMP = -10
SPERRUNG_WARM_P = FREIGABE_WARM_P + 400
SPERRUNG_KALT_P = FREIGABE_KALT_P + 400

#Sollwerte für Regulierung HK1 nach PV-Produktion & Temp
PV_max = 2000
HK1_min = 5 #Pufferspeicher 
HK2_min = 20 #Heizgruppe
HK1_max = 32
HK2_max = 28
HK1_Diff_max = HK1_max - HK1_min
HK2_Diff_max = HK2_max - HK2_min 
AT_Diff_max = 14

# Freigabe WP aufgrund Raumtemp Nacht
T_min_Nacht = 21
T_max_Tag = 22.5
T_verz_Tag = 21.5
T_HK1_Nacht = 5
T_HK2_Nacht = 5

#Freigabe WW Ladung
ww_start = datetime.time(12, 0)
ww_stop = datetime.time(14, 0)
ww_max = 45 #Diese Temperatur muss erreicht werden damit WW-Betrieb beendet wird (VL-Temp WP)

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
    tz = pytz.timezone('Europe/Zurich')
    b_freigabe_12h_temp = 0
    b_freigabe_wp = 0
    b_sperrung_wp = 0
    b_freigabe_normal = 0
    b_absenk_aus = 0
    b_absenk_ein = 0
    logging.basicConfig(level=logging.INFO)
    logging.info("*****************************")
    logging.info("*Starting WP controller")
    now = datetime.datetime.now(tz=tz)
    logging.info("Swiss time: {}".format(now))
    logging.info("*****************************")
    
    logging.info(f"---------- Prüfung Freigabe / Sperrung Heizgrenze ----------") 
    
    # Abfrage aktuelle Aussentemperatur
    t_now = get_vals(UUID["T_outdoor"])["data"]["tuples"][0][1]
    logging.info("Aktuelle Aussentemperatur: {}".format(t_now))
    logging.info("Heizgrenze: {}".format(FREIGABE_NORMAL_TEMP))
    
    # Abfragen 24h Aussentemperatur und ggf. Freigabe Heizgrenze
    t_roll_avg_24 = get_vals(
        UUID["T_outdoor"], duration="-1440min")["data"]["average"]
    if t_roll_avg_24 < FREIGABE_NORMAL_TEMP:
        b_freigabe_normal = 1
    write_vals(UUID["Freigabe_normalbetrieb"], b_freigabe_normal)   
    logging.info("Freigabe Normalbetrieb:{}".format(b_freigabe_normal))
     
    logging.info(f"---------- Prüfung Freigabe / Sperrung Sonderbetrieb ----------") 
    
    #Abfragen aktuelle Energiebilanz zur Prüfung Freigabe Sonderbetrieb
    power_balance = get_vals(
        UUID["PV_Produktion"], duration="-15min")["data"]["average"]
    p_net = power_balance 
    logging.info("Aktuelle Energiebilanz für Freigabe: {}".format(p_net))
    
    #Abfragen aktuelle Energiebilanz zur Prüfung Sperrung Sonderbetrieb
    power_balance2 = get_vals(
        UUID["PV_Produktion"], duration="-45min")["data"]["average"]
    p_net2 = power_balance2 
    logging.info("Aktuelle Energiebilanz für Sperrung: {}".format(p_net2))
    
    # Aktuelle Einschaltschwelle Sonderbetrieb    
    p_freigabe_now = -(FREIGABE_WARM_P + (t_now - FREIGABE_WARM_TEMP) * (
        (FREIGABE_WARM_P - FREIGABE_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP)))
    logging.info("Freigabe_Leistung: {}".format(p_freigabe_now))
    
    # Aktuelle Ausschaltschwelle Sonderbetrieb
    p_sperrung_now = -(SPERRUNG_WARM_P + (t_now - FREIGABE_WARM_TEMP) * (
        (SPERRUNG_WARM_P - SPERRUNG_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP)))
    logging.info("Sperrung_Leistung: {}".format(p_sperrung_now))
    
    if p_net > p_freigabe_now: #Freigabe WP auf Grund von PV-Leistung
        b_freigabe_wp = 1
    if p_net2 < p_sperrung_now: #Sperrung WP auf Grund von PV-Leistung
        b_sperrung_wp = 1
        
    logging.info("Freigabe Leistung: {}".format(b_freigabe_wp))
    logging.info("Sperrung Leistung: {}".format(b_sperrung_wp))    
        
    logging.info(f"---------- Prüfung Freigabe / Sperrung Raumtemperaturen ----------") 
    
    
    
    
    
    
    logging.info(f"---------- Prüfung Freigabe / Sperrung Warmwasserbetrieb ----------") 
    
    
    
    

    #Abrufen aktuelle Leistung Wärmepumpe ==> Prüfen ob WP ausgeschaltet
#     wp_freigabe = 0
#     wp_consumption = get_vals(
#        UUID["WP_Verbrauch"], duration="-5min")["data"]["average"]
#     if wp_consumption < 100:
#         wp_freigabe = 1
    
    #Abrufen aktuelle Warmwassertemp Speicher unten:
    ww_temp = (CLIENT.read_input_registers(REGISTER["WW_Temp"], count=1, unit = 1)).getRegister(0) / 10   
    logging.info("Aktuelle WW-Speichertemp unten: {}".format(ww_temp))
    Ww_max = True
    if ww_temp > ww_max:
        Ww_max = False
   
    
  
   
    #Generiere Freigabe-sperrsignal Leistung & Raumttemperatur
    
    RT_akt_EG = get_vals(UUID["T_Raum_EG"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-15min")["data"]["average"] 
    
    RT_akt_OG = get_vals(UUID["T_Raum_OG"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-15min")["data"]["average"] 
    
    logging.info("Aktuelle Raumtemp EG: {}".format(RT_akt_EG))
    logging.info("Aktueller Raumtemp OG: {}".format(RT_akt_OG))
    
  
    
    T_Freigabe_Nacht = 0
    T_Freigabe_Tag = 0
    T_Verzoegerung_Tag = 0
    
    if RT_akt_EG > T_verz_Tag: #Verzögerung WP Freigabe Tag wenn RT noch zu hoch
        T_Verzoegerung_Tag = 1
    if RT_akt_OG > T_max_Tag: #Sperrung WP auf Grund zu hoher RT am Tag
        T_Freigabe_Tag = 1
    
    if RT_akt_EG > T_min_Nacht: #Sperren WP auf Grund zu hoher RT in Nacht
        T_Freigabe_Nacht = 1
        
    
    
    logging.info("Verzögerung (Temperatur zu hoch wenn 1): {}".format(T_Verzoegerung_Tag))
    logging.info("WP_Leistung (ausgeschaltet wenn 1): {}".format(wp_freigabe))
    logging.info("Freigabe Tag (Temperatur zu hoch wenn 1): {}".format(T_Freigabe_Tag))
    logging.info("Freigabe Nacht (Temperatur zu hoch wenn 1): {}".format(T_Freigabe_Nacht))
    
    write_vals(UUID["Freigabe_WP"], b_freigabe_wp) # Aktiv wenn ausreichend PV Leistung vorhanden
    write_vals(UUID["Sperrung_WP"], b_sperrung_wp) # Aktiv wenn zu wenig PV Leistung vorhanden
    write_vals(UUID["t_Sperrung_Tag"], T_Freigabe_Tag) # Aktiv wenn RT > 25°C
    write_vals(UUID["t_Sperrung_Nacht"], T_Freigabe_Nacht) # 1 wenn RT > 21
    write_vals(UUID["t_Verzoegerung_Tag"], T_Verzoegerung_Tag) # Aktiv wenn RT > 21°C
    write_vals(UUID["WP_Freigabe"], wp_freigabe) # ==> Ist WP ausgeschaltet
   
    #Formatierung Freigabezeiten Warmwasser
    Ww_start = datetime.time(hour=int(ww_start.hour), minute=int((ww_start.hour - int(ww_start.hour))*60)) # Freigabezeit Warmwasser
    Ww_stop = datetime.time(hour=int(ww_stop.hour), minute=int((ww_stop.hour - int(ww_stop.hour))*60)) # Freigabezeit Warmwasser
     
    logging.info(f"---------- Schreiben Betriebsfälle ----------") 
    # Freigabe Programmbetrieb für Erzeugung Warmwasser während Zeitfenster bis max. Vorlauftemperatur erreicht ist. 
    if (now.time() > Ww_start and now.time() < Ww_stop and Ww_max):
        logging.info(f" ---------- WW-Betrieb ----------") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(5))
        WW_Betrieb = 1
        logging.info("WW-Betrieb: {}".format(WW_Betrieb))
    
    #Anlage in Bereitschaft schalten wenn Raumtemperatur über 21°C und nicht ausreichend PV Leistung oder Raumtemp OG zu hoch vorhanden.
    elif (T_Verzoegerung_Tag and b_freigabe_wp == 0 or T_Freigabe_Tag):
        logging.info(f" ---------- Bereitschaftsbetrieb ----------") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(1))
        Sperrung = 1
        logging.info("Bereitschaftsbetrieb, Anlage aus: {}".format(Sperrung))
    
    #Freigabe Sonderbetrieb wenn Heizgrenze erreicht und ausreichend PV-Leistung vorhanden 
    elif (b_freigabe_normal & b_freigabe_wp):
        logging.info(f" ---------- Sonderbetrieb ----------")
        CLIENT.write_register(REGISTER["Betriebsart"], int(3))
        CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_max*10))    
        CLIENT.write_register(REGISTER["Komfort_HK2"], int(HK2_max*10))  
        Freigabe = 1
        logging.info("Sonderbetrieb ein: {}".format(Freigabe))
        logging.info("HK1_aktuell: {}".format(HK1_max))  
        logging.info("HK2_aktuell: {}".format(HK2_max)) 
         
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv aber zu warm im Raum (==> Es läuft nur Umwälzpumpe)
    elif (b_freigabe_normal & T_Freigabe_Nacht):
        logging.info(f" ---------- Absenkbetrieb nur Umwälzpumpe ----------")
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv
        CLIENT.write_register(REGISTER["Eco_HK2"], int(T_HK2_Nacht*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(T_HK1_Nacht*10))
        Absenkbetrieb = 1
        logging.info("Nur Umwälzpumpe ein: {}".format(Absenkbetrieb))
        logging.info("HK1_aktuell: {}".format(T_HK1_Nacht))  
        logging.info("HK2_aktuell: {}".format(T_HK2_Nacht)) 
        
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv und zu wenig PV-Leistung
    elif (b_freigabe_normal & b_sperrung_wp):
        logging.info(f" ---------- Absenkbetrieb WP & Umwälzpumpe ----------") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv.
        CLIENT.write_register(REGISTER["Eco_HK2"], int(HK2_min*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(HK1_min*10))
        Absenkbetrieb = 1
        logging.info("Absenkbetrieb ein: {}".format(Absenkbetrieb))
        logging.info("HK1_aktuell: {}".format(HK1_min))  
        logging.info("HK2_aktuell: {}".format(HK2_min))  
    
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
