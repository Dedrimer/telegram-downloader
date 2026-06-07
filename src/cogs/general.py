import logging
import html
import os
import shutil

from telegram import Update
from telegram.ext import ContextTypes

from ..middlewares.handlers import command_handler
from ..utils import (
    RuntimeSettings,
    available_languages,
    env,
    get_language,
    parse_supported_language,
    save_runtime_settings,
    t,
)
from ..utils.runtime_settings import runtime_settings_store
from ..version import RuntimeInfo, get_runtime_info

logger = logging.getLogger(__name__)

DOWNLOAD_TO_DIR = env.DOWNLOAD_TO_DIR

# List of available commands
commands = {
    "/start": "general.command.start",
    "/help": "general.command.help",
    "/info": "general.command.info",
    "/storage": "general.command.storage",
    "/status": "general.command.status",
    "/single_group": "general.command.single_group",
    "/language": "general.command.language",
}


def _build_help_message() -> str:
    commands_list = t("general.help.title") + "\n" + "\n".join(
        [
            f"<code>{html.escape(key)}</code> - {html.escape(t(value))}"
            for key, value in commands.items()
        ]
    )
    return (
        f"{commands_list}\n\n"
        + t("general.help.footer", download_dir=html.escape(DOWNLOAD_TO_DIR))
    )


def _build_info_message(user_id: int, chat_id: int, runtime_info: RuntimeInfo) -> str:
    bot_api_source = {
        "api": t("general.bot_api_source_api"),
        "unavailable": t("general.bot_api_source_unavailable"),
    }.get(runtime_info.bot_api_version_source, runtime_info.bot_api_version_source)

    return (
        f"<b>{html.escape(t('general.info.user_id'))}</b>: <code>{html.escape(str(user_id))}</code>\n"
        f"<b>{html.escape(t('general.info.chat_id'))}</b>: <code>{html.escape(str(chat_id))}</code>\n\n"
        f"<b>{html.escape(t('general.info.container_versions'))}</b>\n"
        "<code>telegram-downloader</code>: "
        f"<code>{html.escape(runtime_info.downloader_version)}</code>\n"
        "<code>telegram-bot-api</code>: "
        f"<code>{html.escape(runtime_info.bot_api_version)}</code> "
        f"({html.escape(bot_api_source)})"
    )


@command_handler("help")
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a list of available commands to the user."""
    await update.message.reply_text(
        _build_help_message(),
        parse_mode="HTML",
    )


@command_handler("start")
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a start message to the user."""
    user = update.effective_user
    await update.message.reply_html(
        t("general.start", mention=user.mention_html())
    )


@command_handler("info")
async def info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send user, chat, and runtime version information to the user."""
    user = update.effective_user
    runtime_info = await get_runtime_info()
    await update.message.reply_text(
        _build_info_message(user.id, update.effective_chat.id, runtime_info),
        parse_mode="HTML",
    )


@command_handler("storage")
async def storage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send available storage information of the specified folder."""
    if os.path.exists(DOWNLOAD_TO_DIR):
        total, used, free = shutil.disk_usage(DOWNLOAD_TO_DIR)
        await update.message.reply_text(
            "\n".join(
                [
                    t("general.storage.folder", folder=DOWNLOAD_TO_DIR),
                    t("general.storage.total", total=total // (2**30)),
                    t("general.storage.used", used=used // (2**30)),
                    t("general.storage.free", free=free // (2**30)),
                ]
            ),
            parse_mode="markdown",
        )
    else:
        await update.message.reply_text(t("general.storage.missing"))


@command_handler("language")
async def language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show or change the bot language."""
    languages = ", ".join(available_languages())
    if not context.args:
        await update.message.reply_text(
            "\n".join(
                [
                    t("general.language.current", language=get_language()),
                    t("general.language.available", languages=languages),
                    t("general.language.usage"),
                ]
            )
        )
        return

    requested = context.args[0]
    language_code = parse_supported_language(requested)
    if language_code is None:
        await update.message.reply_text(
            t("general.language.invalid", language=requested, languages=languages)
        )
        return

    current = runtime_settings_store.settings
    save_runtime_settings(
        RuntimeSettings(
            single_file_group_enabled=current.single_file_group_enabled,
            single_file_group_delay=current.single_file_group_delay,
            download_status_update_interval=current.download_status_update_interval,
            download_progress_poll_interval=current.download_progress_poll_interval,
            admin_progress_poll_interval=current.admin_progress_poll_interval,
            language=language_code,
        )
    )
    await update.message.reply_text(t("general.language.saved", language=language_code))
