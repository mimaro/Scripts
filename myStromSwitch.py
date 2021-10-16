import requests 
import json
import logging

UUID_P = "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
UUID_T = "	84d8d720-a657-11e9-8c76-3f13823c5e95"
IP_VENTI = "192.168.178.30"
URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"


def main():
    req = requests.get("http://" + IP_VENTI + "/report")
    data = req.content
    decoded_data = json.loads(data)
    print("Actual Power {}".format(decoded_data["power"]))
    print("Actual Temperature {}".format(decoded_data["temperature"]))
    print("Posting to VZ")
    poststring_p = URL_VZ.format(UUID_P, decoded_data["power"])
    poststring_t = URL_VZ.format(UUID_T, decoded_data["temperature"])
    postreq_p = requests.post(poststring_p)
    postreq_t = requests.post(poststring_t)
    print(poststring_p)
    print(poststring_t)
    print(postreq_p.ok)
    print(postreq_t.ok)


if __name__ == "__main__":
    main()

    
    
