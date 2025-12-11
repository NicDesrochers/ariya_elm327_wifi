import asyncio
import logging
import re
import datetime
import socket
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def send(sock, cmd):
    sock.send((cmd + "\r").encode())
    await asyncio.sleep(0.3)
    try:
        resp = sock.recv(4096).decode(errors="ignore")
        return resp.strip()
    except Exception:
        return None

def check_host(ip, port, timeout=1):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

def decode_value(response, divisor=100.0):
    if not response:
        return None
    tokens = response.split()
    if "62" in tokens:
        try:
            idx = tokens.index("62")
            if idx + 4 < len(tokens):
                A = int(tokens[idx+3], 16)
                B = int(tokens[idx+4], 16)
                return (A*256 + B)/divisor
        except Exception:
            return None
    return None

def decode_hv_voltage(response):
    tokens = response.split()
    if "62" in tokens:
        try:
            idx = tokens.index("62")
            if tokens[idx+1].upper() == "20" and tokens[idx+2].upper() == "FE":
                A = int(tokens[idx+3], 16)
                B = int(tokens[idx+4], 16)
                raw = A*256 + B
                return round(raw/10.0, 2)
        except Exception:
            return None
    return None

class SocCoordinator(DataUpdateCoordinator):
    """Coordinator qui gère SOC / Voltage / HV Battery."""

    def __init__(self, config, hass):
        super().__init__(
            hass,
            _LOGGER,
            name="ariya_elm327_wifi",
            update_interval=datetime.timedelta(seconds=60),
        )
        self.config = config
        self._last_valid_soc = None
        self._last_valid_voltage = None
        self._last_valid_hv_voltage = None
        self._last_host_unavailable = None
        self._force_refresh = False   # <-- flag pour bouton
        self._first_run = True        # <-- force la première lecture au boot

    async def async_force_refresh(self):
        """Force un refresh complet SOC/HV même si 12V < 12.8."""
        self._force_refresh = True
        _LOGGER.info("Refresh manuel forcé via bouton")
        await self.async_request_refresh()

    async def _async_wakeup_ecu(self, sock):
        """Envoie les commandes de réveil ECU (1003 + 3E00)."""
        try:
            await send(sock, "ATSHDADAF1")
            _LOGGER.info("Wakeup ECU: envoi des commandes 1003 + 3E00")
            await send(sock, "1003")
            await asyncio.sleep(0.2)
            await send(sock, "3E00")
        except Exception as e:
            _LOGGER.error("Erreur wakeup ECU: %s", e)

    async def _async_update_data(self):
        soc_bms = self._last_valid_soc
        hv_voltage = self._last_valid_hv_voltage
        voltage_12v = self._last_valid_voltage

        if not check_host(self.config["elm_ip"], self.config["elm_port"]):
            self._last_host_unavailable = datetime.datetime.now()
            _LOGGER.warning("ELM327 indisponible, on conserve les dernières valeurs")
            return {
                "soc_bms": soc_bms,
                "voltage_12v": voltage_12v,
                "hv_voltage": hv_voltage,
            }

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.config["elm_ip"], self.config["elm_port"]))

            # Initialisation commune
            for cmd in ["ATZ","ATE0","ATH1","ATSP7","ATFCSM1"]:
                await send(sock, cmd)

            # Lecture 12V
            raw_v = await send(sock, "ATRV")
            _LOGGER.debug("Réponse brute ATRV: %s", raw_v)
            if raw_v:
                m = re.search(r"(-?\d+(?:[.,]\d+)?)\s*[Vv]", raw_v)
                if m:
                    try:
                        voltage_12v = round(float(m.group(1).replace(",", ".")), 2)
                        self._last_valid_voltage = voltage_12v
                    except Exception:
                        pass

            # Condition SOC/HV
            force_due_to_timeout = False
            if self._last_host_unavailable:
                delta = datetime.datetime.now() - self._last_host_unavailable
                if delta.total_seconds() > 1800:
                    force_due_to_timeout = True
                    _LOGGER.info("Force refresh SOC/HV après reconnexion >30min")
                self._last_host_unavailable = None

            if voltage_12v and (voltage_12v > 12.8 or force_due_to_timeout or self._force_refresh or self._first_run):
                _LOGGER.debug("Lecture SOC/HV déclenchée (12V=%s, force=%s, bouton=%s, first_run=%s)",
                              voltage_12v, force_due_to_timeout, self._force_refresh, self._first_run)

                # reset flags
                if self._force_refresh:
                    self._force_refresh = False
                if self._first_run:
                    self._first_run = False

                # 🔎 Ajout : réveil ECU si première lecture ou voltage bas
                if voltage_12v < 12.8 or force_due_to_timeout or self._first_run:
                    await self._async_wakeup_ecu(sock)

                # SOC
                await send(sock, "ATSHDB33F1")
                raw_soc = await send(sock, "229001")
                _LOGGER.debug("Réponse brute SOC: %s", raw_soc)
                val = decode_value(raw_soc)
                _LOGGER.debug("Décodage SOC: %s", val)
                if val is not None:
                    soc_bms = round(val, 2)
                    self._last_valid_soc = soc_bms

                # HV
                await send(sock, "ATSHDADAF1")
                await send(sock, "ATCRA18DAF1DA")
                raw_hv = await send(sock, "2220FE")
                _LOGGER.debug("Réponse brute HV: %s", raw_hv)
                hv_val = decode_hv_voltage(raw_hv) if raw_hv else None
                _LOGGER.debug("Décodage HV: %s", hv_val)
                if hv_val is not None:
                    hv_voltage = hv_val
                    self._last_valid_hv_voltage = hv_voltage

        except Exception as e:
            _LOGGER.error("Erreur session ELM327: %s", e)
        finally:
            if sock:
                try:
                    sock.close()
                except Exception:
                    pass

        data = {
            "soc_bms": soc_bms,
            "voltage_12v": voltage_12v,
            "hv_voltage": hv_voltage,
        }
        _LOGGER.debug("Données mises à jour: %s", data)
        return data
