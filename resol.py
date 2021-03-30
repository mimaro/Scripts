import requests
import json
import logging
import pprint

IP_RESOL = "192.168.178.61"
RESOL_URL = "http://{}/dlx/download/live?sessionAuthUsername=admin&sessionAuthPassword=admin".format(
    IP_RESOL)


RESOL_DATA = {
    "Sensor 1": 1,
    "Sensor 2": 2,
    "Sensor 3": 3,
    "Sensor 4": 4,
    "Sensor 5": 5
    #"PWM_A": 17,
    #"PWM_B": 16
}


UUID = {
    "Sensor 1": "8bf3cdf0-4a61-11e9-b9c2-8d5600e42614",
    "Sensor 2": "2f4ed570-4a62-11e9-843a-1d83a8f181f3",
    "Sensor 3": "9cfe4750-4a61-11e9-9ac9-6b9cc7f23517",
    "Sensor 4": "70d65570-4a61-11e9-b638-fb0f3e7a4677",
    "Sensor 5": "84d8d720-a657-11e9-8c76-3f13823c5e95",
    "PWM_A": "e2bc2ee0-52de-11e9-a86c-1d6437911028",
    "PWM_B": "f60ca430-4a61-11e9-8fa1-47cb405220bd"
}


URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"


def main():
    print(RESOL_URL)
    req = requests.get(RESOL_URL)
    data = req.content
    decoded_data = json.loads(data)
    for k, v in RESOL_DATA.items():
        d = decoded_data["headersets"][0]["packets"][0]["field_values"][v]["value"]
        print("{}: {}".format(k,d))
        poststring = URL_VZ.format(UUID[k], d)
        postreq = requests.post(poststring)
        print(postreq.ok)
    

if __name__ == "__main__":
    main()
