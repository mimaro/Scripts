#!/usr/bin/env python3
"""
Dynamische Rueckspeisebegrenzung fuer Fronius Symo via Modbus TCP (SunSpec)
============================================================================

Liest periodisch den Bilanzwert von einer lokalen Messquelle (per UUID, z.B.
volkszaehler-Middleware) und regelt WMaxLimPct des Wechselrichters so, dass
eine lokal definierte Rueckspeiselimite (in Watt) eingehalten wird.

Konvention Bilanzwert:
    negativ = Ueberschuss (Einspeisung ins Netz)
    positiv = Bezug aus dem Netz

WICHTIG VOR DEM EINSATZ:
- Modbus TCP + SunSpec + externe Steuerung muessen im Fronius-Webinterface
  aktiviert sein (Kommunikation -> Modbus).
- Die SunSpec-Modelladressen werden zur Laufzeit automatisch discovert
  (Modell 103 = Inverter Float, Modell 123 = Immediate Controls). Der exakte
  Registeroffset fuer 'W' (AC-Wirkleistung) innerhalb Modell 103 sowie ein
  eventuelles WMaxLim_Ena-Bit in Modell 123 SOLLTEN gegen das offizielle
  Fronius "Modbus TCP & RTU Register Map"-Dokument geprueft werden, da sich
  Details je nach Datamanager-Firmware unterscheiden koennen.
- get_bilanz_w() ist auf das volkszaehler-Middleware-Format ausgelegt
  (aufgrund der Formulierung "UUID Bilanz"). Falls eine andere Quelle
  (Loxone, MQTT, eigene REST-API, ...) verwendet wird, muss nur diese eine
  Funktion angepasst werden.
"""

import time
import logging
import requests
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian

# ---------------------------------------------------------------------------
# Konfiguration - anpassen!
# ---------------------------------------------------------------------------
FRONIUS_IP = "192.168.1.50"
FRONIUS_PORT = 502
FRONIUS_UNIT_ID = 1                 # Modbus Slave-/Unit-ID des Wechselrichters

BILANZ_API_URL = "http://localhost/middleware.php/data/{uuid}.json?from=now"
BILANZ_UUID = "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

RUECKSPEISE_LIMIT_W = 5000.0        # max. zulaessige Einspeisung (positiv, Watt)
NENNLEISTUNG_W = 12500.0            # Symo 12.5-3-M

MIN_LIMIT_PCT = 0.0
MAX_LIMIT_PCT = 100.0
HYSTERESE_W = 100.0                 # Totband gegen Pendeln
SCHRITTWEITE_ERHOEHUNG_PCT = 1.0    # vorsichtiges Wiederhochfahren pro Zyklus
POLL_INTERVALL_S = 5

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("rueckspeiseregelung")


# ---------------------------------------------------------------------------
# SunSpec-Modelldiscovery ueber pymodbus
# (findet Register-Startadressen automatisch statt sie hart zu codieren)
# ---------------------------------------------------------------------------
class SunSpecMap:
    SUNSPEC_BASE_CANDIDATES = [40000, 0]  # je nach Firmware/Zaehlweise

    def __init__(self, client: ModbusTcpClient, unit_id: int):
        self.client = client
        self.unit_id = unit_id
        self.models = {}  # model_id -> (start_adresse_der_nutzdaten, laenge)
        self._discover()

    def _read(self, address, count):
        rr = self.client.read_holding_registers(address=address, count=count, slave=self.unit_id)
        if rr.isError():
            raise ModbusException(f"Lesefehler an Adresse {address}")
        return rr.registers

    def _discover(self):
        for base in self.SUNSPEC_BASE_CANDIDATES:
            try:
                marker = self._read(base, 2)
            except ModbusException:
                continue
            if (marker[0] << 16 | marker[1]) == 0x53756E53:  # "SunS"
                addr = base + 2
                break
        else:
            raise RuntimeError("Kein SunSpec-Geraet gefunden (Marker 'SunS' fehlt)")

        while True:
            header = self._read(addr, 2)
            model_id, length = header[0], header[1]
            if model_id == 0xFFFF:
                break
            self.models[model_id] = (addr + 2, length)
            addr += 2 + length
        log.info("Gefundene SunSpec-Modelle: %s", sorted(self.models.keys()))

    def data_address(self, model_id):
        if model_id not in self.models:
            raise RuntimeError(f"SunSpec-Modell {model_id} nicht gefunden")
        return self.models[model_id][0]


# ---------------------------------------------------------------------------
# Wechselrichter-Zugriff
# ---------------------------------------------------------------------------
class FroniusInverter:
    MODEL_INVERTER_FLOAT = 103   # dreiphasig, Float-Werte (AC-Leistung etc.)
    MODEL_CONTROLS = 123         # Immediate Controls (WMaxLimPct)

    def __init__(self, ip, port, unit_id):
        self.client = ModbusTcpClient(ip, port=port)
        if not self.client.connect():
            raise ConnectionError(f"Verbindung zu {ip}:{port} fehlgeschlagen")
        self.unit_id = unit_id
        self.map = SunSpecMap(self.client, unit_id)

    def _read(self, address, count):
        rr = self.client.read_holding_registers(address=address, count=count, slave=self.unit_id)
        if rr.isError():
            raise ModbusException(f"Lesefehler an Adresse {address}")
        return rr.registers

    def _write(self, address, value):
        rq = self.client.write_register(address=address, value=value, slave=self.unit_id)
        if rq.isError():
            raise ModbusException(f"Schreibfehler an Adresse {address}")

    def get_current_ac_power_w(self):
        """Aktuelle AC-Wirkleistung in Watt (Modell 103).
        Offset 2 ist der uebliche Ort von 'W' als Float32 - vor Produktivbetrieb
        gegen das Fronius-Registerhandbuch verifizieren."""
        base = self.map.data_address(self.MODEL_INVERTER_FLOAT)
        regs = self._read(base + 2, 2)
        return self._decode_float32(regs)

    def get_wmaxlimpct(self):
        base = self.map.data_address(self.MODEL_CONTROLS)
        regs = self._read(base, 1)
        return regs[0] / 100.0  # SunSpec: 1/100 %

    def set_wmaxlimpct(self, prozent):
        prozent = max(MIN_LIMIT_PCT, min(MAX_LIMIT_PCT, prozent))
        base = self.map.data_address(self.MODEL_CONTROLS)
        wert = int(round(prozent * 100))
        self._write(base, wert)
        # Hinweis: manche Firmware-Staende verlangen zusaetzlich das Setzen
        # eines WMaxLim_Ena-Bits (i.d.R. direkt im Anschluss an WMaxLimPct
        # im selben Modell) - im Registerhandbuch pruefen, falls die Grenze
        # trotz erfolgreichem Schreiben ignoriert wird.
        log.info("WMaxLimPct gesetzt auf %.1f %%", prozent)
        return prozent

    @staticmethod
    def _decode_float32(regs):
        decoder = BinaryPayloadDecoder.fromRegisters(regs, byteorder=Endian.BIG, wordorder=Endian.BIG)
        return decoder.decode_32bit_float()

    def close(self):
        self.client.close()


# ---------------------------------------------------------------------------
# Bilanzwert von der Messquelle holen
# ---------------------------------------------------------------------------
def get_bilanz_w(uuid):
    """Liefert den aktuellen Bilanzwert in Watt.
    Negativ = Ueberschuss (Einspeisung), Positiv = Bezug.
    An die tatsaechliche Messquelle anpassen, falls es nicht volkszaehler ist."""
    url = BILANZ_API_URL.format(uuid=uuid)
    resp = requests.get(url, timeout=5)
    resp.raise_for_status()
    data = resp.json()
    return float(data["data"]["tuples"][-1][1])  # volkszaehler-Format: [ts, wert]


# ---------------------------------------------------------------------------
# Regelschleife
# ---------------------------------------------------------------------------
def regel_schleife():
    inverter = FroniusInverter(FRONIUS_IP, FRONIUS_PORT, FRONIUS_UNIT_ID)
    try:
        while True:
            try:
                bilanz = get_bilanz_w(BILANZ_UUID)
                ueberschuss = max(0.0, -bilanz)
                aktueller_limit_pct = inverter.get_wmaxlimpct()
                aktuelle_ac_leistung = inverter.get_current_ac_power_w()

                abweichung = ueberschuss - RUECKSPEISE_LIMIT_W

                if abweichung > HYSTERESE_W:
                    # zu viel Einspeisung -> Leistung sofort um die Differenz reduzieren
                    ziel_leistung_w = max(0.0, aktuelle_ac_leistung - abweichung)
                    neuer_pct = (ziel_leistung_w / NENNLEISTUNG_W) * 100.0
                    inverter.set_wmaxlimpct(neuer_pct)
                    log.info(
                        "Ueberschuss %.0f W > Limite %.0f W -> reduziere auf %.1f %% (%.0f W)",
                        ueberschuss, RUECKSPEISE_LIMIT_W, neuer_pct, ziel_leistung_w,
                    )
                elif abweichung < -HYSTERESE_W and aktueller_limit_pct < MAX_LIMIT_PCT:
                    # Reserve vorhanden -> Limit vorsichtig wieder anheben
                    neuer_pct = min(MAX_LIMIT_PCT, aktueller_limit_pct + SCHRITTWEITE_ERHOEHUNG_PCT)
                    inverter.set_wmaxlimpct(neuer_pct)
                    log.info(
                        "Ueberschuss %.0f W < Limite %.0f W -> Limit langsam anheben auf %.1f %%",
                        ueberschuss, RUECKSPEISE_LIMIT_W, neuer_pct,
                    )
                else:
                    log.debug("Im Toleranzband, keine Aenderung (Ueberschuss %.0f W)", ueberschuss)

            except (ModbusException, requests.RequestException) as exc:
                log.error("Fehler im Regelzyklus: %s", exc)

            time.sleep(POLL_INTERVALL_S)
    finally:
        inverter.close()


if __name__ == "__main__":
    regel_schleife()
