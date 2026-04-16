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
            AriyaBatteryPowerSensor(coordinator, entry.entry_id),
            AriyaBatteryTempSensor(coordinator, entry.entry_id),
            AriyaRemainingEnergySensor(coordinator, entry.entry_id),
            AriyaBatteryAmpsSensor(coordinator, entry.entry_id),
            AriyaCurrentSensor(coordinator, entry.entry_id),
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
class AriyaBatteryPowerSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya Battery Power"
        self._attr_unique_id = f"{entry_id}_battery_power"
        self._attr_icon = "mdi:lightning-bolt"
        self._attr_native_unit_of_measurement = "kW"
        self._attr_device_class = "power"

    @property
    def native_value(self):
        return self.coordinator.data.get("battery_power")

class AriyaBatteryTempSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya Battery Temperature"
        self._attr_unique_id = f"{entry_id}_battery_temp"
        self._attr_icon = "mdi:thermometer"
        self._attr_native_unit_of_measurement = "°C"
        self._attr_device_class = "temperature"

    @property
    def native_value(self):
        return self.coordinator.data.get("battery_temp")

class AriyaRemainingEnergySensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya Remaining Energy"
        self._attr_unique_id = f"{entry_id}_remaining_kwh"
        self._attr_icon = "mdi:gauge"
        self._attr_native_unit_of_measurement = "kWh"

    @property
    def native_value(self):
        return self.coordinator.data.get("remaining_kwh")

class AriyaBatteryAmpsSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya Battery Amps"
        self._attr_unique_id = f"{entry_id}_battery_amps"
        self._attr_icon = "mdi:current-ac"
        self._attr_native_unit_of_measurement = "A"

    @property
    def native_value(self):
        return self.coordinator.data.get("battery_amps")

class AriyaCurrentSensor(BaseAriyaSensor):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator, entry_id)
        self._attr_name = "Ariya Battery Current"
        self._attr_unique_id = f"{entry_id}_battery_current"
        self._attr_icon = "mdi:current-ac"
        self._attr_native_unit_of_measurement = "A"

    @property
    def native_value(self):
        return self.coordinator.data.get("current_amps")