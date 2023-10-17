import socket
import json
import time

class KebaController:
    def __init__(self):
        # Allgemeine Parameter
        self.portKEBA = 7090
        self.ipKEBA = "192.168.178.59"
        self.failsafeCurrent = 13000
        self.failsafeTimeout = 300

        # KEBA States Steuerung, die gewünschten Parameter
        self.controllerStrom = 0
        self.aenderungLadeLeistung = 0
        self.controllerStatus = 0
        self.controllerStatusString = [
            "Nicht eingesteckt", "Warten auf genügend PV- Überschuss",
            "Laden: Optimiert", "Laden: Definiert"
        ]
        self.minLadeStrom = 10000
        self.maxLadeStrom = 32000
        self.ladeOffSet = 0
        self.ueberschussSeit = 0
        self.ladenSeit = TimeWatch()
        self.eingestecktSeit = TimeWatch()

        # actual KEBA Values
        self.actualU1, self.actualU2, self.actualU3 = 0, 0, 0
        self.actualI1, self.actualI2, self.actualI3 = 0, 0, 0
        self.actualP = 0
        self.actualPF = 1000
        self.actualE = 0
        self.actualMaxCurr = 0
        self.actualMaxCurrHW = 0
        self.actualCurrUser = 0
        self.actualCurrFS = 0
        self.actualTmoFS = 0

        # KEBA States
        self.actualState, self.oldState = 0, 0
        self.actualPlug, self.oldPlug = 0, 0
        self.actualInput, self.oldInput = 0, 0
        self.actualStateString = [
            "KEBA ist am Starten", "KEBA ist nicht bereit (ena0, nicht eingesteckt...",
            "KEBA ist bereit zum laden und wartet auf EV charging request",
            "KEBA ist am laden", "KEBA hat einen Fehler (Siehe getError)",
            "KEBA hat die Autorisierung zurückgewiesen"
        ]
        self.actualPlugString = [
            "Kein Stecker eingesteckt", "Stecker eingesteckt an Wallbox",
            "unbekannter Stecker Status", "Stecker eingesteckt an Wallbox und verriegelt",
            "unbekannter Stecker Status", "Stecker eingesteckt an Wallbox und EV",
            "unbekannter Stecker Status", "Stecker eingesteckt an Wallbox und EV und verriegelt"
        ]
        self.enableSys = 0
        self.enableUser = 0

    def initKEBA(self):
        # UDP communication configuration
        self.us = UdpServer(self.portKEBA)
        self.us.addUdpServerListener(self.packetReceived)
        self.us.start()

    def ladeFunktion(self):
        # Handle charging process and state transitions here
        pass

    def aendereLadeStrom(self):
        # Adjust charging current based on aenderungLadeLeistung
        pass

    def sendCurrRequesttoKEBA(self, reqToKEBA):
        # Send current request to KEBA station
        pass

    def stateChanged(self):
        # Handle state change events
        pass

    def inputChanged(self):
        # Handle input change events
        pass

    def plugChanged(self):
        # Handle plug change events
        pass

    def evaluateDatafromKEBA(self, receivedFromKEBA):
        # Process data received from KEBA station
        pass

    def sendRequesttoKEBA(self, anfrage):
        # Send a request to KEBA station
        pass

    def setKEBAFailsafeTime(self, timeoutZeit, ladestromimFailsafe, speichern):
        # Set failsafe parameters on KEBA station
        pass

    def setKEBAoutputRelais(self, relaisstatus):
        # Set output relais status on KEBA station
        pass

    def getcontrollerCurrent(self):
        return self.controllerStrom

    def getactualState(self):
        return self.actualState

    def getactualPlug(self):
        return self.actualPlug

    def getActualU1(self):
        return self.actualU1

    def getActualU2(self):
        return self.actualU2

    def getActualU3(self):
        return self.actualU3

    def getActualI1(self):
        return self.actualI1

    def getActualI2(self):
        return self.actualI2

    def getActualI3(self):
        return self.actualI3

    def getActualP(self):
        return self.actualP / 1000

    def getActualPF(self):
        return self.actualPF / 10

    def getActualE(self):
        return self.actualE * 10

    def getActualMaxCurr(self):
        return self.actualMaxCurr

    def getActualMaxCurrHW(self):
        return self.actualMaxCurrHW

    def getActualCurrUser(self):
        return self.actualCurrUser

    def getActualCurrFS(self):
        return self.actualCurrFS

    def getEnableSys(self):
        return self.enableSys

    def getEnableUser(self):
        return self.enableUser

    def getInput(self):
        return self.actualInput

class TimeWatch:
    def __init__(self):
        self.start_time = time.time()
        self.enabled = True

    def reset(self):
        self.start_time = time.time()

    def elapsed_time(self):
        return time.time() - self.start_time

class UdpServer:
    def __init__(self, port):
        self.port = port
        self.listeners = []

    def addUdpServerListener(self, listener):
        self.listeners.append(listener)

    def start(self):
        # Start the UDP server
        pass

    def send(self, data, address):
        # Send data over UDP
        pass

    def packetReceived(self, evt):
        for listener in self.listeners:
            listener.packetReceived(evt)

class Services:
    def waitxmilis(self, millis):
        time.sleep(millis / 1000)

#class Volkszaehler:
#    def sendData(self, id, value):
#        # Send data to Volkszaehler
#        pass

keba = KebaController()
keba1 = keba.actualInput


print(keba1)


#if __name__ == "__main__":
#    controller = KebaController()
#    controller.initKEBA()
#    # Main control loop
#    while True:
#        controller.ladeFunktion()



#------------
#import time
#from datetime import datetime
#import requests

#class KebaController:
    # Your KebaController class definition here

#def readLastPowerValFrom(api_url):
#    try:
#        response = requests.get(api_url)
#        data = response.json()
#        return data['value']
#    except Exception as e:
#        print(e)
#        return 0

# Instantiate the KebaController class
#keba = KebaController()

# Define a loop that continues indefinitely
#while True:
 #   try:
 #       now = datetime.now()

 #       BilanzWagenrain8a = -float(readLastPowerValFrom("https://api.sel.energy/api_v1/balance/watt/53CB8E13-0E02-4880-B7F3-8C73C768F271/"))
 #       WP = float(readLastPowerValFrom("https://api.sel.energy/api_v1/consumption/watt/E2271BF8-D70B-43C6-BCFF-0B09130EC3F2/"))

  #      keba.sendRequesttoKEBA("report 1")
  #      keba.sendRequesttoKEBA("report 2")
  #      keba.sendRequesttoKEBA("report 3")

  #      Verfuegbar = BilanzWagenrain8a - 1000 + WP
  #      try:
  #          vz.sendData("f1af1840-6c1f-11e9-8589-e3b0e93baa55", str(Verfuegbar))
  #      except Exception as e1:
  #          print(e1)

   #     keba.setAenderungLadeLeistung(Verfuegbar)
   #     keba.ladeFunktion()

   #     time.sleep(60)

   # except Exception as e:
   #     print(e)
