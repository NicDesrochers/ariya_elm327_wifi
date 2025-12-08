# ariya_elm327_wifi.py
# Version avec cache 30s, réveil ECU si tension basse et lecture SOC corrigée

import socket, time, logging, re, datetime
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ariya_elm327_wifi"

DEFAULT_SCAN_INTERVAL_MINUTES = 1  # lecture chaque minute
SCAN_INTERVAL = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

def check_host(ip, port, timeout=1):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

def send(sock, cmd):
    _LOGGER.debug("Envoi commande: %s", cmd)
    sock.send((cmd + "\r").encode())
    time.sleep(0.3)
    try:
        resp = sock.recv(4096).decode(errors="ignore")
        _LOGGER.debug("Réponse brute: %s", resp.strip())
        return resp
    except Exception as e:
        _LOGGER.warning("Erreur recv: %s", e)
        return None

def decode_value(response, divisor=100.0):
    if not response:
        return None
    tokens = response.split()
    _LOGGER.debug("Tokens reçus: %s", tokens)
    if "62" in tokens:
        try:
            idx = tokens.index("62")
            if idx+4 < len(tokens):
                A = int(tokens[idx+3], 16)
                B = int(tokens[idx+4], 16)
                val = (A*256 + B)/divisor
                _LOGGER.debug("Valeur décodée: %s", val)
                return val
        except Exception as e:
            _LOGGER.warning("Erreur decode_value: %s (réponse=%s)", e, response)
            return None
    return None

def correct_soc(soc_bms):
    return soc_bms - 6

class BaseAriyaSensor(Entity):
    def __init__(self, config, hass):
        self._ip = config["elm_ip"]
        self._port = config["elm_port"]
        self._state = None
        self.hass = hass

    def _connect_and_query(self, pid, header="ATSHDB33F1", wakeup=False):
        if not check_host(self._ip, self._port):
            _LOGGER.debug("Host %s:%s non joignable", self._ip, self._port)
            return None
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self._ip, self._port))
            # Init sequence
            for cmd in ["ATZ","ATE0","ATH1","ATSP7",
                        "ATCRA18DAF1DB","ATFCSH18DADBF1",
                        "ATFCSD300000","ATFCSM1",header]:
                send(sock, cmd)

            # Réveil ECU si demandé
            if wakeup:
                _LOGGER.debug("Envoi séquence réveil ECU")
                send(sock, "1003")   # Diagnostic Session Control
                time.sleep(0.2)
                send(sock, "3E00")   # Tester Present

            raw = send(sock, pid)
            return raw
        except Exception as e:
            _LOGGER.error("Erreur _connect_and_query: %s", e)
            return None
        finally:
            if sock:
                try: sock.close()
                except Exception: pass

class SocCoordinator:
    def __init__(self, config, hass):
        self.config = config
        self.hass = hass
        self.soc_bms = None
        self.voltage_12v = None
        self._last_update = None

    def update(self):
        """Met à jour voltage et SOC avec cache de 30 secondes."""
        now = datetime.datetime.now()
        if self._last_update and (now - self._last_update).total_seconds() < 30:
            _LOGGER.debug("Update déjà effectué il y a %.1f s, réutilise les valeurs",
                          (now - self._last_update).total_seconds())
            return

        self._last_update = now

        if not check_host(self.config["elm_ip"], self.config["elm_port"]):
            _LOGGER.debug("Host non dispo, conserve anciennes valeurs")
            return

        # Lire le voltage
        raw_v = BaseAriyaSensor(self.config, self.hass)._connect_and_query("ATRV")
        if raw_v:
            m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*[Vv]", raw_v)
            if m:
                try:
                    self.voltage_12v = round(float(m.group(1).replace(",", ".")), 2)
                    _LOGGER.debug("Voltage 12V lu: %.2f V", self.voltage_12v)
                except Exception as e:
                    _LOGGER.warning("Erreur parsing voltage: %s", e)

        # Lire le SOC si inconnu OU si voltage > 12.8
        if self.soc_bms is None or (self.voltage_12v and self.voltage_12v > 12.8):
            wakeup_needed = self.voltage_12v and self.voltage_12v <= 12.8
            _LOGGER.debug("Tentative lecture SOC (voltage=%.2f, wakeup=%s)",
                          self.voltage_12v if self.voltage_12v else -1,
                          wakeup_needed)
            raw_soc = BaseAriyaSensor(self.config, self.hass)._connect_and_query("229001",
                                                                                 wakeup=wakeup_needed)
            if raw_soc:
                val = decode_value(raw_soc)
                if val is not None:
                    self.soc_bms = round(val, 2)
                    _LOGGER.debug("SOC BMS mis à jour: %.2f %%", self.soc_bms)
                else:
                    _LOGGER.debug("SOC BMS non décodable, conserve ancienne valeur")
            else:
                _LOGGER.debug("Pas de réponse SOC, conserve ancienne valeur")

async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.data
    coordinator = SocCoordinator(data, hass)

    async_add_entities([
        AriyaSocRawSensor(coordinator),
        AriyaSocSensor(coordinator),
        AriyaElmVoltageSensor(coordinator),
    ], True)

class AriyaSocSensor(Entity):
    should_poll = True
    scan_interval = SCAN_INTERVAL

    def __init__(self, coordinator): 
        self.coordinator = coordinator
        self._state = None

    @property
    def name(self): return "Ariya SOC corrigé"
    @property
    def unit_of_measurement(self): return PERCENTAGE
    @property
    def icon(self): return "mdi:battery"
    @property
    def state(self): return self._state

    def update(self):
        self.coordinator.update()
        if self.coordinator.soc_bms is not None:
            self._state = round(correct_soc(self.coordinator.soc_bms), 2)
        else:
            self._state = None

class AriyaSocRawSensor(Entity):
    should_poll = True
    scan_interval = SCAN_INTERVAL

    def __init__(self, coordinator): 
        self.coordinator = coordinator
        self._state = None

    @property
    def name(self): return "Ariya SOC brut"
    @property
    def unit_of_measurement(self): return PERCENTAGE
    @property
    def icon(self): return "mdi:battery"
    @property
    def state(self): return self._state

    def update(self):
        self.coordinator.update()
        self._state = self.coordinator.soc_bms

class AriyaElmVoltageSensor(Entity):
    should_poll = True
    scan_interval = SCAN_INTERVAL

    def __init__(self, coordinator): 
        self.coordinator = coordinator
        self._state = None

    @property
    def name(self): return "ELM327 Voltage"
    @property
    def unit_of_measurement(self): return UnitOfElectricPotential.VOLT
    @property
    def icon(self): return "mdi:flash"
    @property
    def state(self): return self._state

    def update(self):
        self.coordinator.update()
        self._state = self.coordinator.voltage_12v
