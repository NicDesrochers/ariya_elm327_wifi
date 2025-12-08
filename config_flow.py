import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

DOMAIN = "ariya_elm327_wifi"

class AriyaElm327ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Flux de configuration principal pour Ariya ELM327 WiFi."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="Ariya ELM327 WiFi", data=user_input)

        data_schema = vol.Schema({
            vol.Required("elm_ip"): str,
            vol.Required("elm_port", default=35000): int,
        })

        return self.async_show_form(step_id="user", data_schema=data_schema)


class AriyaElm327OptionsFlowHandler(config_entries.OptionsFlow):
    """Gestion des options pour Ariya ELM327 WiFi."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options_schema = vol.Schema({
            vol.Optional(
                "scan_interval_minutes",
                default=self.config_entry.options.get("scan_interval_minutes", 10)
            ): int,
        })

        return self.async_show_form(step_id="init", data_schema=options_schema)


@callback
def configured_instances(hass):
    """Retourne les instances déjà configurées."""
    return set(entry.data["elm_ip"] for entry in hass.config_entries.async_entries(DOMAIN))
