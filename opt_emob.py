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

VZ_GET_URL = "https://example.tld/api/data/{}/{}"

def get_vals(uuid, duration="-0min"):
    # Daten von vz lesen.
    req = requests.get(VZ_GET_URL.format(uuid, duration), timeout=10)
    req.raise_for_status()
    return req.json()

UUID = "58163cf0-95ff-11f0-b79d-252564addda6"
MAX_MIN = 4320
STEP = 1

def payload_values(payload):
    """
    Extrahiert Werte robust aus möglichen JSON-Formaten:
    - Liste von Dicts: [{"timestamp": "...", "value": 3}, ...]
    - Dict mit 'value'
    - Dict mit 'data': [...]
    - Direkt-Liste von Werten
    """
    if isinstance(payload, list):
        for item in payload:
            if isinstance(item, dict):
                yield item.get("value", None)
            else:
                yield item
    elif isinstance(payload, dict):
        if "value" in payload:
            yield payload["value"]
        if "data" in payload and isinstance(payload["data"], list):
            for item in payload["data"]:
                if isinstance(item, dict):
                    yield item.get("value", None)
                else:
                    yield item
    else:
        # Unbekanntes Format -> nichts liefern
        if hasattr(payload, "get"):
            v = payload.get("value")  # defensiv
            if v is not None:
                yield v

def find_duration_for_state_3():
    # Gehe in 15-Min-Schritten von jetzt bis 4320 Min zurück
    for minutes in range(0, MAX_MIN + 1, STEP):
        duration = f"-{minutes}min"
        try:
            data = get_vals(UUID["Cable_State"], duration)["data"]
            print(data)
        except Exception:
            # Bei transienten Fehlern einfach nächsten Schritt versuchen
            continue

        # Prüfen, ob irgendwo in den zuletzt 'minutes' Minuten ein Wert 3 vorkam
        if any(v == 1 for v in payload_values(data)):
            return minutes

    # Kein Status 3 innerhalb von 72h gefunden
    return MAX_MIN

if __name__ == "__main__":
    value = find_duration_for_state_3()
    # Als reinen Minuten-Wert ausgeben
    print(value)
