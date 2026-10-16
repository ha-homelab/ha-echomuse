"""Bounded language selection for the home-tools prompt.

Keep instructions static: an HA language value must never become prompt text.
This chooses the answer language, not a speech recognizer or a TTS voice.
"""

import re
from types import MappingProxyType

DEFAULT_LANGUAGE = "ru"
LANGUAGE_INSTRUCTIONS = MappingProxyType({
    "en": "Answer briefly in English.",
    "ru": "Answer briefly in Russian.",
    "de": "Answer briefly in German.",
    "es": "Answer briefly in Spanish.",
    "fr": "Answer briefly in French.",
})

# Accept common HA language tags, including language/script/region variants.
# Encoding suffixes, free text and private-use extensions are not supported.
_LANGUAGE_TAG = re.compile(r"[a-z]{2,3}(?:[-_][a-z]{4})?(?:[-_](?:[a-z]{2}|[0-9]{3}))?", re.ASCII | re.IGNORECASE)


def resolve_language(language: object) -> str:
    """Return a supported base language, preserving the Russian default."""
    if not isinstance(language, str) or len(language) > 20:
        return DEFAULT_LANGUAGE
    tag = language.strip()
    if not _LANGUAGE_TAG.fullmatch(tag):
        return DEFAULT_LANGUAGE
    base = tag.replace("_", "-").split("-", 1)[0].lower()
    return base if base in LANGUAGE_INSTRUCTIONS else DEFAULT_LANGUAGE


def answer_instruction(language: object) -> str:
    """Return only trusted catalog text for an untrusted locale value."""
    return LANGUAGE_INSTRUCTIONS[resolve_language(language)]
