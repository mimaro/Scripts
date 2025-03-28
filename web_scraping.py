import requests
from bs4 import BeautifulSoup



#######################################################################################################
# Format URLs
VZ_GET_URL = "http://192.168.178.49/middleware.php/data/{}.json?from={}"
VZ_POST_URL = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

# UUID Gruppe: 77194160-7b62-11ec-8dce-47993bd55908
# Lokale IP-Adresse der Wärmepumpe (bitte anpassen)
url = "http://192.168.178.36/?s=1,1"  

#######################################################################################################


# Beispielhafte UUID-Zuordnung (bitte anpassen!)
UUID = {
    "VERDAMPFERTEMPERATUR": "dd35c760-0bef-11f0-885e-8dc19dbf1d54",
    "VERDICHTEREINTRITTSTEMPERATUR": "90098280-0bf1-11f0-af91-9f616d5bd7d8",
    "ÖLSUMPFTEMPERATUR": "a2174850-0bf1-11f0-9be6-c1126abb310a",
    
}

#"LÜFTERLEISTUNG REL": "uuid-4",
#    "ISTDREHZAHL VERDICHTER": "uuid-5",
#    "SOLLDREHZAHL VERDICHTER": "uuid-6",

# Hier definierst du deine eigene Logik, wie Werte gesendet werden (z. B. über MQTT, HTTP, etc.)
def write_vals(uuid, value):
    print(f"Sende Wert {value} an UUID {uuid}")
    # Hier echte Sende-Funktion einbauen (z. B. requests.post(), mqtt.publish(), etc.)

# Lokale IP-Adresse des Geräts
url = "http://192.168.1.100"  # <== bitte anpassen

# Schlüsselwörter und ihre Einheiten
werte_schluessel = {
    "VERDAMPFERTEMPERATUR": "°C",
    "VERDICHTEREINTRITTSTEMPERATUR": "°C",
    "ÖLSUMPFTEMPERATUR": "°C",
 
}


#   "LÜFTERLEISTUNG REL": "%",
#    "ISTDREHZAHL VERDICHTER": "Hz",
#    "SOLLDREHZAHL VERDICHTER": "Hz",

# Ergebnisse zwischenspeichern
ergebnisse = {}

try:
    # HTML laden
    response = requests.get(url, timeout=5)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    rows = soup.find_all("tr")

    # Werte extrahieren
    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 2:
            key = cells[0].text.strip()
            value_text = cells[1].text.strip()

            for suchbegriff, einheit in werte_schluessel.items():
                if suchbegriff in key:
                    clean_value = value_text.replace(einheit, "").replace(",", ".").strip()
                    try:
                        ergebnisse[suchbegriff] = float(clean_value)
                    except ValueError:
                        ergebnisse[suchbegriff] = None

    # Werte an UUIDs senden
    for name, value in ergebnisse.items():
        uuid = UUID.get(name)
        if uuid and value is not None:
            write_vals(uuid, value)
        else:
            print(f"Kein Wert oder keine UUID für {name}")

except requests.exceptions.RequestException as e:
    print("Fehler beim Zugriff auf das Gerät:", e)
