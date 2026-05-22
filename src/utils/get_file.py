import asyncio
import asyncio
import logging
import os
from typing import Optional

from telegram import Bot, File
from telegram.error import NetworkError, TimedOut, TelegramError

from src.utils.env import env

from ..models import DownloadFile, downloading_files

logger = logging.getLogger(__name__)

# Retry constants
MAX_RETRIES = 5
INITIAL_RETRY_DELAY = 5
MAX_RETRY_DELAY = 60  # 最大重试延迟时间（秒）

# Environment variables
DOWNLOAD_TO_DIR = env.DOWNLOAD_TO_DIR


async def get_file(bot: Bot, file: DownloadFile) -> File:
    """
    Download a file from Telegram with enhanced retry logic.
    Args:
        bot (Bot): The bot instance used to download the file.
        file (DownloadFile): The download file object (containing file_id).
    Returns:
        File: The downloaded file object.
    Raises:
        Exception: If the maximum number of retries is reached/non network error occurs
        or file already exists.
    """
    last_exception = None
    
    for attempt in range(MAX_RETRIES):
        # Log attempt
        logger.info(f"Downloading file '{file.file_name}', attempt {attempt + 1}/{MAX_RETRIES}")
        file.download_retries = attempt

        # Check if file exists in directory already
        check_file_exists(file.file_id, file.file_name, check_downloading_files=False)

        try:
            new_file = await bot.get_file(file.file_id, read_timeout=1800)
            logger.info(f"File '{file.file_name}' downloaded successfully on attempt {attempt + 1}")
            return new_file
        except NetworkError as e:
            last_exception = e
            logger.error(f"Network error on attempt {attempt + 1}: {e}")
            file.last_error = f"Network error: {str(e)}"
            file.retry_history.append(f"Attempt {attempt + 1}: Network error - {str(e)}")
        except TimedOut as e:
            last_exception = e
            logger.error(f"Timeout error on attempt {attempt + 1}: {e}")
            file.last_error = f"Timeout error: {str(e)}"
            file.retry_history.append(f"Attempt {attempt + 1}: Timeout error - {str(e)}")
        except TelegramError as e:
            last_exception = e
            logger.error(f"Telegram error on attempt {attempt + 1}: {e}")
            file.last_error = f"Telegram error: {str(e)}"
            file.retry_history.append(f"Attempt {attempt + 1}: Telegram error - {str(e)}")
            # 对于某些Telegram错误，可能不需要重试
            if "file is too big" in str(e).lower():
                logger.error("File too big, not retrying")
                raise
        except Exception as e:
            last_exception = e
            logger.error(f"Unexpected error on attempt {attempt + 1}: {e}")
            file.last_error = f"Unexpected error: {str(e)}"
            file.retry_history.append(f"Attempt {attempt + 1}: Unexpected error - {str(e)}")
            # 对于非网络相关错误，可能不需要重试
            raise
        
        # 如果不是最后一次尝试，等待后重试
        if attempt < MAX_RETRIES - 1:
            # 使用指数退避策略，但设置最大延迟
            delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
            logger.info(f"Waiting {delay} seconds before retry...")
            await asyncio.sleep(delay)
    
    # 如果所有重试都失败，抛出最后一个异常
    raise Exception(f"Max retries ({MAX_RETRIES}) reached for file '{file.file_name}'. Last error: {last_exception}")


def check_file_exists(
    file_id: str, file_name: str, check_downloading_files: bool = True
) -> bool:
    """
    Check if a file exists in the download directory or is currently being downloaded.

    Args:
        file_id (str): The ID of the file to check.
        file_name (str): The name of the file to check.
        check_downloading_files (bool): Whether to check the downloading_files dictionary.

    Returns:
        bool: True if the file exists

    Raises:
        Exception: If the file already exists in the download directory or is being downloaded.
    """
    if os.path.exists(DOWNLOAD_TO_DIR + file_name):
        raise Exception("File already exists in downloads folder.")

    if check_downloading_files:
        if file_id in downloading_files:
            raise Exception("File is already being downloaded.")

        # Check file_name in downloading_files
        if any(file.file_name == file_name for file in downloading_files.values()):
            raise Exception("File is already being downloaded.")

    return True