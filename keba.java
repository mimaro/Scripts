package controllers;

import java.io.IOException;
import java.net.DatagramPacket;
import java.net.InetAddress;
import java.net.SocketException;
import java.net.UnknownHostException;


import org.json.JSONObject;

import api.Volkszaehler;
import sv.UdpServer;
import sv.Services;
import sv.TimeWatch;

/**
 * @author pascalamiet
 *
 */
public class KebaController {
	
	Services service = new Services();
	Volkszaehler vz = new Volkszaehler();
	
	
	// Allgemeine Parameter
	private int portKEBA;
	private String ipKEBA;
	private Integer failsafeCurrent;			
	private Integer failsafeTimeout;

	UdpServer us = new UdpServer();

	// KEBA States Steuerung, die gewünschten Parameter
	private Integer controllerStrom = 0;
	private Integer aenderungLadeLeistung = 0;	//Wird vom SmartHome gesteuert. Definiert, wieviel die Ladeleistung hoch- oder runtergehen soll
	private Integer controllerStatus = 0;
	private String [] controllerStatusString = {"Nicht eingesteckt", "Warten auf genügend PV- Überschuss", "Laden: Optimiert", "Laden: Definiert"};
	private Integer minLadeStrom;
	private Integer maxLadeStrom;
	private Integer ladeOffSet;
	private Integer ueberschussSeit = 0;
	private TimeWatch ladenSeit = new TimeWatch();
	private TimeWatch eingestecktSeit = new TimeWatch();
	
	// actual KEBA Values
	private Integer actualU1, actualU2, actualU3;	//aktuelle Spannung in V
	private Integer actualI1, actualI2, actualI3; //aktueller Strom in mA
	private Integer actualP = 0;			// aktuelle Wirkleistung in mW
	private Integer actualPF = 1000;			// aktueller PowerFactor
	private Integer actualE; 			//Energie der aktuellen Ladung (E pres) in Wh
	private int actualMaxCurr;			// Current preset value via Control pilot in milliampere.
	private int actualMaxCurrHW;		// Highest possible charging current of the charging connection. Contains device maximum, DIP-switch setting, cable coding and temperature reduction.
	private int actualCurrUser;			// Current preset value of the user via UDP; Default = 63000mA.
	private int actualCurrFS;			// Current preset value for the Failsafe function.
	private int actualTmoFS;			// Communication timeout before triggering the Failsafe function.
	
	
	//KEBA States
	private Integer actualState=0, oldState;		// AktuellerStatus der Ladestation
	private Integer actualPlug=0, oldPlug;		// AktuellerStatus des Steckers
	private Integer actualInput= 0, oldInput;
	private String [] actualStateString = {"KEBA ist am Starten", "KEBA ist nicht bereit (ena0, nicht eingesteckt...", "KEBA ist bereit zum laden und wartet auf EV charging request","KEBA ist am laden","KEBA hat einen Fehler (Siehe getError)","KEBA hat die Autorisierung zurückgewiesen"};
	private String [] actualPlugString = {"Kein Stecker eingesteckt","Stecker eingesteckt an Wallbox","unbekannter Stecker Status","Stecker eingesteckt an Wallbox und verriegelt","unbekannter Stecker Status","Stecker eingesteckt an Wallbox und EV","unbekannter Stecker Status","Stecker eingesteckt an Wallbox und EV und verriegelt"};
	

	
	private int enableSys;
	private int enableUser;
	
	/**
	 * Initialisiert eine neue KEBA ohne Parameter
	 */
	public KebaController(){

		initKEBA();				
		

	}
	
	
	/**
	 * Initialisiert die Kommunikation mit der KEBA Ladestation
	 * @throws InterruptedException 
	 * @throws UnknownHostException
	 * @throws SocketException
	 */
	private void initKEBA(){
		
		//Allgemeine Einstellungen
		portKEBA = 7090;
		ipKEBA = "192.168.178.59";
		
		minLadeStrom = 10000;
		maxLadeStrom = 32000;
		
		failsafeCurrent = 13000;			// Wurde während der Failsafe Zeit kein Wert ena oder curr gesendet, wird die Ladestation diesen Wert zum Laden verwenden
		failsafeTimeout = 300;				// Failsafe-Zeit in Sekunden
		
		ladeOffSet = 0;					// Ladeoffset: Diese Leistung wird in der optimierten Ladung abgezogen.

		
		// UDP- Kommunikation konfigurieren
        us.setPort(portKEBA);                                         // Set the port
        us.addUdpServerListener(new UdpServer.Listener() {         // Add listener
            @Override
            public void packetReceived(UdpServer.Event evt ) {     // Packet received
            	evaluateDatafromKEBA(evt.getPacketAsString());
            } 
        });
        us.start();				
        
	}
	
	/**
	 * Die Funktion kann zyklisch ausgeführt werden und 
	 */
	public void ladeFunktion(){
		
		//System.out.println("State KEBA: "+actualStateString[actualState]);
		//System.out.println("State Steuerung: "+controllerStatusString[controllerStatus]);
		
		switch (actualPlug) {
		case 0: //Kein Stecker eingesteckt
			
			break;
			
		case 1: // Stecker eingesteckt an Wallbox
			
			break;
			
		case 3: //Stecker eingesteckt an Wallbox und verriegelt, Standard, wenn kein EV eingesteckt ist.
				
			break;
			
		case 5: //Stecker eingesteckt an Wallbox und EV
			
			break;
			
		case 7: //Stecker eingesteckt an Wallbox und EV und verriegelt
			

			switch (controllerStatus){
			
			case 0: //EV nicht verbunden
			
			case 1:	//Warten auf genügend PV- Überschuss
				
				controllerStatus = 2; //-> Der Controller wechselt in den Status "optimierte Ladung"
				sendRequesttoKEBA("ena 1");
				
				break;
				
			case 2:	//Laden optimiert
				
				aendereLadeStrom();
				if(actualInput == 1) { //maximalladung
					minLadeStrom = 32000;
				}
				sendCurrRequesttoKEBA(controllerStrom);
				
				break;
				
			case 3: //Laden definiert
				
				aendereLadeStrom();
				minLadeStrom = 16000;
				sendCurrRequesttoKEBA(controllerStrom);
				
				break;
				
			case 4: //Laden optimiert 1-phasig
				
				break;
					
			}
			
			break;

		default:
			break;
		}
    	
    	switch (actualState) {
		case 0:	//KEBA ist am starten
			
			break;
			
		case 1: //KEBA ist nicht bereit (nicht eingesteckt, x1 oder "ena" nicht gesetzt, RFID nicht enabled...
			controllerStrom = minLadeStrom+3000;

			break;
			
		case 2: //KEBA ist bereit zum laden und wartet auf EV charging request
			controllerStrom = minLadeStrom+3000;
	    	
			break;
			
		case 3: //KEBA ist am laden
			
			break;
			
		case 4: //KEBA hat einen Fehler (Siehe getError)

			break;
			
		case 5: //KEBA hat die Autorisierung zurückgewiesen
			
			break;

		default:
			break;
		}
	}
	
	private void aendereLadeStrom(){
		if(aenderungLadeLeistung>0){ //positive Ladestromänderung
			int aenderungLadestrom = ((aenderungLadeLeistung-ladeOffSet)*1000/230)/5;

			controllerStrom+=aenderungLadestrom;
		}
		else{	//negative Ladestromänderung
			
			int aenderungLadestrom=((aenderungLadeLeistung-ladeOffSet)*1000/230/2);
			controllerStrom+=aenderungLadestrom;
			
		}
	}
	

	
	private void sendCurrRequesttoKEBA(Integer reqToKEBA){
		//TODO Ein absolutes Minumum für den Ladestrom definieren!
		if(reqToKEBA<minLadeStrom){ //Der gewünschte Ladestrom ist zu gering
			controllerStrom = minLadeStrom;
			try {
				vz.sendData("f0c4d0d0-6c55-11ee-98da-934802c138a3", controllerStrom.toString());
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
			sendRequesttoKEBA("curr " + minLadeStrom.toString());

		}
		else if(reqToKEBA>maxLadeStrom){ //Der gewünschte Ladestrom ist zu hoch
			controllerStrom = maxLadeStrom;
			try {
				vz.sendData("f0c4d0d0-6c55-11ee-98da-934802c138a3", controllerStrom.toString());
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
			sendRequesttoKEBA("curr " + maxLadeStrom.toString());

		}
		else{
			try {
				vz.sendData("f0c4d0d0-6c55-11ee-98da-934802c138a3", controllerStrom.toString());
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
			sendRequesttoKEBA("curr " + reqToKEBA.toString());
		}
		
		
	}
	
	
	private void stateChanged(){
		
    	switch (actualState) {
		case 0:	//KEBA ist am starten
			ladenSeit.setEnabled(false);
			break;
			
		case 1: //KEBA ist nicht bereit (nicht eingesteckt, x1 oder "ena" nicht gesetzt, RFID nicht enabled...
			ladenSeit.setEnabled(false);
	
			break;
			
		case 2: //KEBA ist bereit zum laden und wartet auf EV charging request
			ladenSeit.setEnabled(false);
			
			break;
			
		case 3: //KEBA ist am laden
			ladenSeit.reset();
			// TODO Timer "Laden seit" starten

			break;
			
		case 4: //KEBA hat einen Fehler (Siehe getError)

			break;
			
		case 5: //KEBA hat die Autorisierung zurückgewiesen
			
			break;

		default:
			break;
		}
		
		
	}
	
	private void inputChanged() {
		switch (actualInput) {
		case 0:
			sendRequesttoKEBA("ena 1");
			try {
				vz.sendData("a4d3f3f0-6c55-11ee-b0f1-5f5a7e9cf2dc", "0");
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
			
		case 1:
			sendRequesttoKEBA("ena 1");
			try {
				vz.sendData("a4d3f3f0-6c55-11ee-b0f1-5f5a7e9cf2dc", "100");
			} catch (IOException e) {
				// TODO Auto-generated catch block
				e.printStackTrace();
			}
		}
	}
	
	
	private void plugChanged(){
		
		switch (actualPlug) {
		case 0: //Kein Stecker eingesteckt
			controllerStatus = 0;
			sendRequesttoKEBA("ena 1");
			break;
			
		case 1: // Stecker eingesteckt an Wallbox
			controllerStatus = 0;
			sendRequesttoKEBA("ena 1");

			break;
			
		case 3: //Stecker eingesteckt an Wallbox und verriegelt, Standard, wenn kein EV eingesteckt ist.
			controllerStatus = 0;
			sendRequesttoKEBA("ena 1");
			
			break;
			
		case 5: //Stecker eingesteckt an Wallbox und EV
			controllerStatus = 0;
			sendRequesttoKEBA("ena 1");

			break;
			
		case 7: //Stecker eingesteckt an Wallbox und EV und verriegelt

			sendRequesttoKEBA("ena 1");
			sendCurrRequesttoKEBA(10000);
			controllerStatus = 2;
			minLadeStrom = 10000;
			
			break;

		default:
			break;
		}
		
	}
	
	


	/**
	 * Wird ausgeführt, wenn die Funktion receiveDatafromKEBA() ein neues Datenpaket empfangen hat.
	 * Evaluiert, was darin steht und setzt die Variablen dementsprechend.
	 * @param receivedFromKEBA Der empfangene String
	 */
	private void evaluateDatafromKEBA(String receivedFromKEBA) {
		if(receivedFromKEBA.equals("TCH-OK :done\n")){
			// Empfang wurde bestätigt 
			//TODO Empfangsbestätigung verarbeiten, ggfl. catch wenn zu lange keine TCH-OK kam.
			//System.out.println(receivedFromKEBA);
		}else{
			try{
				JSONObject objrecfrmKEBA = new JSONObject(receivedFromKEBA);		
				if(objrecfrmKEBA.has("ID")){
					// Das empfangene ist eine Antwort auf eine Report Anfrage
					if(objrecfrmKEBA.getString("ID").equals("1")){
						// Das empfangene Objekt ist eine Antwort auf eine Report 1 Anfrage

					}else if(objrecfrmKEBA.getString("ID").equals("2")){
						// Das empfangene Objekt ist eine Antwort auf eine Report 2 Anfrage
						actualState=objrecfrmKEBA.getInt("State");
						
						actualInput = objrecfrmKEBA.getInt("Input");
						oldInput = actualInput;
						if(oldInput != actualInput) {
							inputChanged();
						}
						actualPlug=objrecfrmKEBA.getInt("Plug");
						enableSys=objrecfrmKEBA.getInt("Enable sys");
						enableUser=objrecfrmKEBA.getInt("Enable user");
						actualTmoFS=objrecfrmKEBA.getInt("Tmo FS");
						actualMaxCurr=objrecfrmKEBA.getInt("Max curr");
						actualMaxCurrHW=objrecfrmKEBA.getInt("Curr HW");
						actualCurrUser=objrecfrmKEBA.getInt("Curr user");
						actualCurrFS=objrecfrmKEBA.getInt("Curr FS");

					}else if(objrecfrmKEBA.getString("ID").equals("3")){
						// Das empfangene Objekt ist eine Antwort auf eine Report 3 Anfrage
						actualU1 = objrecfrmKEBA.getInt("U1");
						actualU2 = objrecfrmKEBA.getInt("U2");
						actualU3 = objrecfrmKEBA.getInt("U3");
						actualI1 = objrecfrmKEBA.getInt("I1");
						actualI2 = objrecfrmKEBA.getInt("I2");
						actualI3 = objrecfrmKEBA.getInt("I3");
						actualP = objrecfrmKEBA.getInt("P");
						actualPF = objrecfrmKEBA.getInt("PF");
						actualE = objrecfrmKEBA.getInt("E pres")*10;

					}
				} else if(objrecfrmKEBA.has("State")){
					// Das empfangene Objekt ist ein "State"- Broadcast
					oldState = actualState;
					actualState = objrecfrmKEBA.getInt("State");
					stateChanged();

				}else if(objrecfrmKEBA.has("Plug")){
					// Das empfangene Objekt ist ein "Plug"- Broadcast
					oldPlug = actualPlug;
					actualPlug = objrecfrmKEBA.getInt("Plug");
					plugChanged();

				} else if(objrecfrmKEBA.has("Input")){
					//TODO Input bearbeiten
					// Das empfangene Objekt ist ein "Input"- Broadcast
					oldInput = actualInput;
					actualInput = objrecfrmKEBA.getInt("Input");
					inputChanged();

				} else if(objrecfrmKEBA.has("Enable sys")){
					// Das empfangene Objekt ist ein "Enable sys"- Broadcast
					enableSys = objrecfrmKEBA.getInt("Enable sys");

				} else if(objrecfrmKEBA.has("Max curr")){
					// Das empfangene Objekt ist ein "Max curr"- Broadcast
					actualMaxCurr = objrecfrmKEBA.getInt("Max curr");

				} else if(objrecfrmKEBA.has("E pres")){
					// Das empfangene Objekt ist ein "E pres"- Broadcast
					actualE = objrecfrmKEBA.getInt("E pres");

				} else{
					// Das empfangene Objekt hat eine andere ID

				}
			}catch (Exception e) {
				System.out.println(e);

			}
		}

	}
	

	
	
	
	
	/**
	 * Sendet Anfragen an die KEBA Ladestation
	 * 
	 * @param anfrage
	 * Anfrage an KEBA Ladestation
	 * 
	 */
	public void sendRequesttoKEBA(String anfrage){
		//Daten Senden

		service.waitxmilis(100);
	    byte[] sendData = new byte[512];    //kann verkleinert werden auf ein paar bytes
		sendData = anfrage.getBytes();	//wandelt einen String in bytes um
	    InetAddress hostAddress;
		try {
			hostAddress = InetAddress.getByName(ipKEBA);//TODO Hier sollte man auch ohne angabe der IP Daten senden können...
		} catch (UnknownHostException e1) {
			hostAddress = null;
			e1.printStackTrace();
		}

		DatagramPacket sendPacket =
				new DatagramPacket(sendData, sendData.length, hostAddress, portKEBA);
		try {
			us.send(sendPacket);
		} catch (IOException e) {
			e.printStackTrace();
		}
	}

	
	/**
	 * Sendet einen Request an die KEBA für die Failsafe- Funktion
	 * @param timeoutZeit Die Zeit in s, nach welcher die Funktion bei Verbindungsunterbruch aktiviert wurde
	 * @param ladestromimFailsafe Der Strom, welcher die KEBA einstellt, wenn keine Verbindung mehr vorhanden ist
	 * @param speichern bei 1 wird die Funktion im EEPROM gespeichert, bei 0 nicht
	 */
	private void setKEBAFailsafeTime(Float timeoutZeit, Float ladestromimFailsafe, Integer speichern){
		sendRequesttoKEBA("failsafe " + timeoutZeit.toString() + " " + ladestromimFailsafe.toString() + " " + speichern.toString());
	}
	
	
	/**
	 * @param relaisstatus 0 Relais offen, 1 Relais geschlossen, >=10 - ca. 150 Pulse/kWh
	 */
	private void setKEBAoutputRelais(Integer relaisstatus){
		sendRequesttoKEBA("output " + relaisstatus.toString());
	}
	

	// Ab hier getter und setter Methoden dieser Klasse	
	/**
	 * @return Controller- Strom der KEBA- Smarthome Steuerung
	 */
	public Integer getcontrollerCurrent(){
		return controllerStrom;
	}
	
	/**
	 * Gibt den aktuellen Status der KEBA zurück.
	 * 
	 * @return
	 * 0: KEBA ist am starten<br>
	 * 1: KEBA ist nicht bereit (nicht eingesteckt, x1 oder "ena" nicht gesetzt, RFID nicht enabled...<br>
	 * 2: KEBA ist bereit zum laden und wartet auf EV charging request<br>
	 * 3: KEBA ist am laden<br>
	 * 4: KEBA hat einen Fehler (Siehe getError)<br>
	 * 5: KEBA hat die Autorisierung zurückgewiesen<br>
	 */
	public Integer getactualState(){
		return actualState;
	}
	
	/**
	 * Gibt den aktuellen Status des KEBA-Steckers zurück. Kann eigentlich nur state 0, 5 und 7 annehmen?!<br>
	 * @return
	 * 0: Stecker nicht eingesteckt<br>
	 * 1: Eingesteckt an Wallbox<br>
	 * 3: Eingesteckt an Wallbox und verriegelt<br>
	 * 5: Eingesteckt an Wallbox und EV<br>
	 * 7: Eingesteckt an Wallbox und EV, verriegelt<br>
	 */
	public Integer getactualPlug(){
		return actualPlug;

	}

	/**
	 * @return Aktuelle Spannung U1 an der KEBA
	 */
	public Integer getActualU1() {
		return actualU1;
	}

	/**
	 * @return Aktuelle Spannung U2 an der KEBA
	 */
	public Integer getActualU2() {
		return actualU2;
	}

	/**
	 * @return Aktuelle Spannung U3 an der KEBA
	 */
	public Integer getActualU3() {
		return actualU3;
	}

	/**
	 * @return Aktueller Strom I1 in mA an der KEBA
	 */
	public Integer getActualI1() {
		return actualI1;
	}

	/**
	 * @return Aktueller Strom I2 in mA an der KEBA
	 */
	public Integer getActualI2() {
		return actualI2;
	}

	/**
	 * @return Aktueller Strom I3 in mA an der KEBA
	 */
	public Integer getActualI3() {
		return actualI3;
	}

	/**
	 * @return Aktuelle Wirkleistung in W an der KEBA
	 */
	public Float getActualP() {
		return (float) actualP/1000;
	}

	/**
	 * @return Aktueller Powerfactor an der KEBA
	 */
	public Integer getActualPF() {
		
		return actualPF/10;
	}

	/**
	 * @return Energie in Wh der aktuellen Ladung an der KEBA
	 */
	public Integer getActualE() {
		return actualE*10;
	}

	/**
	 * @return Current preset value via Control pilot in milliampere.
	 */
	public int getActualMaxCurr() {
		return actualMaxCurr;
	}

	/**
	 * @return Highest possible charging current of the charging connection. Contains device maximum, DIP-switch setting, cable coding and temperature reduction.
	 */
	public int getActualMaxCurrHW() {
		return actualMaxCurrHW;
	}

	/**
	 * @return Current preset value of the user via UDP
	 */
	public int getActualCurrUser() {
		return actualCurrUser;
	}

	/**
	 * @return Aktuell eingestellter "Failsafe"-Strom
	 */
	public int getActualCurrFS() {
		return actualCurrFS;
	}


	public int getEnableSys() {
		return enableSys;
	}

	public int getEnableUser() {
		return enableUser;
	}
	
	public Integer getInput() {
		return actualInput;
	}


	public void setAenderungLadeLeistung(Float aenderungLadeLeistung) {
		this.aenderungLadeLeistung = Math.round(aenderungLadeLeistung);
	}


	public Integer getControllerState() {
		return controllerStatus;
	}


	public void setControllerState(Integer controllerState) {
		this.controllerStatus = controllerState;
	}
}



