import json
import logging
from pathlib import Path
from typing import Any

from .runtime_settings import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, runtime_settings_store

logger = logging.getLogger(__name__)

_LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"
_translations: dict[str, dict[str, str]] = {}


def normalize_language(language: str | None) -> str:
    if not isinstance(language, str):
        return DEFAULT_LANGUAGE
    normalized = language.strip().replace("_", "-")
    lowered = normalized.lower()
    if lowered in {"zh", "zh-cn", "zh-hans", "chinese", "cn"}:
        return "zh-CN"
    if lowered in {"en", "en-us", "en-gb", "english"}:
        return "en"
    return normalized if normalized in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def parse_supported_language(language: str | None) -> str | None:
    if not isinstance(language, str):
        return None
    normalized = language.strip().replace("_", "-")
    lowered = normalized.lower()
    if lowered in {"zh", "zh-cn", "zh-hans", "chinese", "cn"}:
        return "zh-CN"
    if lowered in {"en", "en-us", "en-gb", "english"}:
        return "en"
    return normalized if normalized in SUPPORTED_LANGUAGES else None


def available_languages() -> tuple[str, ...]:
    return tuple(sorted(SUPPORTED_LANGUAGES))


def get_language() -> str:
    return normalize_language(runtime_settings_store.settings.language)


def _load_language(language: str) -> dict[str, str]:
    language = normalize_language(language)
    if language in _translations:
        return _translations[language]

    path = _LOCALES_DIR / f"{language}.json"
    try:
        with open(path, encoding="utf-8") as locale_file:
            payload = json.load(locale_file)
    except (OSError, json.JSONDecodeError) as error:
        logger.warning("Failed to load locale %s from %s: %s", language, path, error)
        payload = {}

    if not isinstance(payload, dict):
        payload = {}
    _translations[language] = {str(key): str(value) for key, value in payload.items()}
    return _translations[language]


def t(key: str, **kwargs: Any) -> str:
    language = get_language()
    text = _load_language(language).get(key)
    if text is None and language != DEFAULT_LANGUAGE:
        text = _load_language(DEFAULT_LANGUAGE).get(key)
    if text is None:
        text = key
    text = text.replace("\\n", "\n")
    if not kwargs:
        return text
    return text.format(**kwargs)
