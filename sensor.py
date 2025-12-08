# ariya_elm327_wifi.py
# Version restaurée basée sur la version fournie par l'utilisateur (vendredi)
# Style synchrone, sockets fermés explicitement, logique de connexion identique.

import socket, time, logging
from datetime import timedelta
from homeassistant.helpers.entity import Entity
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricPotential,
)

_LOGGER = logging.getLogger(__name__)
DOMAIN = "ariya_elm327_wifi"

DEFAULT_SCAN_INTERVAL_MINUTES = 10  # valeur par défaut

def check_host(ip, port, timeout=1):
    """Retourne True si l'IP/port répond, False sinon."""
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

def send(sock, cmd):
    """Envoie une commande et lit une réponse simple (recv unique)."""
    sock.send((cmd + "\r").encode())
    time.sleep(0.3)
    try:
        return sock.recv(4096).decode(errors="ignore")
    except Exception:
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
                return (A*256 + B)/divisor
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

    @property
    def should_poll(self):
        return True

    @property
    def scan_interval(self):
        return self.hass.data[DOMAIN].get("scan_interval", timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES))

    def _connect_and_query(self, pid, header="ATSHDB33F1"):
        if not check_host(self._ip, self._port):
            return None
        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect((self._ip, self._port))
            # Init sequence (version fonctionnelle)
            send(sock, "ATZ"); send(sock, "ATE0"); send(sock, "ATH1"); send(sock, "ATSP7")
            send(sock, "ATCRA18DAF1DB"); send(sock, "ATFCSH18DADBF1")
            send(sock, "ATFCSD300000"); send(sock, "ATFCSM1")
            send(sock, header)
            raw = send(sock, pid)
            sock.close()
            return raw
        except Exception:
            return None
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

# Petit coordinator pour partager la valeur SOC
class SocCoordinator:
    def __init__(self, config, hass):
        self.config = config
        self.hass = hass
        self.soc_bms = None

    def update(self):
        raw = BaseAriyaSensor(self.config, self.hass)._connect_and_query("229001", header="ATSHDB33F1")
        val = decode_value(raw)
        if val is not None:
            self.soc_bms = round(val, 2)
        else:
            self.soc_bms = None

async def async_setup_entry(hass, entry, async_add_entities):
    data = entry.data
    options = entry.options

    scan_interval_minutes = options.get("scan_interval_minutes", DEFAULT_SCAN_INTERVAL_MINUTES)
    hass.data.setdefault(DOMAIN, {})["scan_interval"] = timedelta(minutes=scan_interval_minutes)

    coordinator = SocCoordinator(data, hass)

    async_add_entities([
        AriyaSocRawSensor(coordinator),
        AriyaSocSensor(coordinator),
        AriyaElmVoltageSensor(data, hass),
    ], True)

class AriyaSocSensor(Entity):
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
        if self.coordinator.soc_bms is not None:
            self._state = self.coordinator.soc_bms
        else:
            self._state = None

class AriyaElmVoltageSensor(BaseAriyaSensor):
    def __init__(self, config, hass):
        super().__init__(config, hass)
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
        raw = self._connect_and_query("ATRV", header="ATSHDB33F1")
        # parse simple: chercher nombre suivi de V
        if raw:
            import re
            m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*[Vv]", raw)
            if m:
                try:
                    self._state = round(float(m.group(1).replace(",", ".")), 2)
                    return
                except Exception:
                    pass
        self._state = None
