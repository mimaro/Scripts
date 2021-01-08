import requests
import csv


UUID_BUS_GS = "bcc12cb0-6290-11e9-acca-29f0ac50e804"
UUID_MOA_GS = "4f769670-52e4-11e9-840c-29fd59f140bc"

UUID_BUS_WS = "cf251900-6290-11e9-b8c7-c1df28b9badb"
UUID_MOA_WS = "ca315260-6290-11e9-86e7-519ba48bed8f"

GS = "gre000z0"
WS = "fu3010z0"

URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"

CSV_URL = "https://data.geo.admin.ch/ch.meteoschweiz.messwerte-aktuell/VQHA80.csv"


def main():
    BUS, MOA = {}, {}
    req=requests.get(CSV_URL)
    data = req.content.split("\n")[2:]
    reader = csv.DictReader(data, delimiter = ';')
    for row in reader:
        if row[''] == "BUS":
            BUS=row
        elif row[''] == "MOA":
            MOA=row
    requests.post(URL_VZ.format(UUID_BUS_GS, BUS[GS]))
    requests.post(URL_VZ.format(UUID_MOA_GS, MOA[GS]))
    requests.post(URL_VZ.format(UUID_BUS_WS, BUS[WS]))
    requests.post(URL_VZ.format(UUID_MOA_WS, MOA[WS]))

if __name__ == "__main__":
    main()

