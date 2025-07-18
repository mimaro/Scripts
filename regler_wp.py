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
SUNSET_URL = 'https://api.sunrise-sunset.org/json?lat=47.386479&lng=8.252473&formatted=0' 

########################################################################################################



#######################################################################################################
# Configuration
UUID = {
    "T_outdoor": "308e0d90-6521-11ee-8b08-a34757253caf",
    "Power_balance": "e3fc7a80-6731-11ee-8571-5bf96a498b43",
    "Charge_station": "8270f520-6690-11e9-9272-4dde30159c8f",
    "t_Sperrung_Tag": "3ee81940-6525-11ee-ab8d-95d8fe8c84c1",
    "t_Sperrung_Sonnenuntergang": "48d326e0-6525-11ee-bb62-d9a673cf575c",
    "t_Verzoegerung_Tag": "525c79d0-6525-11ee-a4de-35b9b54b853f",
    "Freigabe_WP": "2dd47740-6525-11ee-8430-33ffcdf1f22e",
    "Sperrung_WP": "35a4c530-6525-11ee-9aab-7be80c763665",
    "Freigabe_normalbetrieb": "1f9b1a00-6525-11ee-a1c0-218fa15dedcf",
    "PV_Produktion": "0ece9080-6732-11ee-92bb-d5c31bcb9442", 
    "WP_Verbrauch": "1b029800-6732-11ee-ae2e-9715cbeba615",
    "T_Raum_EG": "716e8d00-6523-11ee-a6d5-958aeed3d121",
    "T_Raum_OG": "78afd3c0-6523-11ee-980e-9fe998eb4bc6",
    "WW_Temp_mitte": "adf0da80-6522-11ee-82a3-4fe8ca3dfa5c",
    "Puffer_Temp_oben": "59bd6680-6523-11ee-b354-998ee384c361",
    "T_Absenk_F": "65bf3760-6cc2-11ee-a9fc-972ab9d69e77",
    "WW_Time": "24fb6470-7423-11ee-a18e-514019c4b69a",
    "WW_Ein": "54ce3e80-7423-11ee-8ce6-bbd29c465ad6",
    "Steigung_HK": "1ad2ca90-becb-11ef-870c-3f013969b33b"

}

# WP Freigabe, ladestation, WP Verbrauch löschen ==> Reserven

# Parameter Freigabe Heizbetrieb
FREIGABE_NORMAL_TEMP = 14.5
FREIGABE_NORMAL_TEMP_HYST = 15

#Parameter Freigabe Komfortbetrieb
FREIGABE_WARM_P = -400
FREIGABE_KALT_P = -800
FREIGABE_WARM_TEMP = 15
FREIGABE_KALT_TEMP = -10
SPERRUNG_HYST = 500 # Hysterese zur Sperrung Komfortbetrieb

#Parameter Absenk- und Komfortbetrieb
HK1_min = 5 # Tempvorgabe für Absenkbetrieb Pufferspeicher 
HK2_min = 21 # Tempvorgabe für Absenkbetrieb Heizgruppe, 
HK1_max = 30 # Tempvorgabe für Komfortbetrieb Pufferspeicher
HK2_max = 30 # Tempvorgabe für Komfortbetrieb Heizgruppe

# Parameter Freigabe Raumtemperaturen
#T_min_Nacht = 21 # Minimaltemp für EG Nacht
T_max_Tag_OG = 21.5 # Maximaltemp OG für Sperrung WP
T_max_Tag_EG = 25 # Maximaltemp EG für Sperrung WP
T_min_Tag = 21.5 # Minimale Raumtemp EG zur Freigabe WP
T_Absenk = 21.5 # Minimale Raumtemp EG für Freigabe Absenkbetrieb
T_Tag_hyst = 0.3
#T_HK1_Nacht = 5 # Tempvorgabe für Absenkbetrieb nur mit Umwälzpumpe
#T_HK2_Nacht = 5 #Tempvorgabe für Absenkbetrieb nur mit Umwälzpumpe

#Parameter Freigabe vor Sonnenuntergang
AT_MIN = 0
AT_MAX = 14
T_FREIGABE_MIN = 7
T_FREIGABE_MAX = 10

#Parameter Freigabe Speicherladung
T_Speicher_Min = 25

#Parameter WW-Ladung
ww_start = datetime.time(12, 0)
ww_stop = datetime.time(15, 0)
ww_soll = 56 #55°C
ww_aus = 54 #Diese Temperatur muss erreicht werden damit WW-Betrieb beendet wird (VL-Temp WP) 52.5°C
ww_hyst = 1 #Hysterese für Freigabe WW-Betrieb  

#Parameter Steigung Heizkurve
steigung_min = 45
steigung_max = 200
p_sol_max = 2000
p_sol_min = 0

#Parameter Kühlen
rt_freigabe_kuehlen = 15.0
at_freigabe_kuehlen = 15.0

REGISTER = {
    "Komfort_HK1": 1501,
    "Eco_HK1": 1502,
    "Steigung_HK1": 1503,
    "Komfort_HK2": 1504,
    "Eco_HK2": 1505,
    "Steigung_HK2": 1506, 
    "Betriebsart": 1500,
    "WW_Eco": 1510,
    "RT_IST_OG": 583,
    "RT_SOLL_KK2": 1604
}

IP_ISG = "192.168.178.36"

CLIENT = ModbusTcpClient(IP_ISG)
CLIENT.connect()

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

    #######################################################################################################
    logging.info(f"---------- Prüfung Freigabe / Sperrung Heizgrenze ----------") 
    # Abfrage aktuelle Aussentemperatur
    t_now = get_vals(UUID["T_outdoor"])["data"]["tuples"][0][1]
    #t_now = 0
    
    # Abfragen 24h Aussentemperatur und ggf. Freigabe Heizgrenze
    t_roll_avg_24 = get_vals(UUID["T_outdoor"], duration="-1440min")["data"]["average"]
    #t_roll_avg_24 = 0

    #Abfragen aktueller Zustand Freigabe Normalbetrieb (Heizgrenze)
    akt_freigabe_normal = get_vals(UUID["Freigabe_normalbetrieb"], duration="-0min")["data"]["average"]

    b_freigabe_normal = 0
    if akt_freigabe_normal == True: 
        if t_roll_avg_24 < FREIGABE_NORMAL_TEMP_HYST:
            b_freigabe_normal = 1
        else:
            b_freigabe_normal = 0
    
    else:
        if t_roll_avg_24 < FREIGABE_NORMAL_TEMP:
            b_freigabe_normal = 1
        else:
            b_freigabe_normal = 0
    
    write_vals(UUID["Freigabe_normalbetrieb"], b_freigabe_normal)
    
    logging.info("Aktuelle Aussentemperatur: {}".format(t_now))
    logging.info("24h Aussentemperatur ({}°C) < Heizgrenze ({}°C): {}".format(t_roll_avg_24,FREIGABE_NORMAL_TEMP,b_freigabe_normal))

    #############################################################################################################
    logging.info(f"---------- Prüfung Freigabe / Sperrung Sonderbetrieb ----------") 
    b_freigabe_wp = 0
    #b_sperrung_wp = 0
    
    #Abfragen aktuelle Energiebilanz zur Prüfung Freigabe Sonderbetrieb
    power_balance = get_vals(UUID["PV_Produktion"], duration="-30min")["data"]["average"]
    p_net = power_balance 
    #logging.info("PV-Produktion Einschaltschwelle (15min): {}".format(p_net))
    
    # Aktuelle Einschaltschwelle Sonderbetrieb    
    p_freigabe_now = -(FREIGABE_WARM_P + (t_now - FREIGABE_WARM_TEMP) * 
        (FREIGABE_WARM_P - FREIGABE_KALT_P)/(FREIGABE_WARM_TEMP - FREIGABE_KALT_TEMP))
    logging.info("Freigabe_Leistung: {}".format(p_freigabe_now))
  
    #Abfragen aktuelle Freigabe auf Grund Solarüberschuss
    akt_freigabe_wp = get_vals(UUID["Freigabe_WP"], duration="-0min")["data"]["average"]

    if akt_freigabe_wp == 1:
        if p_net < 10:
            b_freigabe_wp = 0
        elif p_net > (p_freigabe_now - SPERRUNG_HYST): #Freigabe WP auf Grund von PV-Leistung
            b_freigabe_wp = 1
        else:
            b_freigabe_wp = 0
    else:
        if p_net > p_freigabe_now: #Freigabe WP auf Grund von PV-Leistung
            b_freigabe_wp = 1
        else:
            b_freigabe_wp = 0
    
    #if p_net2 < p_sperrung_now: #Sperrung WP auf Grund von PV-Leistung
    #    b_sperrung_wp = 1
    
    write_vals(UUID["Freigabe_WP"], b_freigabe_wp) # Aktiv wenn ausreichend PV Leistung vorhanden
    #write_vals(UUID["Sperrung_WP"], b_sperrung_wp) # Aktiv wenn zu wenig PV Leistung vorhanden
    logging.info("30 min PV-Leistung ({} W) > Einschaltschwelle ({} W): {}".format(p_net,p_freigabe_now,b_freigabe_wp))
    #logging.info("45 min PV-Leistung ({} W) < Ausschaltschwelle ({}) W: {}".format(p_net2,p_sperrung_now,b_sperrung_wp))    

    #################################################################################
    logging.info(f"---------- Prüfung Freigabe / Sperrung Raumtemperaturen ----------") 
    T_Freigabe_max = 0
    T_Freigabe_min = 0
    T_Freigabe_Absenk = 0
    T_Freigabe_Betr = 0
    
    #Abfragen aktuelle Raumtemperaturen EG & OG
    RT_akt_EG = get_vals(UUID["T_Raum_EG"], # Frage aktuelle Raumtemperatur ab. 
                      duration="-60min")["data"]["average"] 
    
    #RT_akt_OG = get_vals(UUID["T_Raum_OG"], # Frage aktuelle Raumtemperatur ab. 
    #                  duration="-60min")["data"]["average"] 
    
    logging.info("Aktuelle Raumtemp EG: {}".format(RT_akt_EG))
    #logging.info("Aktueller Raumtemp OG: {}".format(RT_akt_OG))
    
    # Definition Betriebsfreigaben
    akt_freigabe_verz_Tag = get_vals(UUID["t_Verzoegerung_Tag"], duration="-0min")["data"]["average"]
    akt_sperrung_Tag = get_vals(UUID["t_Sperrung_Tag"], duration="-0min")["data"]["average"]
    akt_abesenk = get_vals(UUID["T_Absenk_F"], duration="-0min")["data"]["average"]

    # Aktuelle Sperrung Absenkbetrien Temp zu hoch
    if akt_freigabe_verz_Tag == 1:  
        if RT_akt_EG > (T_min_Tag - T_Tag_hyst): #Sperrung WP wenn Raumtemp EG zu hoch
            T_Freigabe_min = 1  
        else:
            T_Freigabe_min = 0  
    else:
        if RT_akt_EG > (T_min_Tag + T_Tag_hyst): #Sperrung WP wenn Raumtemp EG zu hoch
            T_Freigabe_min = 1  
        else:
            T_Freigabe_min = 0  

    # Aktuelle Sperrung Sonderbetrieb wegen Temp zu hoch
    if akt_sperrung_Tag == 1:  
        if RT_akt_EG > (T_max_Tag_EG - T_Tag_hyst): #Sperrung WP wenn Raumtemp EG zu hoch
            T_Freigabe_max = 1
        else:
            T_Freigabe_max = 0
    else:
        if RT_akt_EG > (T_max_Tag_EG + T_Tag_hyst): #Freigabe WP Sperrung wenn Raumtemp max -0.5°C
            T_Freigabe_max = 1
        else:
            T_Freigabe_max = 0

    # Aktuelle Sperrung Absenkbetrieb
    #if T_Freigabe_min == 1:
    #    T_Freigabe_Absenk = 0
    #else:
    #    T_Freigabe_Absenk = 1

    write_vals(UUID["t_Verzoegerung_Tag"], T_Freigabe_min) # 1 wenn RT EG > 21°C 
    write_vals(UUID["t_Sperrung_Tag"], T_Freigabe_max) # 1 wenn RT OG > 22.5°C
    #write_vals(UUID["T_Absenk_F"], T_Freigabe_Absenk) # 1 wenn RT EG < 21°C
   
    logging.info("Raumtemp EG ({}°C) > Einschaltschwelle ({}°C): {}".format(RT_akt_EG,T_min_Tag,T_Freigabe_min))
    logging.info("Raumtemp EG ({}°C) > Ausschaltschwelle ({}°C) : {}".format(RT_akt_EG, T_max_Tag_EG, T_Freigabe_max))
    #logging.info("Raumtemp EG ({}°C) < Freigabe Absenkbetrieb ({}°C): {}".format(RT_akt_EG,T_Absenk,T_Freigabe_Absenk))

    ################################################################################
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

    #############################################################################
    logging.info(f"---------- Prüfung Speicherladung Pufferspeicher ----------") 
    Freigabe_T_Speicher = 0
    Freigabe_Komfortbetrieb = 0
    Freigabe_Puffertemp = 0

    T_speicher_aktuell = get_vals(UUID["Puffer_Temp_oben"], duration="-1min")["data"]["average"]
    betriebszustand = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)

    #if b_freigabe_normal & b_freigabe_wp & sunset_freigabe: #Prüfen ob Bedingungen für Komfortbetrieb erfüllt
    #    Freigabe_Komfortbetrieb = 1
    #else:
    #    Freigabe_Komfortbetrieb = 0

    #if betriebszustand == 1:
    #    if (T_speicher_aktuell < T_Speicher_Min): #Prüfen Speichertemperatur oben < 25°C
    #        Freigabe_T_Speicher = 1
    #    else:
    #        Freigabe_T_Speicher = 0
    #else:
    #  Freigabe_T_Speicher = 1

    #if Freigabe_Komfortbetrieb & Freigabe_T_Speicher:
    #    Freigabe_Puffertemp = 1
    #else:
    #    Freigabe_Puffertemp = 0
    
    #logging.info("Freigabe Komfortbetrieb: {}".format(Freigabe_Komfortbetrieb))
    #logging.info("Freigabe Puffertemperatur: {}".format(Freigabe_T_Speicher))
    #logging.info("Freigabe Gesamt: {}".format(Freigabe_Puffertemp))

    #####################################################################################
    logging.info(f"---------- Prüfung Freigabe / Sperrung Warmwasserbetrieb ----------") 
    ww_time = 0
    Ww_aus = 0
    Ww_ein = 0
    
    #Formatierung Freigabezeiten Warmwasser
    Ww_start = datetime.time(hour=int(ww_start.hour), minute=int((ww_start.hour - int(ww_start.hour))*60)) # Freigabezeit Warmwasser
    Ww_stop = datetime.time(hour=int(ww_stop.hour), minute=int((ww_stop.hour - int(ww_stop.hour))*60)) # Freigabezeit Warmwasser 
        
    ww_temp = get_vals(UUID["WW_Temp_mitte"], duration="-1min")["data"]["average"]
    betriebszustand = CLIENT.read_holding_registers(1500, count=1, unit= 1).getRegister(0)

    logging.info("Aktuelle WW-Speichertemp mitte: {}".format(ww_temp))

    if betriebszustand == 5:
        if ww_temp < ww_soll:
            Ww_ein = 1
        else:
            Ww_ein = 0
    else:
        if ww_temp < (ww_soll-ww_hyst):
            Ww_ein = 1
        else:
            Ww_ein = 0
       
    if now.time() > Ww_start and now.time() < Ww_stop:
        ww_time = 1

    write_vals(UUID["WW_Time"], ww_time) 
    write_vals(UUID["WW_Ein"], Ww_ein) 
    
    logging.info("Ist-Wert WW-Temp ({}°C) < Einschaltwert WW-Temp ({}°C): {}".format(ww_temp,ww_soll-ww_hyst,Ww_ein))
    #logging.info("Ist-Wert WW-Temp ({}°C) >= Ausschalt-Wert WW-Temp ({}°C): WW_Sperrung {}".format(ww_temp,ww_aus,Ww_aus))
    logging.info("Aktuelle Uhrzeit ({}) in Zeitfenster ({} - {} Uhr): {}".format(now.time(),ww_start,ww_stop,ww_time))

    ######################################################################
    logging.info(f"---------- Modifikation Heizkurve ----------")   
    steigung_soll = 45
    
    #Abfragen aktuelle Stromproduktion PV-Anlage
    power_sol = get_vals(UUID["PV_Produktion"], duration="-15min")["data"]["average"]
    
    p_sol = power_sol - p_freigabe_now

    if p_sol > 0:
        steigung_soll = int((steigung_max-steigung_min)/(p_sol_max-p_sol_min)*p_sol + steigung_min)

        if steigung_soll > 200:
            steigung_soll = 200
    else:
        steigung_soll = steigung_min

    CLIENT.write_register(REGISTER["Steigung_HK1"], steigung_soll)
    CLIENT.write_register(REGISTER["Steigung_HK2"], steigung_soll)
    write_vals(UUID["Steigung_HK"], steigung_soll) 

    logging.info("Überschussleistung: {}".format(p_sol))
    logging.info("Aktuelle Steigung Heizkurve: {}".format(steigung_soll))


    #######################################################################
    logging.info(f"----------------Kühlfunktion--------------------")
    
    T_Soll_Raum_OG = (CLIENT.read_input_registers(REGISTER["RT_IST_OG"], count=1, unit= 1).getRegister(0))/10
    #t1 = (CLIENT.read_input_registers(502, count=1, unit= 1).getRegister(0))/10
    #t2 = (CLIENT.read_input_registers(503, count=1, unit= 1).getRegister(0))/10
    #t3 = (CLIENT.read_input_registers(504, count=1, unit= 1).getRegister(0))/10
    #t4 = (CLIENT.read_input_registers(505, count=1, unit= 1).getRegister(0))/10
    #t45 = (CLIENT.read_input_registers(583, count=1, unit= 1).getRegister(0))/10
    #t5 = (CLIENT.read_input_registers(584, count=1, unit= 1).getRegister(0))/10
    #t6 = (CLIENT.read_input_registers(585, count=1, unit= 1).getRegister(0))/10
    #t7 = (CLIENT.read_input_registers(586, count=1, unit= 1).getRegister(0))/10
    t8 = (CLIENT.read_input_registers(603, count=1, unit= 1).getRegister(0))/10
    t9 = (CLIENT.read_input_registers(604, count=1, unit= 1).getRegister(0))/10

    t10 = (CLIENT.read_holding_registers(1605, count=1, unit= 1).getRegister(0))/10
    t11 = (CLIENT.read_holding_registers(1604, count=1, unit= 1).getRegister(0))/10
    t12 = (CLIENT.read_holding_registers(1514, count=2, unit= 1).getRegister(0))/10
    t13 = (CLIENT.read_holding_registers(1515, count=2, unit= 1).getRegister(0))/10
    t14 = (CLIENT.read_holding_registers(1513, count=2, unit= 1).getRegister(0))/10
    
    #print(t1)
    #print(t2)
    #print(t3)
    #print(t4)
    #print(t45)
    #print(t5)
    #print(t6)
    #print(t7)
    print(t8)
    print(t9)
    #print(t10)
    print(t11)
    print(t12)
    print(t13)
    print(t14)
    

    #if T_Soll_Raum_OG >= rt_freigabe_kuehlen and t_now >= at_freigabe_kuehlen:
    #    print("kuehlbetrieb freigegeben")

    CLIENT.write_register(REGISTER["RT_SOLL_KK2"], 201)
    
    #"RT_SOLL_OG": 1604

    #read holding registers
    #raumsoll hk2 1605 ==> kann geschrieben werden
    #raumsoll hk1 1604?  
    #Hysterese Kühlen 1514
    #Raumsolltemp 1515
    #Vorlaufsolltemp 1513

    #Read Input register
    #Isttemperatur FEK 502
    #Solltemp FEK 503
    # Raumfeuchte 504
    # Taupunkt 505
    # ISt Raumtemp Heizkreis 1. 583
    # RT Soll OG 584
    # Raumfeuchte 585
    #Taupunkt 586
    #Soll Raumtemp KK1 603 
    #Soll Raumtemp KK2 604
   
    

    
    #######################################################################
    logging.info(f"---------- Schreiben Betriebsfälle ----------")   
    
    # Freigabe Programmbetrieb für Erzeugung Warmwasser während Zeitfenster bis max. Vorlauftemperatur erreicht ist. 
         
    if ww_time and Ww_ein:
        logging.info(f"WW-Betrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(5))
        time.sleep(5)
        CLIENT.write_register(REGISTER["WW_Eco"], ww_soll*10) 

    #Freigabe Kühlbetrieb
    elif (T_Soll_Raum_OG >= rt_freigabe_kuehlen and t_now >= at_freigabe_kuehlen): #Freigabe Kühlbetrieb
        logging.info(f"Kühlbetrieb")
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Kühlbetrieb nicht aktiv.
    
    #Anlage in Bereitschaft schalten wenn Raumtemperatur EG über 21.2°C und nicht ausreichend PV Leistung vorhanden.
    elif (T_Freigabe_min and b_freigabe_wp == 0):
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
               
    #Freigabe Absenkbetrieb wenn Heizperiode aktiv und RT EG < 21°C
    elif (b_freigabe_normal & (T_Freigabe_min == 0)): #b_sperrung_wp
        logging.info(f" Absenkbetrieb") 
        CLIENT.write_register(REGISTER["Betriebsart"], int(2)) # Muss auf Programmbetrieb sein, sonst wird Silent-Mode in Nacht nicht aktiv.
        CLIENT.write_register(REGISTER["Eco_HK2"], int(HK2_min*10))   
        CLIENT.write_register(REGISTER["Eco_HK1"], int(HK1_min*10))
        CLIENT.write_register(REGISTER["WW_Eco"], 100)

    else:
        if betriebszustand == 5:
            CLIENT.write_register(REGISTER["Betriebsart"], int(1))
            CLIENT.write_register(REGISTER["WW_Eco"], 100)
            logging.info(f"Deaktivieren WW-Betrieb")    
        else:
            logging.info(f"Beibehalten aktuelle Betriebsart") 

    CLIENT.close()
        
    logging.info("********************************")
    
if __name__ == "__main__":
    main()
