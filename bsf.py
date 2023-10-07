
# Dient nicht mehr als Messung bei BSF sondern als Raumtempfühler im 1. OG

import requests 
import json
import logging

#UUID_P = "ad5c809"
UUID_T = "78afd3c0-6523-11ee-980e-9fe998eb4bc6"
IP_VENTI = "192.168.178.37"
URL_VZ = "192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"

Offset = -2.1


def main():
    req = requests.get("http://" + IP_VENTI + "/report")
    data = req.content
    decoded_data = json.loads(data)
    print(decoded_data)
    print("Actual Power {}".format(decoded_data["power"]))
    print("Actual Temperature {}".format(decoded_data["temperature"]+ Offset))
    print("Posting to VZ")
    #poststring_p = URL_VZ.format(UUID_P, decoded_data["power"])
    poststring_t = URL_VZ.format(UUID_T, decoded_data["temperature"]+ Offset)
    #postreq_p = requests.post(poststring_p)
    postreq_t = requests.post(poststring_t)
    #print(poststring_p)
    print(poststring_t)
    #print(postreq_p.ok)
    print(postreq_t.ok)




if __name__ == "__main__":
    main()
