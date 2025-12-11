from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities([AriyaForceRefreshButton(coordinator, entry.entry_id)], True)

class AriyaForceRefreshButton(CoordinatorEntity, ButtonEntity):
    def __init__(self, coordinator, entry_id):
        super().__init__(coordinator)
        self._attr_name = "Ariya Force Refresh"
        self._attr_unique_id = f"{entry_id}_force_refresh"
        self._attr_icon = "mdi:refresh"

    async def async_press(self):
        await self.coordinator.async_force_refresh()
