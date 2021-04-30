
import requests 
import json
import logging

UUID = "ad5c8090-3698-11ea-8ad7-7f796afef9a1"
IP_VENTI = "192.168.178.30"
URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"


def main():
    req = requests.get("http://" + IP_VENTI + "/report")
    data = req.content
    decoded_data = json.loads(data)
    print("Actual Power {}".format(decoded_data["power"]))
    print("Posting to VZ")
    poststring = URL_VZ.format(UUID, decoded_data["power"])
    postreq = requests.post(poststring)
    print(poststring)
    print(postreq.ok)





if __name__ == "__main__":
    main()
