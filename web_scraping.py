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
# Configuration
UUID = {
    "T_Verdampfer": "dd35c760-0bef-11f0-885e-8dc19dbf1d54"
  
    }

def write_vals(uuid, val):
    # Daten auf vz schreiben.
    poststring = VZ_POST_URL.format(uuid, val)
    #logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)

# https://www.youtube.com/watch?v=cVnYod9Fhko

def main():




    try:
        # Weboberfläche abrufen
        response = requests.get(url, timeout=5)
        response.raise_for_status()  # wirft Fehler bei schlechtem Statuscode

        # HTML parsen
        soup = BeautifulSoup(response.text, "html.parser")

        # Nach dem Wert der Verdampfertemperatur suchen
        rows = soup.find_all("tr")
        verdampfertemperatur = None

        for row in rows:
            cells = row.find_all("td")
            if len(cells) == 2 and "VERDAMPFERTEMPERATUR" in cells[0].text:
                value_text = cells[1].text.strip().replace("°C", "").replace(",", ".")
                t_verdampfer = float(value_text)
                break

        # Ergebnis ausgeben
        if t_verdampfer is not None:
            print("Verdampfertemperatur:", t_verdampfer, "°C")
        else:
            print("Verdampfertemperatur nicht gefunden.")

    except requests.exceptions.RequestException as e:
        print("Fehler beim Zugriff auf das Gerät:", e)
   


    write_vals(UUID["T_Verdampfer"], t_verdampfer)


   
    print("well done")


if __name__=="__main__":
        main()
  
