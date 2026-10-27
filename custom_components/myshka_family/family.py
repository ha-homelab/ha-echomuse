"""Bounded local Russian family activities; no network or device side effects.

Only complete supported requests are consumed. Named authors, unknown topics,
web searches and household commands stay with the normal agent. Original verse
is labelled. The caller controls the microphone; continue_conversation is a hint.
"""

from collections import OrderedDict
import math
import re
import time
from typing import NamedTuple

MAX_SPEECH_CHARS = 600


class FamilyReply(NamedTuple):
    speech: str
    continue_conversation: bool
    kind: str
    content_id: str
    provenance: str
    source_url: str = ""


class FamilyPiece(NamedTuple):
    """A reviewed piece; speech includes its attribution, if applicable."""

    content_id: str
    kind: str
    topic: str
    speech: str
    provenance: str = "original"
    source_url: str = ""


class Riddle(NamedTuple):
    content_id: str
    audience: str
    question: str
    answer: str
    accepted: tuple
    hint: str


PIECES = (
    FamilyPiece("bunny_stream", "poem", "bunny", "Вот наш собственный стишок о зайке.\n"
                "Зайка сел у ручейка,\nЛапкой трогал облака.\n"
                "Облака в воде качались,\nЗайке тихо улыбались."),
    FamilyPiece("bunny_sun", "poem", "bunny", "Ещё один наш стишок о зайке.\n"
                "По тропинке зайка скачет,\nВ рукавичке солнце прячет.\n"
                "Развернул её у кочки —\nЗасмеялись все цветочки."),
    FamilyPiece("cat_cloud", "poem", "cat", "Вот наш собственный стишок о котике.\n"
                "Котик облачко поймал,\nВ мягкий клубочек смотал.\n"
                "Уложил его в лукошко:\nПусть поспит ещё немножко."),
    FamilyPiece("rain_drum", "poem", "rain", "Вот наш собственный стишок о дождике.\n"
                "Дождь стучал по крыше: кап!\nКот боялся мокрых лап.\n"
                "Но увидел: у дорожки\nПьют цветы из каждой ложки."),
    FamilyPiece("sleep_boat", "poem", "sleep", "Вот наш собственный вечерний стишок.\n"
                "Спит кораблик у причала,\nНочь волну убаюкала.\n"
                "Спят и мачта, и канат,\nЗвёзды сон его хранят."),
    FamilyPiece("sun_window", "poem", "any", "Вот наш собственный короткий стишок.\n"
                "Солнце выглянуло к нам,\nПробежалось по домам.\n"
                "На ладошке луч уселся,\nУлыбнулся и согрелся."),
    FamilyPiece("bunny_fingers", "nursery", "bunny", "Вот наша собственная потешка про зайку.\n"
                "Два пальчика — два ушка,\nЛадошка — мягкая подушка.\n"
                "Зайка ушками качает,\nВсем привет передаёт.\n"
                "А теперь пускай немножко\nНа ладошке отдохнёт."),
    FamilyPiece("rain_fingers", "nursery", "rain", "Вот наша собственная потешка про дождик.\n"
                "Капля — пальчиком по ручке,\nКапля — радуга на тучке.\n"
                "Тихо пальчики стучат,\nПусть ладошки помолчат.\n"
                "Снова капли заплясали —\nВсе дождинки мы поймали!"),
    FamilyPiece("morning_hands", "nursery", "any", "Вот наша собственная потешка.\n"
                "Пальчик пальчику кивнул,\nЛуч в ладошку заглянул.\n"
                "Мы ладошки раскрываем,\nДобрый день всем посылаем!"),
)

RIDDLES = (
    Riddle("rabbit", "child", "Два длинных ушка над травой,\nПушистый хвостик за спиной.\n"
           "Морковка хрустит — кто спешит по дорожке?", "Зайка", ("зайка", "заяц", "зайчик", "кролик"),
           "Он умеет прыгать и быстро шевелит ушами."),
    Riddle("umbrella", "child", "Надо мной раскрылся круг,\nКапли барабанят вдруг.\n"
           "Под ним сухо и уютно. Что я держу?", "Зонт", ("зонт", "зонтик"),
           "Его берут с собой, когда обещают дождь."),
    Riddle("pencil", "child", "Я оставляю след на листе, но не хожу.\n"
           "Становлюсь короче, когда рисую. Кто я?", "Карандаш", ("карандаш", "карандашик"),
           "Меня точат, чтобы кончик снова стал острым."),
    Riddle("moon", "child", "Вечером в окне видна,\nТо кругла, то как струна.\n"
           "Светит мягко, не греет. Что это?", "Луна", ("луна", "месяц"),
           "Она — спутник Земли."),
    Riddle("battery_light", "adult", "В коробке три фонарика. Один сломан, а у двух других "
           "сели батарейки. Сколько фонариков находится в коробке?", "Три", ("3", "три", "три фонарика"),
           "Спросили, сколько фонариков лежит в коробке, а не сколько светит."),
    Riddle("calendar_day", "adult", "Позавчера была пятница. Какой день будет послезавтра?",
           "Вторник", ("вторник",), "Сначала определите сегодняшний день: после пятницы прошло два дня."),
)

_TOPICS = {
    "зайке": "bunny", "зайку": "bunny", "зайца": "bunny", "зайце": "bunny",
    "зайчике": "bunny", "зайчика": "bunny", "кролике": "bunny", "кролика": "bunny",
    "котике": "cat", "котика": "cat", "коте": "cat", "кота": "cat",
    "кошке": "cat", "кошку": "cat", "котенке": "cat", "котенка": "cat",
    "дождике": "rain", "дождик": "rain", "дожде": "rain", "дождь": "rain",
    "сне": "sleep", "сон": "sleep", "на ночь": "sleep",
}
_PIECE_REQUEST = re.compile(
    r"(?:(?:расскажи|прочитай|рассказывай|почитай|сочини|придумай) (?:мне |нам )?)?"
    r"(?:(?:короткий|короткую|детский|детскую|новый|новую|смешной|смешную) )?"
    r"(?P<kind>стишок|стих|стихотворение|потешку|потешка)"
    r"(?: (?:(?:о|об|про) (?P<topic>[а-я ]+)|(?P<sleep>на ночь)))?"
)
_RIDDLE_REQUEST = re.compile(
    r"(?:(?:загадай|расскажи|придумай|задавай) (?:мне |нам )?)?"
    r"(?:(?:новую|еще одну|детскую|интересную|сложную) )?загадк[ау]"
    r"(?: (?P<audience>для детей|для ребенка|для малышей|для взрослых|для взрослого|посложнее))?"
)
_CONTINUE = {"еще", "еще одну", "еще один", "следующая", "следующий", "давай еще", "другую", "другой"}
_HINT = {"подсказка", "дай подсказку", "подскажи", "помоги отгадать"}
_REVEAL = {"не знаю", "я не знаю", "сдаюсь", "ответ", "скажи ответ", "какой ответ", "расскажи ответ", "ответ на загадку"}
_STOP = {"хватит", "стоп", "закончим", "давай закончим", "не хочу больше"}
_NEW_REQUEST = re.compile(
    r"\b(?:включи|выключи|поставь|останови|открой|закрой|прибавь|убавь|расскажи|прочитай|"
    r"найди|поищи|спой|сыграй|играй|скажи|какая|какое|какие|какой|почему|зачем|сколько|где|когда)\b"
)


def _normalise(text):
    return re.sub(r"\s+", " ", re.sub(r"[^а-яa-z0-9 ]", " ", text.casefold().replace("ё", "е"))).strip()


def _request_text(text):
    text = _normalise(text)
    for prefix in ("мышка ", "пожалуйста "):
        if text.startswith(prefix):
            text = text[len(prefix):]
    if text.endswith(" пожалуйста"):
        text = text[:-11].strip()
    return text


class _Session:
    def __init__(self, now):
        self.touched = now
        self.last_kind = None
        self.last_topic = None
        self.original_only = False
        self.counts = {}
        self.riddle = None
        self.hint_given = False


class FamilySessionManager:
    """TTL/LRU dialogue state, isolated by caller-supplied conversation key.

    Extra pieces precede bundled pieces for the same category/topic. Use these
    for independently verified licensed or public-domain readings. No network
    fetch, microphone activation or household action happens here.
    """

    def __init__(self, *, ttl_seconds=600, max_sessions=128, extra_pieces=(), clock=time.monotonic):
        if not isinstance(max_sessions, int) or isinstance(max_sessions, bool) or not 1 <= max_sessions <= 1024:
            raise ValueError("max_sessions must be between 1 and 1024")
        if not isinstance(ttl_seconds, (int, float)) or isinstance(ttl_seconds, bool) or not math.isfinite(ttl_seconds) or not 1 <= ttl_seconds <= 3600:
            raise ValueError("ttl_seconds must be between 1 and 3600")
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.clock = clock
        self.sessions = OrderedDict()
        self.pieces = tuple(extra_pieces) + PIECES
        seen = set()
        for piece in self.pieces:
            if (piece.content_id in seen or not piece.content_id or piece.kind not in {"poem", "nursery"}
                    or piece.topic not in {"any", "bunny", "cat", "rain", "sleep"}
                    or not 1 <= len(piece.speech) <= MAX_SPEECH_CHARS
                    or piece.provenance not in {"original", "public_domain", "licensed"}
                    or (piece.provenance != "original" and not piece.source_url.startswith("https://"))):
                raise ValueError("Invalid or duplicate family catalogue piece")
            seen.add(piece.content_id)

    def _session(self, conversation_id, now):
        for key in list(self.sessions):
            if now - self.sessions[key].touched >= self.ttl_seconds:
                del self.sessions[key]
        return self.sessions.get(conversation_id)

    def _remember(self, conversation_id, session, now):
        session.touched = now
        self.sessions[conversation_id] = session
        self.sessions.move_to_end(conversation_id)
        while len(self.sessions) > self.max_sessions:
            self.sessions.popitem(last=False)

    def _piece(self, session, kind, topic, original_only=False):
        options = [p for p in self.pieces if p.kind == kind and p.topic == topic
                   and (not original_only or p.provenance == "original")]
        if not options:
            return None
        key = (kind, topic, original_only)
        count = session.counts.get(key, 0)
        piece = options[count % len(options)]
        session.counts[key] = count + 1
        session.last_kind, session.last_topic = kind, topic
        session.original_only = original_only
        session.riddle = None
        return FamilyReply(piece.speech, False, kind, piece.content_id, piece.provenance, piece.source_url)

    def _riddle(self, session, audience):
        options = [r for r in RIDDLES if r.audience == audience]
        key = ("riddle", audience)
        count = session.counts.get(key, 0)
        riddle = options[count % len(options)]
        session.counts[key] = count + 1
        session.last_kind, session.last_topic = "riddle", audience
        session.riddle, session.hint_given = riddle, False
        return FamilyReply("Вот наша загадка. " + riddle.question + " Отвечайте: «Мой ответ…». Для подсказки скажите: «Подсказка к загадке».", True, "riddle", riddle.content_id, "original")

    def continue_activity(self, kind, *, conversation_id, language="ru"):
        session = self._session(conversation_id, self.clock())
        if session and session.last_kind == kind:
            return self.respond("ещё", conversation_id=conversation_id, language=language)
        request = {"riddle": "загадка", "nursery": "потешка", "poem": "стишок"}.get(kind)
        return self.respond(request, conversation_id=conversation_id, language=language) if request else None

    def respond(self, text, *, conversation_id, language="ru", now=None):
        """Return a response for a complete supported utterance, else None."""
        if (not isinstance(text, str) or not 1 <= len(text) <= 500
                or not isinstance(conversation_id, str) or not 1 <= len(conversation_id) <= 256
                or not isinstance(language, str) or language.lower().split("-")[0] != "ru"):
            return None
        now = self.clock() if now is None else now
        if not isinstance(now, (int, float)) or isinstance(now, bool) or not math.isfinite(now):
            raise ValueError("now must be a finite monotonic timestamp")
        request = _request_text(text)
        session = self._session(conversation_id, now)
        match = _PIECE_REQUEST.fullmatch(request)
        if match:
            kind = "nursery" if match["kind"].startswith("потеш") else "poem"
            topic_text = match["topic"] or match["sleep"]
            topic = _TOPICS.get(topic_text) if topic_text else "any"
            if topic is None:
                return None
            session = session or _Session(now)
            result = self._piece(session, kind, topic, request.startswith(("сочини ", "придумай ")))
            if result:
                self._remember(conversation_id, session, now)
            return result
        match = _RIDDLE_REQUEST.fullmatch(request)
        if match:
            audience = "adult" if match["audience"] in {"для взрослых", "для взрослого", "посложнее"} or "сложную" in request else "child"
            session = session or _Session(now)
            result = self._riddle(session, audience)
            self._remember(conversation_id, session, now)
            return result
        if session is None:
            return None
        if request in _STOP:
            del self.sessions[conversation_id]
            return FamilyReply("Хорошо, закончили.", False, "stop", "", "dialogue")
        if request in _CONTINUE and session.last_kind:
            result = (self._riddle(session, session.last_topic) if session.last_kind == "riddle"
                      else self._piece(session, session.last_kind, session.last_topic, session.original_only))
            self._remember(conversation_id, session, now)
            return result
        riddle = session.riddle
        if riddle is None:
            return None
        if request in _HINT:
            session.hint_given = True
            result = FamilyReply("Подсказка: " + riddle.hint, True, "hint", riddle.content_id, "dialogue")
        elif request in _REVEAL:
            session.riddle = None
            result = FamilyReply("Ответ: " + riddle.answer + ".", False, "answer", riddle.content_id, "dialogue")
        else:
            answer = re.sub(r"^(?:(?:это|наверное|кажется|думаю|я думаю|может быть|мой ответ) )+", "", request)
            if answer in riddle.accepted:
                session.riddle = None
                result = FamilyReply("Верно! Это " + riddle.answer.lower() + ".", False, "correct", riddle.content_id, "dialogue")
            elif not request or "?" in text or len(request.split()) > 7 or _NEW_REQUEST.search(request):
                return None
            else:
                speech = "Пока не угадали. "
                if session.hint_given:
                    speech += "Можно попробовать ещё или сказать: «Ответ на загадку»."
                else:
                    session.hint_given = True
                    speech += "Подсказка: " + riddle.hint
                result = FamilyReply(speech, True, "try_again", riddle.content_id, "dialogue")
        self._remember(conversation_id, session, now)
        return result
