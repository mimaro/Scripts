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
    "Freigabe_EMob": "756356f0-9396-11f0-a24e-add622cac6cb",
    "Cable_State": "58163cf0-95ff-11f0-b79d-252564addda6"
    
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

def last_state_3_minutes():
    UUID = "58163cf0-95ff-11f0-b79d-252564addda6"
    # 72 Stunden = 4320 Minuten
    MAX_MINUTES = 4320  

    # Daten abrufen
    data = get_data(UUID, "-4320min")

    # Aktuelle Zeit (UTC)
    now = datetime.now(timezone.utc)

    # Annahme: Datenstruktur z.B. [{"timestamp": "2025-09-20T12:34:56Z", "value": 3}, ...]
    # Falls deine API ein anderes Format liefert, musst du Key-Namen anpassen
    last_3_time = None
    for entry in data:
        value = entry.get("value")
        if value == 3:
            # ISO8601-String in UTC-Datetime umwandeln
            ts = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
            if (last_3_time is None) or (ts > last_3_time):
                last_3_time = ts

    if last_3_time is None:
        # Kein Status 3 in den letzten 72h
        return MAX_MINUTES
    else:
        diff_minutes = int((now - last_3_time).total_seconds() // 60)
        # Begrenzen auf max. 4320 min
        return min(diff_minutes, MAX_MINUTES)

if __name__ == "__main__":
    minutes_since_last_3 = last_state_3_minutes()
    print(minutes_since_last_3)
