import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import DOMAIN, PLATFORMS
from .coordinator import SocCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Ariya ELM327 WiFi from a config entry."""
    _LOGGER.debug("Setting up integration %s (entry_id=%s)", DOMAIN, entry.entry_id)

    coordinator = SocCoordinator(entry.data, hass)
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"coordinator": coordinator}

    # 🔑 Premier refresh obligatoire pour initialiser coordinator.data
    await coordinator.async_config_entry_first_refresh()

    # Charger les plateformes (sensor, button, etc.)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Ariya ELM327 WiFi config entry."""
    _LOGGER.debug("Unloading integration %s (entry_id=%s)", DOMAIN, entry.entry_id)

    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded

async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle migration if needed (e.g., add default options)."""
    _LOGGER.debug("Migrating config entry for %s (version=%s)", DOMAIN, entry.version)

    if entry.version == 1:
        new_options = {**entry.options}
        if "scan_interval_minutes" not in new_options:
            new_options["scan_interval_minutes"] = 10
            _LOGGER.info("Added default scan_interval_minutes=10 during migration")
        hass.config_entries.async_update_entry(entry, options=new_options, version=2)

    return True
