import asyncio
import json
import logging
import os
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

APP_VERSION = "0.2.1"
BOT_API_VERSION = "10.1.0"
BOT_API_VERSION_METHOD = "getBotApiVersion"
BOT_API_VERSION_TIMEOUT = 3.0

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeInfo:
    downloader_version: str
    bot_api_version: str
    bot_api_version_source: str


def get_downloader_version() -> str:
    return (
        os.getenv("TELEGRAM_DOWNLOADER_VERSION")
        or _get_installed_downloader_version()
        or APP_VERSION
    )


def get_configured_bot_api_version() -> str:
    return os.getenv("TELEGRAM_BOT_API_VERSION") or BOT_API_VERSION


async def get_runtime_info() -> RuntimeInfo:
    bot_api_version = await get_bot_api_version()
    return RuntimeInfo(
        downloader_version=get_downloader_version(),
        bot_api_version=bot_api_version[0],
        bot_api_version_source=bot_api_version[1],
    )


async def get_bot_api_version() -> tuple[str, str]:
    try:
        reported_version = await asyncio.to_thread(_request_bot_api_version_sync)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
        logger.info("Failed to fetch Bot API version: %s", exc)
        reported_version = None

    if reported_version:
        return reported_version, "api"

    return get_configured_bot_api_version(), "configured"


def _get_installed_downloader_version() -> str | None:
    try:
        return package_version("telegram-downloader")
    except PackageNotFoundError:
        return None


def _request_bot_api_version_sync() -> str | None:
    from .utils.env import env

    url = (
        f"{env.LOCAL_BOT_API_URL.rstrip('/')}/bot"
        f"{env.BOT_TOKEN}/{BOT_API_VERSION_METHOD}"
    )
    request = Request(url, method="POST")
    with urlopen(request, timeout=BOT_API_VERSION_TIMEOUT) as response:
        payload = json.loads(response.read().decode("utf-8"))

    if not payload.get("ok"):
        return None

    result = payload.get("result")
    if isinstance(result, dict):
        version = result.get("version")
    elif isinstance(result, str):
        version = result
    else:
        version = None

    if isinstance(version, str) and version.strip():
        return version.strip()
    return None
