import asyncio
import logging
import re
import datetime
import socket
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

async def send(sock, cmd):
    sock.send((cmd + "\r").encode())
    await asyncio.sleep(0.5)
    try:
        resp = sock.recv(4096).decode(errors="ignore")
        # Nettoyer : retirer \r, \n, >, espaces multiples
        clean_resp = resp.replace('\r', ' ').replace('\n', ' ').replace('>', '').strip()
        # Réduire les espaces multiples
        clean_resp = ' '.join(clean_resp.split())
        _LOGGER.debug("ELM CMD: %s -> RESP: %s", cmd, clean_resp)
        return clean_resp
    except Exception:
        return None

def check_host(ip, port, timeout=1):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False

class SocCoordinator(DataUpdateCoordinator):
    def __init__(self, config, hass):
        super().__init__(
            hass, _LOGGER, name="ariya_elm327_wifi",
            update_interval=datetime.timedelta(minutes=2),  # Probe 12V toutes les 2 minutes
        )
        self.config = config
        self._force_refresh = False
        self._first_run = True
        self._last_full_update = None  # Timestamp de la dernière lecture complète 

    async def async_force_refresh(self):
        self._force_refresh = True
        _LOGGER.info("Refresh manuel forcé")
        await self.async_request_refresh()

    async def _async_update_data(self):
        data = self.data if self.data else {
            "soc_bms": None, "voltage_12v": None, "hv_voltage": None,
            "battery_amps": 0.0, "current_amps": 0.0, "remaining_kwh": None,
            "battery_temp": None, "battery_power": 0.0
        }

        if not check_host(self.config["elm_ip"], self.config["elm_port"]):
            return data

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect((self.config["elm_ip"], self.config["elm_port"]))

            for cmd in ["ATZ", "ATE0", "ATH1", "ATSP7", "ATCAF1"]:
                await send(sock, cmd)

            raw_v = await send(sock, "ATRV")
            voltage_12v = None
            if raw_v:
                m = re.search(r"(\d+\.\d+)", raw_v)
                if m:
                    voltage_12v = data["voltage_12v"] = float(m.group(1))

            # Protection 12V (13.5V) + Force si premier run ou bouton
            now = datetime.datetime.now()
            should_do_full_update = False
            
            if self._first_run or self._force_refresh:
                should_do_full_update = True
            elif voltage_12v and voltage_12v > 13.5:
                if self._last_full_update is None or (now - self._last_full_update) >= datetime.timedelta(hours=1):
                    should_do_full_update = True
            
            if should_do_full_update:
                
                # On marque le succès pour ne plus forcer au prochain tour si tension basse
                if self._first_run or self._force_refresh:
                    _LOGGER.debug("Lecture forcée ou initiale activée")
                
                self._first_run = False
                self._force_refresh = False
                self._last_full_update = datetime.datetime.now()

                await send(sock, "ATSHDB33F1")
                await send(sock, "ATCRA18DAF1DB")
                await send(sock, "1003")
                await asyncio.sleep(0.8)

                # --- SOC ---
                await send(sock, "ATFCSM0")
                res = await send(sock, "229001")
                #await send(sock, "ATFCSM1")
                if res and "62 90 01" in res:
                    t = res.split("62 90 01")[1].split()
                    data["soc_bms"] = round((int(t[0], 16) * 256 + int(t[1], 16)) / 100.0, 2)

                # --- HV VOLTAGE ---
                #await send(sock, "ATFCSM0")
                res = await send(sock, "229006")
                #await send(sock, "ATFCSM1")
                if res and "62 90 06" in res:
                    t = res.split("62 90 06")[1].split()
                    # Utilisation des octets t[1] et t[2] selon le backup
                    raw_v_hv = int(t[1], 16) * 256 + int(t[2], 16)
                    data["hv_voltage"] = round(raw_v_hv / 4.0, 1)

                # --- CURRENT ---
                #await send(sock, "ATFCSM0")
                res_i = await send(sock, "2291CF")
                if res_i and "62 91 CF" in res_i:
                    # On isole les octets de données situés après le PID
                    t = res_i.split("62 91 CF")[1].split()
                    
                    if len(t) >= 2:
                        # Conversion Hex -> Int 16-bit (Big Endian)
                        raw_i = int(t[0], 16) * 256 + int(t[1], 16)
                        
                        # Gestion du complément à deux (pour les valeurs négatives)
                        if raw_i > 32767: 
                            raw_i -= 65536
                            
                        # Le facteur magique Nissan est 1/64
                        # 31867 / 64 = 497.92A
                        data["battery_amps"] = abs(round(raw_i / 64.0, 1))
                
                res_i = await send(sock, "229284")
                if res_i and "62 92 84" in res_i:
                    t = res_i.split("62 92 84")[1].split()
                    # Décodage des deux derniers octets (46 42 par ex)
                    raw_i = int(t[-2], 16) * 256 + int(t[-1], 16)
                    if raw_i > 32767: raw_i -= 65536
                    data["current_amps"] = abs(round(raw_i / 1000.0, 2))
                # --- ENERGY ---
                #await send(sock, "ATFCSM0")
                res_e = await send(sock, "2291C8")
                #await send(sock, "ATFCSM1")
                if res_e and "62 91 C8" in res_e:
                    t = res_e.split("62 91 C8")[1].split()
                    if len(t) >= 3:
                        wh = (int(t[0], 16) * 65536) + (int(t[1], 16) * 256) + int(t[2], 16)
                        data["remaining_kwh"] = round(wh / 1000.0, 2)

                # --- TEMP ---
                #await send(sock, "ATFCSM0")
                res_t = await send(sock, "229131")
                #await send(sock, "ATFCSM1")
                if res_t and "62 91 31" in res_t:
                    t = res_t.split("62 91 31")[1].split()
                    if len(t) >= 2:
                        temp_raw = (int(t[0], 16) * 16) + (int(t[1], 16) >> 4)
                        data["battery_temp"] = temp_raw - 40

                # --- POWER ---
                if data["hv_voltage"] and data["current_amps"]:
                    pwr = (data["hv_voltage"] * data["current_amps"]) / 1000.0
                    data["battery_power"] = round(pwr * -1, 2)
                    _LOGGER.debug("Power: %.2fkW (HV=%.1fV, I=%.2fA)", data["battery_power"], data["hv_voltage"], data["current_amps"])

            else:
                _LOGGER.debug("Économie d'énergie: Tension 12V à %.1fV", voltage_12v)

        except Exception as e:
            _LOGGER.error("Erreur session Ariya: %s", e)
        finally:
            if sock: sock.close()

        return data
