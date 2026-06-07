import json
import logging
import os
from dataclasses import asdict, dataclass
from typing import Any

from .env import env

logger = logging.getLogger(__name__)

SINGLE_FILE_GROUP_DELAY_MIN = 0.1
SINGLE_FILE_GROUP_DELAY_MAX = 60.0
DOWNLOAD_STATUS_UPDATE_INTERVAL_MIN = 3.0
DOWNLOAD_STATUS_UPDATE_INTERVAL_MAX = 60.0
DOWNLOAD_PROGRESS_POLL_INTERVAL_MIN = 1.0
DOWNLOAD_PROGRESS_POLL_INTERVAL_MAX = 10.0
ADMIN_PROGRESS_POLL_INTERVAL_MIN = 0.2
ADMIN_PROGRESS_POLL_INTERVAL_MAX = 10.0


@dataclass(frozen=True)
class RuntimeSettings:
    single_file_group_enabled: bool
    single_file_group_delay: float
    download_status_update_interval: float
    download_progress_poll_interval: float
    admin_progress_poll_interval: float


def _parse_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on", "enabled"}:
            return True
        if normalized in {"0", "false", "no", "off", "disabled"}:
            return False
    return default


def _parse_float(
    value: Any,
    default: float,
    min_value: float | None = None,
    max_value: float | None = None,
) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if parsed <= 0:
        return default
    if min_value is not None:
        parsed = max(min_value, parsed)
    if max_value is not None:
        parsed = min(max_value, parsed)
    return parsed


def build_default_runtime_settings() -> RuntimeSettings:
    return RuntimeSettings(
        single_file_group_enabled=env.SINGLE_FILE_GROUP_ENABLED,
        single_file_group_delay=env.SINGLE_FILE_GROUP_DELAY,
        download_status_update_interval=env.DOWNLOAD_STATUS_UPDATE_INTERVAL,
        download_progress_poll_interval=env.DOWNLOAD_PROGRESS_POLL_INTERVAL,
        admin_progress_poll_interval=env.ADMIN_PROGRESS_POLL_INTERVAL,
    )


class RuntimeSettingsStore:
    def __init__(self, path: str, defaults: RuntimeSettings):
        self.path = path
        self.defaults = defaults
        self.settings = defaults

    def load(self) -> RuntimeSettings:
        if not os.path.exists(self.path):
            self.settings = self.defaults
            try:
                self.save(self.settings)
            except OSError as error:
                logger.warning("Failed to initialize runtime settings at %s: %s", self.path, error)
            return self.settings

        try:
            with open(self.path, encoding="utf-8") as settings_file:
                payload = json.load(settings_file)
        except (OSError, json.JSONDecodeError) as error:
            logger.warning("Failed to load runtime settings from %s: %s", self.path, error)
            self.settings = self.defaults
            return self.settings

        if not isinstance(payload, dict):
            logger.warning("Runtime settings file %s must contain a JSON object", self.path)
            self.settings = self.defaults
            return self.settings

        self.settings = RuntimeSettings(
            single_file_group_enabled=_parse_bool(
                payload.get("single_file_group_enabled"),
                self.defaults.single_file_group_enabled,
            ),
            single_file_group_delay=_parse_float(
                payload.get("single_file_group_delay"),
                self.defaults.single_file_group_delay,
                SINGLE_FILE_GROUP_DELAY_MIN,
                SINGLE_FILE_GROUP_DELAY_MAX,
            ),
            download_status_update_interval=_parse_float(
                payload.get("download_status_update_interval"),
                self.defaults.download_status_update_interval,
                DOWNLOAD_STATUS_UPDATE_INTERVAL_MIN,
                DOWNLOAD_STATUS_UPDATE_INTERVAL_MAX,
            ),
            download_progress_poll_interval=_parse_float(
                payload.get("download_progress_poll_interval"),
                self.defaults.download_progress_poll_interval,
                DOWNLOAD_PROGRESS_POLL_INTERVAL_MIN,
                DOWNLOAD_PROGRESS_POLL_INTERVAL_MAX,
            ),
            admin_progress_poll_interval=_parse_float(
                payload.get("admin_progress_poll_interval"),
                self.defaults.admin_progress_poll_interval,
                ADMIN_PROGRESS_POLL_INTERVAL_MIN,
                ADMIN_PROGRESS_POLL_INTERVAL_MAX,
            ),
        )
        try:
            self.save(self.settings)
        except OSError as error:
            logger.warning("Failed to backfill runtime settings at %s: %s", self.path, error)
        return self.settings

    def save(self, settings: RuntimeSettings | None = None) -> None:
        settings = settings or self.settings
        settings_dir = os.path.dirname(self.path)
        if settings_dir:
            os.makedirs(settings_dir, exist_ok=True)

        temp_path = f"{self.path}.tmp"
        with open(temp_path, "w", encoding="utf-8") as settings_file:
            json.dump(asdict(settings), settings_file, indent=2, sort_keys=True)
            settings_file.write("\n")

        os.replace(temp_path, self.path)
        self.settings = settings


runtime_settings_store = RuntimeSettingsStore(
    env.APP_SETTINGS_FILE,
    build_default_runtime_settings(),
)
runtime_settings = runtime_settings_store.load()


def save_runtime_settings(settings: RuntimeSettings) -> None:
    global runtime_settings
    runtime_settings_store.save(settings)
    runtime_settings = runtime_settings_store.settings
