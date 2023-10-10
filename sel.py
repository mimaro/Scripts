import requests
import json
import pprint
import datetime
import logging
import pytz
import time
from pymodbus.client.sync import ModbusTcpClient

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"


########################################################################################################



#######################################################################################################
# Configuration
UUID = {
    "P_Wagenrain_8a": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "P_PV-Anlage": "0ece9080-6732-11ee-92bb-d5c31bcb9442",
    "P_Wärmepumpe": "1b029800-6732-11ee-ae2e-9715cbeba615"
}

REGISTER = {
    "P_PV-Anlage": 1501,
    "E_PV-Anlage": 1502,
    "P_Wagenrain_8a": 1503,
    "E_Wagenrain_8a": 1504,
    "P_Wärmepumpe": 1505,
    "E_Wärmepumpe": 1506
}

SEL_TCP = "192.168.178.40"

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
         
        
    logging.info(f"---------- Prüfung Freigabe / Sperrung Raumtemperaturen ----------") 
     
        
        
    write_vals(UUID["t_Verzoegerung_Tag"], T_Freigabe_min) # 1 wenn RT EG > 21°C 
    write_vals(UUID["t_Sperrung_Tag"], T_Freigabe_max) # 1 wenn RT OG > 22.5°C
    #write_vals(UUID["T_Absenk"], T_Freigabe_Absenk) # 1 wenn RT EG < 21.5°C
   
   
    logging.info("Raumtemp EG ({}°C) > Einschaltschwelle ({}°C): {}".format(RT_akt_EG,T_min_Tag,T_Freigabe_min))
    logging.info("Raumtemp OG ({}°C) > Ausschaltschwelle ({}°C): {}".format(RT_akt_OG,T_max_Tag_OG,T_Freigabe_max))
    logging.info("Raumtemp EG ({}°C) > Ausschaltschwelle ({}°C) : {}".format(RT_akt_EG, T_max_Tag_EG, T_Freigabe_max))
    logging.info("Raumtemp EG ({}°C) < Freigabe Absenkbetrieb ({}°C): {}".format(RT_akt_EG,T_Absenk,T_Freigabe_Absenk))
    logging.info("Raumtemp OG ({}°C) < Freigabe Absenkbetrieb ({}°C): {}".format(RT_akt_OG,T_Absenk,T_Freigabe_Betr))
    

    
    logging.info(f"---------- Prüfung Freigabe / Sperrung Sonnenuntergang ----------") 
    #r = requests.get(SUNSET_URL, verify=False) # Daten abfragen
    r = requests.get(SUNSET_URL) 
    
    now_CH = now.time().hour
    tz_UTC = pytz.utc
    now_UTC = datetime.datetime.now(tz=tz_UTC).hour
    d_time = now_CH - now_UTC
    
    data = json.loads(r.content)
    sunset = data['results']['sunset'] # Daten für Sonnenuntergang
    sunset_time_UTC = datetime.datetime(int(sunset[0:4]), int(sunset[5:7]), int(sunset[8:10]),int(sunset[11:13]), int(sunset[14:16])) # Sonnenuntergang in Zeit-Format umwandeln
    sunset_time_CH = sunset_time_UTC + datetime.timedelta(hours=d_time) #Aktueller Zeitpunkt Sonnenuntergang
    time_now = now.time() #Aktuelle Zeit

    t_delta_sunset_freigabe = ((T_FREIGABE_MAX - T_FREIGABE_MIN) / (AT_MAX - AT_MIN)) *(AT_MAX-t_roll_avg_24) + T_FREIGABE_MIN
    t_sunset_freigabe = (sunset_time_CH - datetime.timedelta(hours=t_delta_sunset_freigabe)).time() #Berechneter Freigabezeitpunkt Sonderbetrieb in Abhängigkeit 24h AT
    
    sunset_freigabe = 0
    if time_now > t_sunset_freigabe:
        sunset_freigabe = 1
    
    write_vals(UUID["t_Sperrung_Sonnenuntergang"], sunset_freigabe) 
   
    logging.info("sunset time CH: {}".format(sunset_time_CH))
    logging.info("time now: {}".format(time_now))    
    logging.info("24 h AT: {}".format(t_roll_avg_24))
    logging.info("Zeitpunkt Freigabe vor Sonnenuntergang: {}".format(t_delta_sunset_freigabe))
    logging.info("Freigabezeitpunkt: {}".format(t_sunset_freigabe))
    logging.info("time sunset freigabe: {}".format(sunset_freigabe))
    
    logging.info(f"---------- Prüfung Freigabe / Sperrung Warmwasserbetrieb ----------") 
    ww_time = 0
    Ww_aus = 0
    Ww_ein = 0
    
    #Formatierung Freigabezeiten Warmwasser
    Ww_start = datetime.time(hour=int(ww_start.hour), minute=int((ww_start.hour - int(ww_start.hour))*60)) # Freigabezeit Warmwasser
    Ww_stop = datetime.time(hour=int(ww_stop.hour), minute=int((ww_stop.hour - int(ww_stop.hour))*60)) # Freigabezeit Warmwasser 
        
    ww_temp = get_vals(
        UUID["WW_Temp_mitte"], duration="-1min")["data"]["average"]
    
    logging.info("Aktuelle WW-Speichertemp mitte: {}".format(ww_temp))
    
    if ww_temp >= ww_aus:
        Ww_aus = 1
    
    if (ww_aus - ww_temp) > ww_hyst:  
        Ww_ein = 1
    
    if now.time() > Ww_start and now.time() < Ww_stop:
        ww_time = 1
    
    logging.info("Ist-Wert WW-Temp ({}°C) < Einschalt-Wert WW-Temp ({}°C): WW_Freigabe {}".format(ww_temp,ww_aus-ww_hyst,Ww_ein))
    logging.info("Ist-Wert WW-Temp ({}°C) >= Ausschalt-Wert WW-Temp ({}°C): WW_Sperrung {}".format(ww_temp,ww_aus,Ww_aus))
    logging.info("Aktuelle Uhrzeit ({}) in Zeitfenster ({} - {} Uhr): {}".format(now.time(),ww_start,ww_stop,ww_time))
   
     
    logging.info(f"---------- Schreiben Betriebsfälle ----------")   
    
    # Freigabe Programmbetrieb für Erzeugung Warmwasser während Zeitfenster bis max. Vorlauftemperatur erreicht ist. 
         
    if (ww_time and Ww_aus == 0) or (ww_time and Ww_ein):
        logging.info(f"WW-Betrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(2))
        time.sleep(5)
        CLIENT.write_register(REGISTER["WW_Eco"], ww_soll*10)      
           
    #Anlage in Bereitschaft schalten wenn Raumtemperatur EG über 21°C und nicht ausreichend PV Leistung vorhanden oder Raumtemp OG zu hoch.
    elif (T_Freigabe_min and b_freigabe_wp == 0 or T_Freigabe_max):
        logging.info(f"Bereitschaftsbetrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(1))
        CLIENT.write_register(REGISTER["WW_Eco"], 100)
    
    #Freigabe Sonderbetrieb wenn Heizgrenze erreicht, ausreichend PV-Leistung vorhanden und Freigabe vor Sonnenuntergang erreicht
    elif (b_freigabe_normal & b_freigabe_wp & sunset_freigabe):
        logging.info(f"Komfortbetrieb")
        CLIENT.write_register(REGISTER["Betriebsart"], int(3))
        CLIENT.write_register(REGISTER["Komfort_HK1"], int(HK1_max*10))    
        CLIENT.write_register(REGISTER["Komfort_HK2"], int(HK2_max*10))  
        CLIENT.write_register(REGISTER["WW_Eco"], 100)
               
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv 
    elif (b_freigabe_normal & T_Freigabe_Absenk ): #b_sperrung_wp
        logging.info(f" Absenkbetrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv.
        CLIENT.write_register(REGISTER["Eco_HK2"], int(HK2_min*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(HK1_min*10))
        CLIENT.write_register(REGISTER["WW_Eco"], 100)
        
    else:
        logging.info(f"Beibehalten aktuelle Betriebsart") 
        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()

