import requests 
import json
import logging

UUID_P = "7f07bdc0-6525-11ee-97bc-bd186bf2b3bf"
IP_VENTI = "192.168.178.41"
URL_VZ = "192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"



def main():
    req = requests.get("http://" + IP_VENTI + "/report")
    data = req.content
    decoded_data = json.loads(data)
    print(decoded_data)
    print("Actual Power {}".format(decoded_data["power"]))
    print("Posting to VZ")
    poststring_p = URL_VZ.format(UUID_P, decoded_data["power"])
    postreq_p = requests.post(poststring_p)
    print(poststring_p)
    print(postreq_p.ok)



if __name__ == "__main__":
    main()
