"""Narrow native intents; the existing local household agent remains unchanged."""
import re
import uuid

from homeassistant.helpers import intent
from .service import session_key

DOMAIN = "myshka_family"


class FamilyIntent(intent.IntentHandler):
    def __init__(self, intent_type):
        self.intent_type = intent_type

    async def async_handle(self, request):
        service = request.hass.data[DOMAIN]
        slots = {k: v["value"] for k, v in request.slots.items()}
        subject = str(slots.get("subject", ""))
        response = request.create_response()
        response.response_type = intent.IntentResponseType.QUERY_ANSWER
        source = ""
        if len(subject) > 180 or re.search(r"\b(включи|выключи|удали|открой|закрой|останови)\b", subject.lower()):
            speech = "Попросите об истории и об управлении устройствами отдельными командами."
        elif self.intent_type == "MyshkaRead":
            speech, source = await service.read(subject or "зайке", thematic=bool(slots.get("thematic", False)))
        elif self.intent_type == "MyshkaCreate":
            speech = await service.create(str(slots.get("kind", "стих")), subject or "дружба")
        elif self.intent_type == "MyshkaSong":
            speech = await service.song(subject, request)
        else:
            text = request.text_input or str(slots.get("request", ""))
            if "request" in slots:
                text = str(slots["request"])
            if slots.get("prepared"):
                text = "стишок" + (" о " + subject if subject else "")
            key = session_key(request)
            if self.intent_type == "MyshkaRiddleReply" and key is None:
                speech = "Отвечайте на загадку с той же колонки, на которой её услышали."
            else:
                identity = key or uuid.uuid4().hex
                if slots.get("continue_kind"):
                    reply = service.manager.continue_activity(slots["continue_kind"], conversation_id=identity)
                else:
                    reply = service.manager.respond(text, conversation_id=identity)
                if reply:
                    speech, source = reply.speech, reply.source_url
                else:
                    speech = "Сначала скажите: «Загадай загадку» или «Расскажи потешку»."
        response.async_set_speech(speech)
        if source:
            response.async_set_card("Источник стихотворения", source)
        return response


async def async_setup_intents(hass):
    for name in ("MyshkaRead", "MyshkaCreate", "MyshkaActivity", "MyshkaRiddleReply", "MyshkaSong"):
        intent.async_register(hass, FamilyIntent(name))
