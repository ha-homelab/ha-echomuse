"""Fast read-only state questions, even when a control-capable LLM is selected."""

from homeassistant.auth.permissions.const import POLICY_READ
from homeassistant.components.intent import GetStateIntentHandler
from homeassistant.helpers import intent

from .policy import READ_DOMAINS


class HomeStateIntent(GetStateIntentHandler):
    """Reuse HA target matching and exposure checks without a model round trip.

    HA excludes HassGetState from prefer-local handling for control-capable LLMs.
    A distinct custom intent keeps explicit state questions on the native path.
    Responses are defined in the accompanying per-language sentence files.
    """

    intent_type = "EchoMuseGetState"

    async def async_handle(self, intent_obj):
        response = await super().async_handle(intent_obj)
        states = [*response.matched_states, *response.unmatched_states]
        user = None
        if intent_obj.context.user_id:
            user = await intent_obj.hass.auth.async_get_user(intent_obj.context.user_id)
            if user is None:
                raise intent.IntentHandleError("Entity permission denied")
        for state in states:
            if state.domain not in READ_DOMAINS or (
                user and not user.permissions.check_entity(state.entity_id, POLICY_READ)
            ):
                raise intent.IntentHandleError("Entity permission denied")
        return response


async def async_setup_intents(hass):
    """Register through HA's intent platform discovery."""
    intent.async_register(hass, HomeStateIntent())
