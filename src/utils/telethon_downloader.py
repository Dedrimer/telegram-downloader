import asyncio
import logging
import os

from telethon import TelegramClient, utils
from telethon.sessions import MemorySession

from .env import env

logger = logging.getLogger(__name__)

_client: TelegramClient | None = None
_client_lock = asyncio.Lock()


def is_configured() -> bool:
    return bool(env.TELEGRAM_API_ID and env.TELEGRAM_API_HASH)


async def _get_client() -> TelegramClient:
    global _client

    if not is_configured():
        raise RuntimeError("TELEGRAM_API_ID and TELEGRAM_API_HASH are required for cancellable downloads.")

    async with _client_lock:
        if _client is None:
            _client = TelegramClient(
                MemorySession(),
                env.TELEGRAM_API_ID,
                env.TELEGRAM_API_HASH,
            )

        if not _client.is_connected():
            await _client.connect()

        if not await _client.is_user_authorized():
            await _client.start(bot_token=env.BOT_TOKEN)

        return _client


async def download_bot_file_id(file_id: str, file_size: int, target_path: str) -> str:
    """
    Download a Bot API file_id via MTProto.

    This keeps the actual file transfer in the bot process instead of delegating it to the
    local Bot API server. Cancelling the asyncio task therefore stops the transfer itself.
    """
    media = utils.resolve_bot_file_id(file_id)
    if media is None:
        raise RuntimeError("Unable to resolve Telegram Bot API file_id for cancellable download.")

    media.size = file_size
    client = await _get_client()

    os.makedirs(os.path.dirname(target_path) or ".", exist_ok=True)
    await client.download_media(media, file=target_path)
    logger.info("Cancellable download completed: %s", target_path)
    return target_path


async def download_message_media(
    chat_id: int,
    message_id: int,
    file_id: str,
    file_size: int,
    target_path: str,
) -> str:
    client = await _get_client()

    try:
        message = await client.get_messages(chat_id, ids=message_id)
        if message and message.media:
            await client.download_media(message, file=target_path)
            logger.info("Cancellable message media download completed: %s", target_path)
            return target_path
    except asyncio.CancelledError:
        raise
    except Exception as e:
        logger.warning(
            "Failed to download by message reference, falling back to file_id: %s",
            e,
        )

    return await download_bot_file_id(file_id, file_size, target_path)
