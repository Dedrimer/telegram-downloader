import logging
import html
import os
import shutil

from telegram import Update
from telegram.ext import ContextTypes

from ..middlewares.handlers import command_handler
from ..utils import env
from ..version import RuntimeInfo, get_runtime_info

logger = logging.getLogger(__name__)

DOWNLOAD_TO_DIR = env.DOWNLOAD_TO_DIR

# List of available commands
commands = {
    "/start": "Start the bot",
    "/help": "Get help",
    "/info": "Get user, chat, and container version info",
    "/storage": "Get available storage information",
    "/status": "Get downloading files status",
    "/single_group": "Group consecutive single-file messages into one batch",
}


def _build_help_message() -> str:
    commands_list = "The following commands are available:\n" + "\n".join(
        [
            f"<code>{html.escape(key)}</code> - {html.escape(value)}"
            for key, value in commands.items()
        ]
    )
    return (
        f"{commands_list}\n\n"
        "Send me a file and I'll download it to "
        f"<code>{html.escape(DOWNLOAD_TO_DIR)}</code>."
    )


def _build_info_message(user_id: int, chat_id: int, runtime_info: RuntimeInfo) -> str:
    bot_api_source = {
        "api": "reported by Bot API",
        "unavailable": "unavailable",
    }.get(runtime_info.bot_api_version_source, runtime_info.bot_api_version_source)

    return (
        f"<b>User ID</b>: <code>{html.escape(str(user_id))}</code>\n"
        f"<b>Chat ID</b>: <code>{html.escape(str(chat_id))}</code>\n\n"
        "<b>Container Versions</b>\n"
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
        f"Hi {user.mention_html()}! I'm a bot that can download files for you. "
        "Send me a file and I'll download it for you.\n\n"
        "Use /help to see available commands."
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
            f"📂 *Folder*:   `{DOWNLOAD_TO_DIR}`\n"
            f"🟣 *Total Space*:   `{total // (2**30)} GB`\n"
            f"🟠 *Used Space*:   `{used // (2**30)} GB`\n"
            f"🟢 *Free Space*:    `{free // (2**30)} GB`",
            parse_mode="markdown",
        )
    else:
        await update.message.reply_text("The specified folder does not exist.")
