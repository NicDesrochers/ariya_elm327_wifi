import logging
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import PERCENTAGE, UnitOfElectricPotential

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

def correct_soc(soc_bms: float) -> float:
    """Correction du SOC brut."""
    return soc_bms - 6 if soc_bms is not None else None

async def async_setup_entry(hass, entry, async_add_entities):
    """Ajoute les capteurs Ariya."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    async_add_entities(
        [
            AriyaSocRawSensor(coordinator, entry.entry_id),
            AriyaSocSensor(coordinator, entry.entry_id),
            AriyaElmVoltageSensor(coordinator, entry.entry_id),
            AriyaHvVoltageSensor(coordinator, entry.entry_id),
        ],
        True,
    )

class BaseAriyaSensor(CoordinatorEntity, SensorEntity):
    """Classe de base pour ajouter restore_state et device_info."""

    _attr_restore_state = True  # <-- conserve la valeur au reboot

    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self._entry_id = entry_id

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._entry_id)},
            "name": "Nissan Ariya",
            "manufacturer": "Nissan",
            "model": "Ariya ELM327 WiFi",
        }

class AriyaSocSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya SOC corrigé"
        self._attr_unique_id = f"{entry_id}_soc_corrige"
        self._attr_icon = "mdi:battery"
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        soc_bms = self.coordinator.data.get("soc_bms")
        return correct_soc(soc_bms)

class AriyaSocRawSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya SOC brut"
        self._attr_unique_id = f"{entry_id}_soc_raw"
        self._attr_icon = "mdi:battery"
        self._attr_native_unit_of_measurement = PERCENTAGE

    @property
    def native_value(self):
        return self.coordinator.data.get("soc_bms")

class AriyaElmVoltageSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "ELM327 Voltage"
        self._attr_unique_id = f"{entry_id}_elm327_voltage"
        self._attr_icon = "mdi:flash"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self):
        return self.coordinator.data.get("voltage_12v")

class AriyaHvVoltageSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "HV Battery Voltage"
        self._attr_unique_id = f"{entry_id}_hv_voltage"
        self._attr_icon = "mdi:car-electric"
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT

    @property
    def native_value(self):
        return self.coordinator.data.get("hv_voltage")
