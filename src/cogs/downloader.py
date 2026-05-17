import asyncio
import logging
import math
import os
import platform
import re
import shutil
import traceback

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes, filters

from ..middlewares.auth import auth_required
from ..middlewares.handlers import (
    callback_query_handler,
    command_handler,
    message_handler,
)
from ..models import DownloadFile, downloading_files
from ..utils import check_file_exists, env, get_file

logger = logging.getLogger(__name__)

# Environment variables
BOT_TOKEN = env.BOT_TOKEN
BOT_API_DIR = env.BOT_API_DIR
DOWNLOAD_TO_DIR = env.DOWNLOAD_TO_DIR

# 确保最后带上反斜杠，作为代码层的终极防护
if not BOT_API_DIR.endswith("/"):
    BOT_API_DIR += "/"
if not DOWNLOAD_TO_DIR.endswith("/"):
    DOWNLOAD_TO_DIR += "/"

TOKEN_SUB_DIR = BOT_TOKEN.replace(":", ":", 1) if os.name == "nt" else BOT_TOKEN

# 🌟 定义用于 Markdown V1 的转义函数（这可以绕过 V2 的各种麻烦限制）
def escape_md(text: str) -> str:
    if not isinstance(text, str):
        text = ""
    # 在 Markdown V1 中，代码块 `...` 内几乎只需要转义反引号本身
    # 如果字符中本身包含反引号，我们移除它（因为无法嵌套在 V1 单行代码块中）
    return text.replace('`', "'")

# 🌟 核心修复：通用的 MarkdownV2 转义函数
def escape_md2(text: str) -> str:
    """
    在 MarkdownV2 模式下，转义消息文本中的特殊字符
    """
    if not isinstance(text, str):
        text = str(text)
    # 这里的列表是 Telegram 所有需要转义的特殊字符
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', text)

@command_handler("status")
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not downloading_files:
        await update.message.reply_text("No files are being downloaded at the moment.")
        return

    status_message = "*Downloading files status:*\nPage 1\n"
    for i, file in enumerate(downloading_files.values(), start=1):
        # 🌟 使用转义函数处理文件名和状态等字符串
        safe_file_name = escape_md(file.file_name)
        safe_status = escape_md(file.status)
        
        file_status = (
            f"> 📄 *File name:* `{safe_file_name}`\n"
            f"> 💾 *File size:* `{escape_md(file.file_size_mb)}`\n"
            f"> ⏰ *Start time:* `{escape_md(file.start_datetime)}`\n"
            f"> ⏱ *Duration:* `{escape_md(file.current_download_duration)}`\n"
            f"> 🔻 *Retries:* `{file.download_retries}`\n"
            f"> 🔄 *Status:* `{safe_status}`\n\n"
        )
        status_message += file_status

        if i % 2 == 0 or i == len(downloading_files):
            if i > 2:
                status_message = f"Page {math.ceil(i / 2)}\n" + status_message
            await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=status_message,
                parse_mode="Markdown",
            )
            status_message = ""
            await asyncio.sleep(0.3)

@message_handler(filters.Document.ALL | filters.VIDEO | filters.AUDIO)
@auth_required
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Download command received, entering pre-check...")
    
    media = update.message.document or update.message.video or update.message.audio
    if not media:
        logger.warning("No valid media objects found!")
        return
    
    raw_name = getattr(media, "file_name", None)
    if not raw_name:
        ext = ".mp4" if getattr(update.message, "video", None) else ".file"
        try:
             ext = "." + media.mime_type.split("/")[-1]
        except:
             pass
        file_name = f"{media.file_id}{ext}"
    else:
        file_name = raw_name

    logger.info(f"Target file name parsed as: {file_name}")

    try:
        check_file_exists(media.file_id, file_name)
    except Exception as e:
        logger.warning(f"File exist check hit an issue (Ignored): {e}")

    file_size = DownloadFile.convert_size(media.file_size)
    
    # 🌟 转义动态部分：文件名和文件大小
    safe_file_name = escape_md(file_name)
    safe_file_size = escape_md(file_size)
    
    response_message = (
        f"Are you sure you want to download the file?\n\n"
        f"> 📄 *File name:* `{safe_file_name}`\n"
        f"> 💾 *File size:* `{safe_file_size}`\n"
    )

    await context.bot.send_message(
        chat_id=update.message.chat_id,
        text=response_message,
        reply_to_message_id=update.message.message_id,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data="yes"),
                    InlineKeyboardButton("No", callback_data="no"),
                ]
            ]
        ),
    )

@callback_query_handler()
@auth_required
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Button command received")
    query = update.callback_query
    await query.answer()

    message = update.effective_message.reply_to_message
    media = message.document or message.video or message.audio
    if not media:
        await query.edit_message_text("Original file message not found or unsupported.")
        return
        
    file_id = media.file_id
    raw_name = getattr(media, "file_name", None)
    if not raw_name:
        ext = ".mp4" if getattr(message, "video", None) else ".file"
        file_name = f"{file_id}{ext}"
    else:
        file_name = raw_name
        
    file_size = media.file_size

    await update.effective_message.edit_reply_markup(reply_markup=None)

    if query.data == "yes":
        logger.info(f"Confirmed to download file -> {file_name}")

        try:
            check_file_exists(file_id, file_name)
        except Exception as e:
             logger.warning(f"Secondary check bypassed: {e}")

        download_file = DownloadFile(
            file_id,
            file_name,
            file_size,
        )
        downloading_files[file_id] = download_file

        await message.reply_text("⬇️ Downloading file...")

        try:
            new_file = await get_file(context.bot, download_file)
        except Exception as e:
            logger.error(f"Error downloading file: {e}")
            traceback.print_exc()
            downloading_files.pop(file_id, None)
            error_text = escape_md(str(e))
            safe_file_name = escape_md(file_name)
            await message.reply_text(
                f"⛔ Error downloading file\n`{safe_file_name}`\n```\n{error_text}```",
                parse_mode="Markdown",
            )
            return
        
        # 处理下载后的移动逻辑（原逻辑保持并修复）
        else:
            download_file.download_complete()

            relative_path = new_file.file_path
            
            if not relative_path.startswith(TOKEN_SUB_DIR):
                target_api_file = os.path.join(BOT_API_DIR, TOKEN_SUB_DIR, relative_path)
            else:
                target_api_file = os.path.join(BOT_API_DIR, relative_path)

            move_to_path = os.path.join(DOWNLOAD_TO_DIR, file_name)

            if not os.path.exists(target_api_file):
                logger.warning(f"Standard path {target_api_file} not found. Attempting recursive search fallback...")
                file_basename = relative_path.split("/")[-1]
                found = False
                for root, dirs, files in os.walk(BOT_API_DIR):
                    if file_basename in files:
                        target_api_file = os.path.join(root, file_basename)
                        found = True
                        logger.info(f"Fallback successful: Found file at {target_api_file}")
                        break
                if not found:
                    logger.error(f"Cannot locate the downloaded file anywhere inside {BOT_API_DIR}")
                    await message.reply_text(escape_md("⛔ Internal error: Could not locate downloaded file on disk."), parse_mode="Markdown")
                    return

            try:
                os.makedirs(DOWNLOAD_TO_DIR, exist_ok=True)
                # 🌟 shutil.move 会根据文件系统智能判断，能够跨文件系统移动
                await asyncio.to_thread(shutil.move, target_api_file, move_to_path)
            except Exception as move_error:
                logger.error(f"Error MOVING file: {move_error}")
                try:
                    # 只有在 shutil 失败时，再尝试验名（退化逻辑）
                    os.rename(target_api_file, move_to_path)
                except Exception as rename_error:
                    logger.error(f"Error RENAMING file (Fallback failed): {rename_error}")
                    downloading_files.pop(file_id, None)
                    
                    move_error_text = escape_md(str(move_error) + "\n" + str(rename_error))
                    safe_target = escape_md(target_api_file)
                    safe_move_to = escape_md(move_to_path)
                    
                    await message.reply_text(
                        f"⛔ Error moving file\n> Source: `{safe_target}`\n> Target: `{safe_move_to}`\nErrors:\n```\n{move_error_text}```",
                        parse_mode="Markdown",
                    )
                    return

            # 🌟 修复 Bug：删除多余的第二次 move_complete 调用
            download_file.move_complete()
            downloading_files.pop(file_id, None)

            if platform.system() == "Linux":
                try:
                    os.chmod(move_to_path, 0o664)
                except Exception as e:
                    logger.warning(f"Failed to change permissions: {e}")

            safe_file_name_final = escape_md(file_name)
            response_message = (
                f"✅ File downloaded successfully.\n\n"
                f"> 📄 *File:* `{safe_file_name_final}`\n"
                f"> 💾 *Size:* `{escape_md(download_file.file_size_mb)}`\n"
                f"> ⏱ *Total Duration:* `{escape_md(download_file.total_duration)}`"
            )
            await message.reply_text(response_message, parse_mode="Markdown")

    else:
        logger.info("Download cancelled")
        await message.reply_text("Download cancelled.")