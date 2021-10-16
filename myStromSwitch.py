import requests 
import json
import logging

UUID_P = "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
IP_VENTI = "192.168.178.30"
URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"



def main():
    req = requests.get("http://" + IP_VENTI + "/report")
    data = req.content
    decoded_data = json.loads(data)
    print(decoded_data)
    print("Actual Power {}".format(decoded_data["power"])
    print("Posting to VZ")
    poststring_p = URL_VZ.format(UUID_P, decoded_data["power"])
    postreq_p = requests.post(poststring_p)
    print(poststring_p)
    print(postreq_p.ok)



if __name__ == "__main__":
    main()
