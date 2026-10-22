"""Register a private speech service and validate TLS before storing credentials."""
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from . import DOMAIN
from .client import Client, SettingsError, AuthenticationError, connection_options


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                options = await self.hass.async_add_executor_job(connection_options, user_input)
                await Client(async_get_clientsession(self.hass), options).request()
                await self.async_set_unique_id(options[0])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(title='Local Russian Speech', data=dict(user_input, endpoint=options[0]))
            except AuthenticationError:
                errors['base'] = 'invalid_auth'
            except (SettingsError, OSError, ValueError):
                errors['base'] = 'cannot_connect'
        return self.async_show_form(step_id='user', errors=errors, data_schema=vol.Schema({
            vol.Required('endpoint'): str,
            vol.Required('token'): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required('ca_file'): str,
        }))

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = dict(entry.data, **user_input)
            try:
                options = await self.hass.async_add_executor_job(connection_options, data)
                await Client(async_get_clientsession(self.hass), options).request()
                return self.async_update_reload_and_abort(entry, data_updates=data)
            except AuthenticationError:
                errors['base'] = 'invalid_auth'
            except (SettingsError, OSError, ValueError):
                errors['base'] = 'cannot_connect'
        return self.async_show_form(step_id='reauth_confirm', errors=errors, data_schema=vol.Schema({
            vol.Required('token'): selector.TextSelector(selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }))
