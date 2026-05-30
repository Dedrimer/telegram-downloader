import logging
import html
import os
import shutil

from telegram import Update
from telegram.ext import ContextTypes

from ..middlewares.handlers import command_handler
from ..utils import env

logger = logging.getLogger(__name__)

DOWNLOAD_TO_DIR = env.DOWNLOAD_TO_DIR

# List of available commands
commands = {
    "/start": "Start the bot",
    "/help": "Get help",
    "/info": "Get user and chat info",
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
    """Send user and chat IDs to the user."""
    user = update.effective_user
    await update.message.reply_text(
        f"*User ID*: {user.id}\n*Chat ID*: {update.effective_chat.id}",
        parse_mode="markdown",
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
