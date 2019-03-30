import requests 
import json
import logging

UUID = "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
IP_RESOL = "192.168.178.202"
RESOL_URL = "http://{}/dlx/download/live?sessionAuthUsername=admin&sessionAuthPassword=roost".format(IP_RESOL)

URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"


def main():
    print(RESOL_URL)
    req = requests.get(RESOL_URL)
    print(req.content)
    data = req.content
    decoded_data = json.loads(data)
    #print("Actual Power {}".format(decoded_data["power"]))
    #print("Posting to VZ")
    #poststring = URL_VZ.format(UUID, decoded_data["power"])
    #postreq = requests.post(poststring)
    print(decoded_data)
    print(postreq.ok)





if __name__ == "__main__":
    main()
    