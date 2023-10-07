import requests
import json
import logging
import pprint

IP_RESOL = "192.168.178.22"
RESOL_URL = "http://{}/dlx/download/live?sessionAuthUsername=admin&sessionAuthPassword=admin".format(
    IP_RESOL)


RESOL_DATA = {
    "Sensor 1": 1,
    "Sensor 2": 2,
    "Sensor 3": 3
    #"Sensor 4": 4,
    #"Sensor 5": 5
    #"PWM_A": 17,
    #"PWM_B": 16
}


UUID = {
    "Sensor 1": "5ffdcda0-6525-11ee-a47b-ab0862f52c7a",
    "Sensor 2": "6856a280-6525-11ee-bfdf-b1cfbbd0a9c1",
    "Sensor 3": "7135fcc0-6525-11ee-a009-f733eeddb1d9",
    "Sensor 4": "70d65570-4a61-11e9-b638",
    "Sensor 5": "84d8d720-a657-11e9-8c7",
    "PWM_A": "e2bc2ee0-52de-11e9-a86",
    "PWM_B": "f60ca430-4a61-11e9-8f"
}


URL_VZ = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"


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
