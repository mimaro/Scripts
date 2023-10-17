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
        #global actualPlug, actualState, controllerStatus, controllerStrom, minLadeStrom, actualInput

        # Debug print statements (you can uncomment these if needed)
        # print("State KEBA: " + actualStateString[actualState])
        # print("State Steuerung: " + controllerStatusString[controllerStatus])

        # Handle charging based on actualPlug
        if actualPlug == 0:
            pass  # Kein Stecker eingesteckt
        elif actualPlug == 1:
            pass  # Stecker eingesteckt an Wallbox
        elif actualPlug == 3:
            pass  # Stecker eingesteckt an Wallbox und verriegelt, Standard, wenn kein EV eingesteckt ist.
        elif actualPlug == 5:
           pass  # Stecker eingesteckt an Wallbox und EV
        elif actualPlug == 7:
            # Stecker eingesteckt an Wallbox und EV und verriegelt
            if controllerStatus == 0:  # EV nicht verbunden
                pass
            elif controllerStatus == 1:  # Warten auf genügend PV- Überschuss
                controllerStatus = 2  # Der Controller wechselt in den Status "optimierte Ladung"
                sendRequesttoKEBA("ena 1")
            elif controllerStatus == 2:  # Laden optimiert
                aendereLadeStrom()
                if actualInput == 1:  # maximalladung
                    minLadeStrom = 32000
                sendCurrRequesttoKEBA(controllerStrom)
            elif controllerStatus == 3:  # Laden definiert
                aendereLadeStrom()
                minLadeStrom = 16000
                sendCurrRequesttoKEBA(controllerStrom)
            elif controllerStatus == 4:  # Laden optimiert 1-phasig
                pass

        # Handle charging based on actualState
        if actualState == 0:  # KEBA ist am starten
            pass
        elif actualState == 1:  # KEBA ist nicht bereit
            controllerStrom = minLadeStrom + 3000
        elif actualState == 2:  # KEBA ist bereit zum laden und wartet auf EV charging request
            controllerStrom = minLadeStrom + 3000
        elif actualState == 3:  # KEBA ist am laden
            pass
        elif actualState == 4:  # KEBA hat einen Fehler
            pass  # Siehe getError
        elif actualState == 5:  # KEBA hat die Autorisierung zurückgewiesen
            pass


    def aendereLadeStrom(self):
        #global aenderungLadeLeistung, ladeOffSet, controllerStrom

        if aenderungLadeLeistung > 0:  # Positive Ladestromänderung
            aenderungLadestrom = ((aenderungLadeLeistung - ladeOffSet) * 1000 / 230) // 5
            controllerStrom += aenderungLadestrom
        else:  # Negative Ladestromänderung
            aenderungLadestrom = ((aenderungLadeLeistung - ladeOffSet) * 1000 / 230) // 2
            controllerStrom += aenderungLadestrom

    def sendCurrRequesttoKEBA(reqToKEBA):
        global controllerStrom, minLadeStrom, maxLadeStrom

        # TODO: Define an absolute minimum for the Ladestrom
        if reqToKEBA < minLadeStrom:  # The desired charging current is too low
            controllerStrom = minLadeStrom
            try:
                vz.sendData("e32099e0-6c1f-11e9-adfe-b7877ec8d38d", str(controllerStrom))
            except Exception as e:
                # Handle the exception here
                print("Error:", e)
            sendRequesttoKEBA("curr " + str(minLadeStrom))

        elif reqToKEBA > maxLadeStrom:  # The desired charging current is too high
            controllerStrom = maxLadeStrom
            try:
                vz.sendData("e32099e0-6c1f-11e9-adfe-b7877ec8d38d", str(controllerStrom))
            except Exception as e:
                # Handle the exception here
                print("Error:", e)
            sendRequesttoKEBA("curr " + str(maxLadeStrom))

        else:
            try:
                vz.sendData("e32099e0-6c1f-11e9-adfe-b7877ec8d38d", str(controllerStrom))
            except Exception as e:
                # Handle the exception here
                print("Error:", e)
            sendRequesttoKEBA("curr " + str(reqToKEBA))


    def stateChanged(self):
        global actualState, ladenSeit

        if actualState == 0:  # KEBA is starting
            ladenSeit.setEnabled(False)
        elif actualState == 1:  # KEBA is not ready (not plugged in, x1 or "ena" not set, RFID not enabled...)
            ladenSeit.setEnabled(False)
        elif actualState == 2:  # KEBA is ready for charging and waiting for EV charging request
            ladenSeit.setEnabled(False)
        elif actualState == 3:  # KEBA is charging
            ladenSeit.reset()
            # TODO: Start the "Laden seit" timer here
        elif actualState == 4:  # KEBA has an error (See getError)
            pass  # Handle the error here
        elif actualState == 5:  # KEBA has rejected authorization
            pass  # Handle the rejection here
        else:
            pass  # Handle other cases here


    def inputChanged(self):
        global actualInput

        if actualInput == 0:
            sendRequesttoKEBA("ena 1")
            try:
                vz.sendData("440ea890-6741-11e9-83d4-69e4af40dfb6", "0")
            except IOError as e:
                # Handle the IO error here
                pass  # You can replace this with appropriate error handling

        elif actualInput == 1:
            sendRequesttoKEBA("ena 1")
            try:
                vz.sendData("440ea890-6741-11e9-83d4-69e4af40dfb6", "100")
            except IOError as e:
                # Handle the IO error here
                pass  # You can replace this with appropriate error handling


    def plugChanged(self):
        global actualPlug, controllerStatus

        if actualPlug == 0 or actualPlug == 1 or actualPlug == 3 or actualPlug == 5:
            controllerStatus = 0
            sendRequesttoKEBA("ena 1")

        elif actualPlug == 7:
            sendRequesttoKEBA("ena 1")
            sendCurrRequesttoKEBA(10000)
            controllerStatus = 2
            minLadeStrom = 10000


    import json

    def evaluateDatafromKEBA(receivedFromKEBA):
        global actualState, actualInput, oldInput, actualPlug, enableSys, enableUser, actualTmoFS, actualMaxCurr, actualMaxCurrHW, actualCurrUser, actualCurrFS
        global actualU1, actualU2, actualU3, actualI1, actualI2, actualI3, actualP, actualPF, actualE

        if receivedFromKEBA == "TCH-OK :done\n":
            # Empfang wurde bestätigt
            # TODO Empfangsbestätigung verarbeiten, ggfl. catch wenn zu lange keine TCH-OK kam.
            # print(receivedFromKEBA)
            pass
        else:
            try:
                objrecfrmKEBA = json.loads(receivedFromKEBA)
                if "ID" in objrecfrmKEBA:
                    # Das empfangene ist eine Antwort auf eine Report Anfrage
                    if objrecfrmKEBA["ID"] == "1":
                        # Das empfangene Objekt ist eine Antwort auf eine Report 1 Anfrage
                        pass
                    elif objrecfrmKEBA["ID"] == "2":
                        # Das empfangene Objekt ist eine Antwort auf eine Report 2 Anfrage
                        actualState = objrecfrmKEBA["State"]
                        actualInput = objrecfrmKEBA["Input"]
                        oldInput = actualInput
                        if oldInput != actualInput:
                            inputChanged()
                        actualPlug = objrecrecfrmKEBA["Plug"]
                        enableSys = objrecfrmKEBA["Enable sys"]
                        enableUser = objrecfrmKEBA["Enable user"]
                        actualTmoFS = objrecfrmKEBA["Tmo FS"]
                        actualMaxCurr = objrecfrmKEBA["Max curr"]
                        actualMaxCurrHW = objrecfrmKEBA["Curr HW"]
                        actualCurrUser = objrecfrmKEBA["Curr user"]
                        actualCurrFS = objrecfrmKEBA["Curr FS"]
                    elif objrecfrmKEBA["ID"] == "3":
                        # Das empfangene Objekt ist eine Antwort auf eine Report 3 Anfrage
                        actualU1 = objrecfrmKEBA["U1"]
                        actualU2 = objrecfrmKEBA["U2"]
                        actualU3 = objrecfrmKEBA["U3"]
                        actualI1 = objrecfrmKEBA["I1"]
                        actualI2 = objrecfrmKEBA["I2"]
                        actualI3 = objrecfrmKEBA["I3"]
                        actualP = objrecfrmKEBA["P"]
                        actualPF = objrecfrmKEBA["PF"]
                        actualE = objrecfrmKEBA["E pres"] * 10
                elif "State" in objrecfrmKEBA:
                    # Das empfangene Objekt ist ein "State"- Broadcast
                    oldState = actualState
                    actualState = objrecfrmKEBA["State"]
                    stateChanged()
                elif "Plug" in objrecfrmKEBA:
                    # Das empfangene Objekt ist ein "Plug"- Broadcast
                    oldPlug = actualPlug
                    actualPlug = objrecfrmKEBA["Plug"]
                    plugChanged()
                elif "Input" in objrecfrmKEBA:
                    # TODO Input bearbeiten
                    # Das empfangene Objekt ist ein "Input"- Broadcast
                    oldInput = actualInput
                    actualInput = objrecfrmKEBA["Input"]
                    inputChanged()
                elif "Enable sys" in objrecfrmKEBA:
                    # Das empfangene Objekt ist ein "Enable sys"- Broadcast
                    enableSys = objrecfrmKEBA["Enable sys"]
                elif "Max curr" in objrecfrmKEBA:
                    # Das empfangene Objekt ist ein "Max curr"- Broadcast
                    actualMaxCurr = objrecfrmKEBA["Max curr"]
                elif "E pres" in objrecfrmKEBA:
                    # Das empfangene Objekt ist ein "E pres"- Broadcast
                    actualE = objrecfrmKEBA["E pres"]
                else:
                    # Das empfangene Objekt hat eine andere ID
                    pass
            except Exception as e:
                print(e)


    import socket

    def sendRequesttoKEBA(anfrage):
        # Daten Senden
        service.waitxmilis(100)
        send_data = anfrage.encode('utf-8')  # Converts a string to bytes using UTF-8 encoding
        host_address = ipKEBA  # Use the IP address or hostname here
        port = portKEBA

        try:
            host_address = socket.gethostbyname(ipKEBA)  # Resolve the hostname to an IP address
        except socket.error as e:
            host_address = None
            print(e)

        send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        send_packet = (send_data, (host_address, port))
        try:
            send_socket.sendto(*send_packet)
        except socket.error as e:
            print(e)
        finally:
            send_socket.close()


    def setKEBAFailsafeTime(timeoutZeit, ladestromimFailsafe, speichern):
        sendRequesttoKEBA(f"failsafe {timeoutZeit} {ladestromimFailsafe} {speichern}")


    def setKEBAoutputRelais(relaisstatus):
        sendRequesttoKEBA(f"output {relaisstatus}")


    def getcontrollerCurrent(self):
        return self.controllerStrom

    def get_actual_state(self):
        """
        Returns the current state of the KEBA.

        Returns:
        0: KEBA is starting
        1: KEBA is not ready (not plugged in, x1 or "ena" not set, RFID not enabled...)
        2: KEBA is ready to charge and waiting for an EV charging request
        3: KEBA is charging
        4: KEBA has an error (See get_error)
        5: KEBA has rejected the authorization
        """
        return self.actual_state  # Assuming actual_state is a variable defined elsewhere

       
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


    def set_aenderung_lade_leistung(self, aenderung_lade_leistung):
        self.aenderung_lade_leistung = round(aenderung_lade_leistung)



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
keba.initKEBA():

keba1 = keba.sendRequesttoKEBA("report 1")

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
