import requests 
import json
import logging

UUID_P = "d92bc9e0-80c5-11ef-8443-b5ad123097e5"
IP_VENTI = "192.168.178.41"
URL_VZ = "http://192.168.178.49/middleware.php/data/{}.json?operation=add&value={}"



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
