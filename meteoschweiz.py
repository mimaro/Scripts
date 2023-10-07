import requests
import csv

UUID_BUS_GS = "159392d0-6521-11ee-9c72-dd2421c1d835"

GS = "gre000z0"
WS = "fu3010z0"

URL_VZ = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

CSV_URL = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/VQHA80.csv"

def main():
    BUS = {}
    req=requests.get(CSV_URL)
    data = req.content.split("\n")[:]
    reader = csv.DictReader(data, delimiter = ';')
    for row in reader:
        if row['Station/Location'] == "BUS":
            BUS=row

    requests.post(URL_VZ.format(UUID_BUS_GS, BUS[GS]))
   

if __name__ == "__main__":
    main()

