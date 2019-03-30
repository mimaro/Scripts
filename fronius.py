import requests 
import json
import logging


UUID = "ef68a4b0-52e0-11e9-8a53-abf37aed52f5"
URL_VZ = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"

IP_FRONIUS = "192.168.178.20"
REQ = "http://{}/solar_api/v1/GetInverterRealtimeData.cgi?Scope=Device&DeviceId=1&DataCollection=CommonInverterData".format(IP_FRONIUS)


def main():
    print(REQ)
    req = requests.get(REQ)
    data = json.loads(req.content)
    udc, idc = data["Body"]["Data"]["UDC"]["Value"], data["Body"]["Data"]["IDC"]["Value"] 
    pdc = udc * idc
    poststring = URL_VZ.format(UUID, pdc)
    postreq = requests.post(poststring)
    print(poststring)
    print(postreq.ok)




if __name__ == "__main__":
    main()