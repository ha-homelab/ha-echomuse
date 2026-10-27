"""Local family activities alongside the existing Home Assistant agent."""

import json
from pathlib import Path

import probatio as vol
from homeassistant.helpers import config_validation as cv

from .family import FamilySessionManager
from .creative_contract import validate_api_key
from .service import FamilyService, validate_local_origin, validate_public_uri

DOMAIN = "myshka_family"

CONFIG_SCHEMA = vol.Schema({
    vol.Optional(DOMAIN): vol.Schema({
        vol.Optional("ollama_url"): validate_local_origin,
        vol.Optional("ollama_api_key"): validate_api_key,
        vol.Optional("public_creative_uri"): validate_public_uri,
        vol.Optional("model", default="qwen3:4b-instruct"): cv.string,
        vol.Optional("music_players", default={}): {cv.string: cv.entity_id},
        vol.Optional("music_config_entry_id"): cv.string,
    }),
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Load a reviewed local catalogue; do not change the current voice pipeline."""
    settings = config[DOMAIN]
    library = await hass.async_add_executor_job(
        lambda: json.loads(Path(__file__).with_name("library.json").read_text())
    )
    hass.data[DOMAIN] = FamilyService(hass, settings, FamilySessionManager(), library)
    return True
