
import requests
import json
import pprint
import datetime
import logging

#######################################################################################################
# Format URLs

VZ_POST_URL = "http://vz.wiuhelmtell.ch/middleware.php/data/{}.json?operation=add&value={}"
########################################################################################################

#######################################################################################################
# Configuration
#UUID = {
 #   "COP_o_venti": "312ec8e0-52e7-11e9-ac6d-4f4dd87fd97b",
  #  "COP_m_venti": "3a89b8a0-52e7-11e9-b184-73ec439c39c9",
  #  "WP_th": "9399ca80-910c-11e9-ac0f-31ff5bbdf885",
  #  "WP_el": "92096720-35ae-11e9-a74c-534de753ada9",
  #  "Venti": "8cbbcb70-3c0d-11e9-87f9-9db68697df1d"
#}

###########################################################################################################

def get_vals(uuid, duration="-0min"):
    req = requests.get(VZ_GET_URL.format(uuid, duration))
    #return(json.loads(req.content))
    return req.json()

def write_vals(uuid, val):
    poststring = VZ_POST_URL.format(uuid, val)
    logging.info("Poststring {}".format(poststring))
    postreq = requests.post(poststring)
    logging.info("Ok? {}".format(postreq.ok))
 
    
def main():
    logging.info("********************************")
    logging.info("COP")
    wp_therm = get_vals(UUID["WP_th"])["data"]["tuples"][0][1]
    wp_el = get_vals(UUID["WP_el"])["data"]["tuples"][0][1]
    venti = get_vals(UUID["Venti"])["data"]["tuples"][0][1]
    cop_o_venti = wp_therm / wp_el
    cop_m_venti = wp_therm / (wp_el + venti)
    write_vals(UUID["COP_o_venti"], cop_o_venti)
    write_vals(UUID["COP_m_venti"], cop_m_venti)
   
if __name__ == "__main__":
main()






----------------------------

sensor = '/sys/bus/w1/devices/28-02161f5a48ee/w1_slave'
 
def readTempSensor(sensorName) :
    """Aus dem Systembus lese ich die Temperatur der DS18B20 aus."""
    f = open(sensorName, 'r')
    lines = f.readlines()
    f.close()
    return lines
 
def readTempLines(sensorName) :
    lines = readTempSensor(sensorName)
    # Solange nicht die Daten gelesen werden konnten, bin ich hier in einer Endlosschleife
    while lines[0].strip()[-3:] != 'YES':
        time.sleep(0.2)
        lines = readTempSensor(sensorName)
    temperaturStr = lines[1].find('t=')
    # Ich überprüfe ob die Temperatur gefunden wurde.
    if temperaturStr != -1 :
        tempData = lines[1][temperaturStr+2:]
        tempCelsius = float(tempData) / 1000.0
        tempKelvin = 273 + float(tempData) / 1000
        tempFahrenheit = float(tempData) / 1000 * 9.0 / 5.0 + 32.0
        # Rückgabe als Array - [0] tempCelsius => Celsius...
        return [tempCelsius, tempKelvin, tempFahrenheit]
 
try:
    while True :
        # Mit einem Timestamp versehe ich meine Messung und lasse mir diese in der Console ausgeben.
        print("Temperatur um " + time.strftime('%H:%M:%S') +" drinnen: " + str(readTempLines(sensor)[0]) + " °C")
        # Nach 10 Sekunden erfolgt die nächste Messung
        time.sleep(10)
except KeyboardInterrupt:
    # Programm wird beendet wenn CTRL+C gedrückt wird.
    print('Temperaturmessung wird beendet')
except Exception as e:
    print(str(e))
    sys.exit(1)
finally:
    # Das Programm wird hier beendet, sodass kein Fehler in die Console geschrieben wird.
    print('Programm wird beendet.')
    sys.exit(0)


