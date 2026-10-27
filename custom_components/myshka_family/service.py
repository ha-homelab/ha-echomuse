"""Family content with local defaults and an opt-in public-topic relay."""
import asyncio
import hashlib
import ipaddress
import json
import re
from urllib.parse import urlsplit

import aiohttp
from wyoming.asr import Transcript
from wyoming.client import AsyncClient
from wyoming.handle import Handled
from .public_topics import public_prompt
from .creative_contract import CREATIVE_OPTIONS, creative_messages
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

CREATIVE_TIMEOUT_SECONDS = 25
MUSIC_TIMEOUT_SECONDS = 15

def normalise(text):
    return re.sub(r"\s+", " ", re.sub(r"[^а-яa-z0-9 ]", " ", text.casefold().replace("ё", "е"))).strip()


def validate_local_origin(value):
    if not isinstance(value, str):
        raise ValueError("A local Ollama origin is required")
    url = urlsplit(value)
    host = url.hostname or ""
    try:
        ip = ipaddress.ip_address(host)
        local = ip.is_private and not ip.is_unspecified and not ip.is_multicast
    except ValueError:
        local = host.endswith(".svc.cluster.local") or host == "localhost"
    if (url.scheme not in {"http", "https"} or not local or url.username or url.password
            or url.path not in {"", "/"} or url.query or url.fragment):
        raise ValueError("Use a private IP or Kubernetes service origin without credentials or path")
    return value.rstrip("/")


def validate_public_uri(value):
    if not isinstance(value, str) or not value.startswith("tcp://"):
        raise ValueError("Use an explicitly audited local stateless Wyoming bridge")
    validate_local_origin("http://" + value[6:])
    return value


def session_key(intent):
    # Native intents have no conversation ID; do not share browser sessions.
    source = intent.satellite_id or intent.device_id
    if not source:
        return None
    return hashlib.sha256(f"{source}:{intent.context.user_id or ''}".encode()).hexdigest()


def bounded_output(text):
    if not isinstance(text, str):
        raise ValueError("Missing creative text")
    text = text.strip()
    if (not text or len(text) > 1200 or "<" in text or ">" in text
            or not re.search("[А-Яа-я]", text)
            or re.search(r"https?://|\b(?:tool_calls|function_call)\b", text)):
        raise ValueError("Invalid creative text")
    return text


class FamilyService:
    def __init__(self, hass, settings, manager, library):
        self.hass, self.settings, self.manager = hass, settings, manager
        self.entries = library["entries"]
        self.generating = False
        for entry in self.entries:
            if hashlib.sha256(entry["text"].encode()).hexdigest() != entry["sha256"]:
                raise ValueError("Family library checksum mismatch")

    def lookup(self, query, *, thematic=False):
        query = re.sub(r" (?:пожалуйста|с выражением)$", "", normalise(query))
        for entry in self.entries:
            authors = [entry["author"], *entry.get("author_aliases", [])]
            titles = [entry["title"], *entry.get("title_aliases", [])]
            candidates = [*authors, *titles]
            candidates.extend(f"{a} {t}" for a in authors for t in titles)
            candidates.extend(f"{t} {a}" for a in authors for t in titles)
            if thematic:
                candidates.extend(entry.get("topics", []))
            if query in {normalise(s) for s in candidates}:
                return entry
        return None

    async def read(self, query, *, thematic=False):
        entry = self.lookup(query, thematic=thematic)
        if entry:
            return (f'{entry["author"]}. «{entry["title"]}».\n{entry["text"]}', entry["source"]["url"])
        if thematic:
            return await self.create("стих", query), ""
        return ("В моей проверенной библиотеке пока нет этого произведения. "
                "Могу прочитать «Зайчика» Блока или сочинить новый стишок на вашу тему.", "")

    async def create(self, kind, topic):
        if kind not in {"стих", "сказка", "потешка"} or not isinstance(topic, str) or not 1 <= len(topic) <= 180:
            return "Назовите короткую тему для стишка или сказки."
        if self.generating:
            return "Я ещё заканчиваю предыдущую сказку. Попробуйте через несколько секунд."
        public_uri = self.settings.get("public_creative_uri")
        if public_uri:
            prompt = public_prompt(kind, topic)
            if prompt is None:
                return "Для новой истории назовите общую тему без имён: например, зайчик, робот и кот или дружба."
            self.generating = True
            try:
                async with asyncio.timeout(CREATIVE_TIMEOUT_SECONDS):
                    async with AsyncClient.from_uri(public_uri) as client:
                        await client.write_event(Transcript(text=prompt).event())
                        event = await client.read_event()
                if event is None or not Handled.is_type(event.type):
                    raise ValueError("Creative service did not return text")
                text = bounded_output(Handled.from_event(event).text)
                return "Вот моя новая " + {"стих": "рифмовка", "сказка": "сказка", "потешка": "потешка"}[kind] + ".\n" + text
            except (OSError, TimeoutError, ValueError, KeyError, TypeError):
                return "Сейчас не удалось сочинить новую историю. Могу прочитать готовый стих или загадать загадку."
            finally:
                self.generating = False
        origin = self.settings.get("ollama_url")
        if not origin:
            return "Сочинение новых историй пока не настроено. Могу прочитать стих или загадать загадку."
        self.generating = True
        try:
            session = async_get_clientsession(self.hass)
            payload = {
                "model": self.settings["model"], "stream": False, "think": False, "keep_alive": -1,
                "messages": creative_messages(kind, topic),
                "options": dict(CREATIVE_OPTIONS),
            }
            api_key = self.settings.get("ollama_api_key")
            headers = {"Authorization": "Bearer " + api_key} if api_key else {}
            # Bound the complete operation as well as aiohttp's transport. A
            # stalled response body must release the shared generation slot.
            async with asyncio.timeout(CREATIVE_TIMEOUT_SECONDS):
                async with session.post(origin + "/api/chat", json=payload,
                                        timeout=aiohttp.ClientTimeout(total=CREATIVE_TIMEOUT_SECONDS),
                                        allow_redirects=False, headers=headers) as response:
                    if response.status != 200:
                        raise ValueError("Local generation unavailable")
                    try:
                        await response.content.readexactly(32769)
                    except asyncio.IncompleteReadError as end:
                        raw = end.partial
                    else:
                        raise ValueError("Oversized local response")
                    result = json.loads(raw)
            if (not isinstance(result, dict) or not result.get("done")
                    or result.get("done_reason") == "length"
                    or not isinstance(result.get("message"), dict)
                    or result["message"].get("tool_calls")):
                raise ValueError("Incomplete creative response")
            text = bounded_output(result["message"]["content"])
            return "Вот моя новая " + {"стих": "рифмовка", "сказка": "сказка", "потешка": "потешка"}[kind] + ".\n" + text
        except (aiohttp.ClientError, TimeoutError, ValueError, KeyError, TypeError):
            return ("Сейчас не успеваю сочинить новую историю. "
                    "Попросите прочитать «Зайчика» Блока или загадать загадку — они уже готовы.")
        finally:
            self.generating = False

    async def song(self, title, intent):
        if not title:
            return "Какую песенку включить? Скажите «Включи песню» и её название."
        source = intent.satellite_id or intent.device_id
        target = self.settings["music_players"].get(source)
        if not target:
            return "Для этой колонки пока не настроен музыкальный проигрыватель."
        state = self.hass.states.get(target)
        if state is None or state.state in {"unknown", "unavailable"}:
            return "Музыкальный проигрыватель этой колонки сейчас недоступен."
        if intent.context.user_id:
            user = await self.hass.auth.async_get_user(intent.context.user_id)
            if user is None or not user.permissions.check_entity(target, POLICY_CONTROL):
                return "У вас нет разрешения управлять этим проигрывателем."
        play_requested = False
        try:
            # One total budget covers lookup and dispatch, with no retry. A
            # timed-out play call may already have reached the player.
            async with asyncio.timeout(MUSIC_TIMEOUT_SECONDS):
                result = await self.hass.services.async_call("music_assistant", "search", {
                    "name": title, "media_type": ["track"], "limit": 5, "library_only": True,
                    **({"config_entry_id": self.settings["music_config_entry_id"]}
                       if self.settings.get("music_config_entry_id") else {}),
                }, blocking=True, return_response=True, context=intent.context)
                if not isinstance(result, dict) or not isinstance(result.get("tracks"), list):
                    raise ValueError("Malformed library result")
                tracks = result["tracks"]
                if any(not isinstance(row, dict) or not isinstance(row.get("name"), str) for row in tracks):
                    raise ValueError("Malformed track")
                matches = [row for row in tracks if normalise(row["name"]) == normalise(title)]
                if len(matches) != 1:
                    return "Не нашла единственную песню с таким названием в вашей библиотеке. Уточните название."
                row = matches[0]
                uri = row.get("uri", "")
                if not isinstance(uri, str) or not re.fullmatch(r"library://track/[0-9]+", uri):
                    return "Эта песня пока недоступна в локальной музыкальной библиотеке."
                play_requested = True
                await self.hass.services.async_call("music_assistant", "play_media", {
                    "entity_id": target, "media_id": uri, "media_type": "track", "enqueue": "replace",
                }, blocking=True, context=intent.context)
                return f'Отправила песню «{row["name"]}» на эту колонку.'
        except TimeoutError:
            if play_requested:
                return "Не дождалась подтверждения от проигрывателя. Музыка ещё может начать играть."
            return "Поиск песни занял слишком много времени. Воспроизведение не запускала."
        except (HomeAssistantError, ValueError, KeyError, TypeError):
            return "Не удалось включить песенку. Попробуйте чуть позже."
