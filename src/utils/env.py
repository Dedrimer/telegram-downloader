import logging

from dotenv import load_dotenv
from pydantic import ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )
    BOT_TOKEN: str
    LOCAL_BOT_API_URL: str
    BOT_API_DIR: str
    DOWNLOAD_TO_DIR: str
    USER_ID: str
    CHAT_ID: str
    APP_SETTINGS_FILE: str = "./data/settings.json"
    SINGLE_FILE_GROUP_ENABLED: bool = False
    SINGLE_FILE_GROUP_DELAY: float = 1.0
    DOWNLOAD_STATUS_UPDATE_INTERVAL: float = 5.0
    DOWNLOAD_PROGRESS_POLL_INTERVAL: float = 1.0
    ADMIN_PROGRESS_POLL_INTERVAL: float = 0.5
    MAX_CONCURRENT_DOWNLOADS: int = 1
    ADMIN_API_ENABLED: bool = False
    ADMIN_API_HOST: str = "0.0.0.0"
    ADMIN_API_PORT: int = 8088
    ADMIN_API_TOKEN: str = ""


logger.info("Loading environment variables")

try:
    env = Settings()
except ValidationError as e:
    logger.error("Environment variables validation error: %s", e)
    exit(1)
