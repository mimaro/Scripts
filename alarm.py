import smtplib 
from email.message import EmailMessage
import ssl
import requests
import json
import pprint
import datetime
import logging
#import pytz

#######################################################################################################
# Format URLs
VZ_GET_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?from={}"

#######################################################################################################
# UUID's

UUID = {
  "T_Puffer": "88b7c280-1cab-11e9-938e-fb5dc04c61d4",
  "PV_Prod": "101ca060-50a3-11e9-a591-cf9db01e4ddd"
  
}

#######################################################################################################

def get_vals(uuid, duration="-0min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    #return(json.loads(req.content))
    return req.json()

WP_check = get_vals(UUID["T_Puffer"])["data"]["average"]
PV_check = get_vals(UUID["PV_Prod"])["data"]["average"]

print(WP_check)
print(PV_check)



# msg = EmailMessage()
# msg.set_content("Auf dem Volkszähler sind fehlende Daten vorhanden")
# msg["Subject"] = "Alarmierung Datenfehler VZ"
# msg["From"] = "m.roost@gmx.net"
# msg["To"] = "m.roost@gmx.net"

# context=ssl.create_default_context()

# with smtplib.SMTP("mail.gmx.net", port=587) as smtp:
#     smtp.starttls(context=context)
#     smtp.login(msg["From"], "TurionX2klm09LMFO")
#     smtp.send_message(msg)
