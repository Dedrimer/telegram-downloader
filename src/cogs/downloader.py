import asyncio
import logging
import math
import os
import platform
import re
import shutil
import traceback
from typing import List, Optional, Tuple

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
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
from ..utils import cancel_file_download, check_file_exists, env, get_file
from ..utils.media_group import get_media_info, process_media_group

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

# 存储媒体组的确认消息
_media_group_confirmations = {}

# 存储媒体组失败文件信息，用于重试
_media_group_failed_files = {}

# 存储媒体组文件选择状态
_media_group_file_selections = {}

# 存储当前下载任务，用于从 /status 或下载状态消息取消下载
_download_tasks = {}

# 存储下载状态消息取消按钮的短 token 到 file_id 映射
_download_cancel_tokens = {}

# 存储 /status 取消下载选择状态
_status_cancel_selections = {}

# Runtime settings for collecting consecutive single-file messages into one batch.
_SINGLE_FILE_GROUP_MIN_DELAY = 0.1
_SINGLE_FILE_GROUP_MAX_DELAY = 60.0


def _clamp_single_file_group_delay(delay: float) -> float:
    return max(_SINGLE_FILE_GROUP_MIN_DELAY, min(delay, _SINGLE_FILE_GROUP_MAX_DELAY))


_single_file_grouping_enabled = env.SINGLE_FILE_GROUP_ENABLED
_single_file_grouping_delay = _clamp_single_file_group_delay(env.SINGLE_FILE_GROUP_DELAY)
_pending_single_file_groups: dict[str, List[Message]] = {}
_single_file_group_timers: dict[str, asyncio.Task] = {}
_single_file_group_lock = asyncio.Lock()


def _remove_download_cancel_token(file_id: str) -> None:
    for token, mapped_file_id in list(_download_cancel_tokens.items()):
        if mapped_file_id == file_id:
            _download_cancel_tokens.pop(token, None)
            return


async def _cancel_download(file_id: str) -> bool:
    download_file = downloading_files.get(file_id)
    if download_file:
        download_file.request_cancel()

    api_cancelled = False
    try:
        api_cancelled = await cancel_file_download(file_id)
        logger.info("cancelFileDownload returned %s for file_id %s", api_cancelled, file_id)
    except Exception as e:
        logger.warning("cancelFileDownload failed for file_id %s: %s", file_id, e)

    task = _download_tasks.get(file_id)
    if task and not task.done():
        task.cancel()
        return True

    downloading_files.pop(file_id, None)
    _download_tasks.pop(file_id, None)
    _remove_download_cancel_token(file_id)
    return api_cancelled


def _build_status_cancel_keyboard(status_session_id: str, file_ids: List[str], selected: List[bool]):
    keyboard = []
    row = []
    active_file_ids = [file_id for file_id in file_ids if file_id in downloading_files]
    total_pages = math.ceil(len(active_file_ids) / 8) if active_file_ids else 1
    page = int(_status_cancel_selections.get(status_session_id, {}).get('page', 0))
    page = max(0, min(page, total_pages - 1))
    start_idx = page * 8
    end_idx = start_idx + 8
    active_index_set = set(active_file_ids[start_idx:end_idx])

    for i, file_id in enumerate(file_ids):
        if file_id not in active_index_set:
            continue
        icon = "✅" if i < len(selected) and selected[i] else "❌"
        row.append(InlineKeyboardButton(f"{icon} {i + 1}", callback_data=f"stc_tog_{status_session_id}_{i}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"stc_page_{status_session_id}_{page - 1}"))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"stc_page_{status_session_id}_{page + 1}"))
        keyboard.append(nav_row)

    active_indexes = [i for i, file_id in enumerate(file_ids) if file_id in downloading_files]
    all_selected = bool(active_indexes) and all(selected[i] for i in active_indexes)
    keyboard.append([
        InlineKeyboardButton(
            "❌ Deselect All" if all_selected else "✅ Select All",
            callback_data=f"stc_dsall_{status_session_id}" if all_selected else f"stc_sall_{status_session_id}",
        )
    ])
    keyboard.append([
        InlineKeyboardButton("🛑 Cancel Selected", callback_data=f"stc_conf_{status_session_id}"),
        InlineKeyboardButton("Close", callback_data=f"stc_close_{status_session_id}"),
    ])
    return keyboard

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
@auth_required
async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not downloading_files:
        await update.message.reply_text("No files are being downloaded at the moment.")
        return

    files_items = list(downloading_files.items())
    status_session_id = str(update.effective_chat.id)
    _status_cancel_selections[status_session_id] = {
        'file_ids': [file_id for file_id, _ in files_items],
        'selected': [False] * len(files_items),
        'page': 0,
    }

    status_message = "*Downloading files status:*\n"
    for i, (file_id, file) in enumerate(files_items, start=1):
        # 🌟 使用转义函数处理文件名和状态等字符串
        safe_file_name = escape_md(file.file_name)
        safe_status = escape_md(file.status)
        
        file_status = (
            f"> {i}. 📄 *File name:* `{safe_file_name}`\n"
            f"> 💾 *File size:* `{escape_md(file.file_size_mb)}`\n"
            f"> ⏰ *Start time:* `{escape_md(file.start_datetime)}`\n"
            f"> ⏱ *Duration:* `{escape_md(file.current_download_duration)}`\n"
            f"> 🔻 *Retries:* `{file.download_retries}`\n"
            f"> 🔄 *Status:* `{safe_status}`\n\n"
        )
        status_message += file_status

    keyboard = _build_status_cancel_keyboard(
        status_session_id,
        [file_id for file_id, _ in files_items],
        [False] * len(files_items),
    )

    status_message += (
        "\nSelect files below, then press *Cancel Selected* to cancel downloads.\n"
        "❌ means not selected, ✅ means selected."
    )

    await update.message.reply_text(
        status_message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def _parse_single_file_group_delay(value: str) -> Optional[float]:
    normalized = value.strip().lower()
    if normalized.endswith("s"):
        normalized = normalized[:-1]

    try:
        delay = float(normalized)
    except ValueError:
        return None

    if delay <= 0:
        return None
    return _clamp_single_file_group_delay(delay)


def _build_single_file_group_id(first_message: Message, last_message: Message) -> str:
    return f"single-{first_message.chat_id}-{first_message.message_id}-{last_message.message_id}"


async def _send_single_file_confirmation(
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    media = message.document or message.video or message.audio
    if not media:
        logger.warning("No valid media objects found!")
        return

    info = get_media_info(message)
    if not info:
        logger.warning("No valid media info found!")
        return

    file_id, file_name, file_size = info
    logger.info(f"Target file name parsed as: {file_name}")

    try:
        check_file_exists(file_id, file_name)
    except Exception as e:
        logger.warning(f"File exist check hit an issue (Ignored): {e}")

    safe_file_name = escape_md(file_name)
    safe_file_size = escape_md(DownloadFile.convert_size(file_size))

    response_message = (
        f"Are you sure you want to download the file?\n\n"
        f"> 📄 *File name:* `{safe_file_name}`\n"
        f"> 💾 *File size:* `{safe_file_size}`\n"
    )

    await context.bot.send_message(
        chat_id=message.chat_id,
        text=response_message,
        reply_to_message_id=message.message_id,
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


async def _queue_single_file_for_grouping(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    if not _single_file_grouping_enabled:
        return False

    message = update.message
    if not message or message.media_group_id or not get_media_info(message):
        return False

    group_key = str(message.chat_id)
    async with _single_file_group_lock:
        messages = _pending_single_file_groups.setdefault(group_key, [])
        messages.append(message)

        timer = _single_file_group_timers.pop(group_key, None)
        if timer:
            timer.cancel()

        _single_file_group_timers[group_key] = asyncio.create_task(
            _delayed_single_file_group_process(
                group_key,
                context,
                _single_file_grouping_delay,
            )
        )

    logger.info(
        "Queued single-file message %s for grouped processing in chat %s",
        message.message_id,
        message.chat_id,
    )
    return True


async def _delayed_single_file_group_process(
    group_key: str,
    context: ContextTypes.DEFAULT_TYPE,
    delay: float,
) -> None:
    try:
        await asyncio.sleep(delay)

        async with _single_file_group_lock:
            messages = _pending_single_file_groups.pop(group_key, [])
            _single_file_group_timers.pop(group_key, None)

        if not messages:
            return

        files_info = []
        for msg in messages:
            info = get_media_info(msg)
            if info:
                files_info.append((info, msg))

        if not files_info:
            logger.warning("No valid files found in single-file group %s", group_key)
            return

        synthetic_group_id = _build_single_file_group_id(messages[0], messages[-1])
        logger.info(
            "Processing single-file group %s with %s file(s)",
            synthetic_group_id,
            len(files_info),
        )
        await _handle_media_group_download(files_info, context, media_group_id=synthetic_group_id)

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Error processing single-file group %s: %s", group_key, e)
        traceback.print_exc()


async def _flush_pending_single_file_groups(context: ContextTypes.DEFAULT_TYPE) -> int:
    async with _single_file_group_lock:
        pending_groups = list(_pending_single_file_groups.values())
        _pending_single_file_groups.clear()
        timers = list(_single_file_group_timers.values())
        _single_file_group_timers.clear()

    for timer in timers:
        timer.cancel()
    if timers:
        await asyncio.gather(*timers, return_exceptions=True)

    flushed = 0
    for messages in pending_groups:
        files_info = []
        for msg in messages:
            info = get_media_info(msg)
            if info:
                files_info.append((info, msg))

        if not files_info:
            continue

        flushed += len(files_info)
        synthetic_group_id = _build_single_file_group_id(messages[0], messages[-1])
        await _handle_media_group_download(files_info, context, media_group_id=synthetic_group_id)

    return flushed


@command_handler("single_group")
@auth_required
async def single_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global _single_file_grouping_delay, _single_file_grouping_enabled

    args = context.args or []
    usage = (
        "Usage:\n"
        "/single_group on [seconds] - enable grouped single-file forwarding\n"
        "/single_group off - disable it\n"
        "/single_group <seconds> - set delay and enable it\n"
        "/single_group status - show current setting"
    )

    if not args or args[0].lower() == "status":
        state = "ON" if _single_file_grouping_enabled else "OFF"
        await update.message.reply_text(
            f"Single-file grouping is {state}.\n"
            f"Delay: {_single_file_grouping_delay:.2f}s\n\n"
            f"{usage}"
        )
        return

    command = args[0].lower()
    delay_arg = None
    enable_after_parse = False

    if command in {"on", "enable", "enabled"}:
        enable_after_parse = True
        if len(args) > 1:
            delay_arg = args[1]
    elif command in {"off", "disable", "disabled"}:
        _single_file_grouping_enabled = False
        flushed = await _flush_pending_single_file_groups(context)
        suffix = f"\nFlushed {flushed} pending file(s)." if flushed else ""
        await update.message.reply_text(f"Single-file grouping is OFF.{suffix}")
        return
    else:
        delay_arg = args[0]
        enable_after_parse = True

    if delay_arg is not None:
        delay = _parse_single_file_group_delay(delay_arg)
        if delay is None:
            await update.message.reply_text(
                "Invalid delay. Use a positive number of seconds.\n\n" + usage
            )
            return
        _single_file_grouping_delay = delay

    if enable_after_parse:
        _single_file_grouping_enabled = True

    await update.message.reply_text(
        f"Single-file grouping is ON.\nDelay: {_single_file_grouping_delay:.2f}s"
    )


async def _handle_media_group_download(
    files_info: List[Tuple[Tuple[str, str, int], Message]],
    context: ContextTypes.DEFAULT_TYPE,
    media_group_id: Optional[str] = None,
):
    """
    处理媒体组的批量下载
    """
    if not files_info:
        return
    
    # 从第一个文件获取聊天信息
    first_info, first_message = files_info[0]
    chat_id = first_message.chat_id
    
    # 构建文件列表消息
    files_list = []
    total_size = 0
    for (file_id, file_name, file_size), message in files_info:
        size_mb = file_size / 1024 / 1024
        total_size += size_mb
        safe_name = escape_md(file_name)
        files_list.append(f"> 📄 `{safe_name}` ({size_mb:.2f} MB)")
    
    files_text = "\n".join(files_list)
    
    response_message = (
        f"Are you sure you want to download {len(files_info)} files?\n\n"
        f"{files_text}\n\n"
        f"> 💾 *Total size:* `{total_size:.2f} MB`"
    )
    
    # 存储媒体组信息用于后续处理
    media_group_id = media_group_id or first_message.media_group_id
    if not media_group_id:
        media_group_id = _build_single_file_group_id(first_message, files_info[-1][1])
    _media_group_confirmations[media_group_id] = {
        'files_info': files_info,
        'context': context
    }
    
    await context.bot.send_message(
        chat_id=chat_id,
        text=response_message,
        reply_to_message_id=first_message.message_id,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Yes", callback_data=f"media_group_yes_{media_group_id}"),
                    InlineKeyboardButton("No", callback_data=f"media_group_no_{media_group_id}"),
                ],
                [
                    InlineKeyboardButton("📱 Select Files", callback_data=f"mg_select_{media_group_id}"),
                ]
            ]
        ),
    )

@message_handler(filters.Document.ALL | filters.VIDEO | filters.AUDIO)
@auth_required
async def download(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Download command received, entering pre-check...")
    
    # 检查是否是媒体组的一部分
    if update.message.media_group_id:
        logger.info(f"Message is part of media group: {update.message.media_group_id}")
        is_media_group = await process_media_group(update, context, _handle_media_group_download)
        if is_media_group:
            return


    if await _queue_single_file_for_grouping(update, context):
        return

    # 处理单个文件
    await _send_single_file_confirmation(update.message, context)

async def _update_download_status(
    status_message: Message,
    fallback_message: Message,
    text: str,
    parse_mode: str = None,
    reply_markup=None,
):
    """
    更新下载状态消息；优先编辑原提示消息，失败时才降级发送新消息
    """
    if status_message:
        try:
            await status_message.edit_text(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            logger.warning(f"Failed to edit download status message, fallback to reply: {e}")
    await fallback_message.reply_text(
        text,
        parse_mode=parse_mode,
        reply_markup=reply_markup,
    )


async def _download_single_file(
    file_id: str,
    file_name: str,
    file_size: int,
    message: Message,
    context: ContextTypes.DEFAULT_TYPE,
    status_message: Message = None,
) -> bool:
    """
    下载单个文件
    """
    task = asyncio.current_task()
    if task:
        _download_tasks[file_id] = task

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

    cancel_token = file_id[-16:] if len(file_id) > 16 else file_id
    if cancel_token in _download_cancel_tokens and _download_cancel_tokens[cancel_token] != file_id:
        cancel_token = str(abs(hash(file_id)))[-16:]
    _download_cancel_tokens[cancel_token] = file_id
    cancel_reply_markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🛑 Cancel Download", callback_data=f"dl_cancel_{cancel_token}")]]
    )

    await _update_download_status(
        status_message,
        message,
        (
            f"⬇️ *Downloading file...*\n\n"
            f"> 📄 *File:* `{escape_md(file_name)}`\n"
            f"> 💾 *Size:* `{escape_md(download_file.file_size_mb)}`"
        ),
        parse_mode="Markdown",
        reply_markup=cancel_reply_markup,
    )

    try:
        new_file = await get_file(context.bot, download_file)
    except asyncio.CancelledError:
        logger.info(f"Download cancelled for file: {file_name}")
        downloading_files.pop(file_id, None)
        _download_tasks.pop(file_id, None)
        _download_cancel_tokens.pop(cancel_token, None)
        if status_message:
            short_file_id = file_id[-8:] if len(file_id) > 8 else file_id
            await _update_download_status(
                status_message,
                message,
                f"🛑 *Download cancelled*\n\n> 📄 *File:* `{escape_md(file_name)}`",
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{short_file_id}"),
                            InlineKeyboardButton("❌ Close", callback_data="cancel_retry"),
                        ]
                    ]
                ),
            )
        return False
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        traceback.print_exc()
        downloading_files.pop(file_id, None)
        _download_tasks.pop(file_id, None)
        _download_cancel_tokens.pop(cancel_token, None)
        error_text = escape_md(str(e))
        safe_file_name = escape_md(file_name)
        
        # 提供重试按钮，使用简单的文本格式避免Markdown解析问题
        retry_message = (
            f"⛔ Error downloading file\n"
            f"File: {safe_file_name}\n"
            f"Error: {error_text}\n\n"
            f"🔄 Retry information:\n"
            f"Attempts: {download_file.download_retries + 1}\n"
            f"Last error: {escape_md(download_file.last_error or 'Unknown')}"
        )
        
        # 使用文件ID的最后8位作为回调数据，避免超过Telegram限制
        short_file_id = file_id[-8:] if len(file_id) > 8 else file_id
        
        await _update_download_status(
            status_message,
            message,
            retry_message,
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("🔄 Retry", callback_data=f"retry_{short_file_id}"),
                        InlineKeyboardButton("❌ Cancel", callback_data="cancel_retry"),
                    ]
                ]
            ),
        )
        return False
    
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
            _download_tasks.pop(file_id, None)
            _download_cancel_tokens.pop(cancel_token, None)
            await _update_download_status(
                status_message,
                message,
                escape_md("⛔ Internal error: Could not locate downloaded file on disk."),
                parse_mode="Markdown",
            )
            return False

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
            _download_tasks.pop(file_id, None)
            _download_cancel_tokens.pop(cancel_token, None)
            
            move_error_text = escape_md(str(move_error) + "\n" + str(rename_error))
            safe_target = escape_md(target_api_file)
            safe_move_to = escape_md(move_to_path)
            
            await _update_download_status(
                status_message,
                message,
                f"⛔ Error moving file\n> Source: `{safe_target}`\n> Target: `{safe_move_to}`\nErrors:\n```\n{move_error_text}```",
                parse_mode="Markdown",
            )
            _download_tasks.pop(file_id, None)
            return False

    download_file.move_complete()
    downloading_files.pop(file_id, None)
    _download_tasks.pop(file_id, None)
    _download_cancel_tokens.pop(cancel_token, None)

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
    await _update_download_status(
        status_message,
        message,
        response_message,
        parse_mode="Markdown",
    )
    return True

async def _show_file_selection(
    query,
    media_group_id: str,
    page: int = 0
):
    """
    显示文件选择界面
    支持分页：每页最多 8 个文件按钮（避免 Telegram 消息按钮过多）
    """
    if media_group_id not in _media_group_confirmations:
        await query.edit_message_text("⚠️ Media group session expired.")
        return
    
    media_group_info = _media_group_confirmations[media_group_id]
    files_info = media_group_info['files_info']
    
    # 初始化选择状态（默认全部选中）
    if media_group_id not in _media_group_file_selections:
        _media_group_file_selections[media_group_id] = [True] * len(files_info)
    
    selections = _media_group_file_selections[media_group_id]
    
    # 分页逻辑
    files_per_page = 8
    total_pages = math.ceil(len(files_info) / files_per_page)
    page = max(0, min(page, total_pages - 1))
    
    start_idx = page * files_per_page
    end_idx = min(start_idx + files_per_page, len(files_info))
    
    # 构建文件列表文本
    file_lines = []
    for i, ((file_id, file_name, file_size), msg) in enumerate(files_info):
        status = "✅" if selections[i] else "❌"
        size_mb = file_size / 1024 / 1024
        safe_name = escape_md(file_name[:25] + "..." if len(file_name) > 25 else file_name)
        file_lines.append(f"{status} {i+1}. `{safe_name}` ({size_mb:.2f} MB)")
    
    files_text = "\n".join(file_lines)
    
    # 统计选中信息
    selected_count = sum(1 for s in selections if s)
    selected_size = sum(
        files_info[i][0][2] for i in range(len(files_info)) if selections[i]
    ) / 1024 / 1024
    
    message_text = (
        f"📱 *Select files to download*\n\n"
        f"{files_text}\n\n"
        f"> 💾 *Selected size:* `{selected_size:.2f} MB`\n"
        f"> 📁 *Selected files:* `{selected_count}/{len(files_info)}`"
    )
    
    if total_pages > 1:
        message_text += f"\n> 📄 *Page:* `{page + 1}/{total_pages}`"
    
    # 构建按钮 - 当前页的文件切换按钮，每行3个
    keyboard = []
    row = []
    for i in range(start_idx, end_idx):
        status_icon = "✅" if selections[i] else "❌"
        btn = InlineKeyboardButton(
            f"{status_icon} {i+1}",
            callback_data=f"mgs_tog_{media_group_id}_{i}"
        )
        row.append(btn)
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    
    # 分页按钮（如果需要）
    if total_pages > 1:
        nav_row = []
        if page > 0:
            nav_row.append(InlineKeyboardButton(
                "⬅️ Prev",
                callback_data=f"mgs_page_{media_group_id}_{page - 1}"
            ))
        if page < total_pages - 1:
            nav_row.append(InlineKeyboardButton(
                "Next ➡️",
                callback_data=f"mgs_page_{media_group_id}_{page + 1}"
            ))
        keyboard.append(nav_row)
    
    # 全选/全不选按钮
    all_selected = all(selections)
    if all_selected:
        keyboard.append([InlineKeyboardButton(
            "❌ Deselect All",
            callback_data=f"mgs_dsall_{media_group_id}"
        )])
    else:
        keyboard.append([InlineKeyboardButton(
            "✅ Select All",
            callback_data=f"mgs_sall_{media_group_id}"
        )])
    
    # 确认/取消按钮
    keyboard.append([
        InlineKeyboardButton("✅ Confirm", callback_data=f"mgs_conf_{media_group_id}"),
        InlineKeyboardButton("❌ Cancel", callback_data=f"mgs_cancel_{media_group_id}"),
    ])
    
    await query.edit_message_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def _show_status_cancel_selection(query, status_session_id: str):
    """
    刷新 /status 的取消下载选择界面
    """
    session = _status_cancel_selections.get(status_session_id)
    if not session:
        await query.edit_message_text("Status selection session expired.")
        return

    file_ids = session['file_ids']
    selected = session['selected']

    lines = ["*Downloading files status:*\n"]
    active_count = 0
    for i, file_id in enumerate(file_ids):
        file = downloading_files.get(file_id)
        mark = "✅" if i < len(selected) and selected[i] else "❌"
        if file:
            active_count += 1
            safe_file_name = escape_md(file.file_name)
            safe_status = escape_md(file.status)
            lines.append(
                f"> {mark} {i + 1}. 📄 *File name:* `{safe_file_name}`\n"
                f"> 💾 *File size:* `{escape_md(file.file_size_mb)}`\n"
                f"> ⏰ *Start time:* `{escape_md(file.start_datetime)}`\n"
                f"> ⏱ *Duration:* `{escape_md(file.current_download_duration)}`\n"
                f"> 🔻 *Retries:* `{file.download_retries}`\n"
                f"> 🔄 *Status:* `{safe_status}`\n"
            )
        else:
            lines.append(f"> {mark} {i + 1}. `_Download already finished or removed_`\n")

    if active_count == 0:
        _status_cancel_selections.pop(status_session_id, None)
        await query.edit_message_text("No files are being downloaded at the moment.")
        return

    selected_count = sum(1 for i, s in enumerate(selected) if s and i < len(file_ids) and file_ids[i] in downloading_files)
    active_file_ids = [file_id for file_id in file_ids if file_id in downloading_files]
    total_pages = math.ceil(len(active_file_ids) / 8) if active_file_ids else 1
    page = int(session.get('page', 0))
    text = "\n".join(lines)
    text += (
        f"\n> 🛑 *Selected to cancel:* `{selected_count}/{active_count}`\n"
        f"> 📄 *Page:* `{page + 1}/{total_pages}`\n\n"
        "Select files below, then press *Cancel Selected* to cancel downloads.\n"
        "❌ means not selected, ✅ means selected."
    )

    keyboard = _build_status_cancel_keyboard(status_session_id, file_ids, selected)

    await query.edit_message_text(
        text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


@callback_query_handler()
@auth_required
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info("Button command received")
    query = update.callback_query
    await query.answer()

    # 处理下载状态消息上的取消按钮（/status 的取消按钮仍然保留）
    if query.data.startswith("dl_cancel_"):
        cancel_token = query.data[len("dl_cancel_"):]
        file_id = _download_cancel_tokens.get(cancel_token)
        if not file_id:
            await query.edit_message_text("Cancel failed: download task not found or already finished.")
            return

        file = downloading_files.get(file_id)
        cancel_started = await _cancel_download(file_id)
        if cancel_started:
            safe_file_name = escape_md(file.file_name if file else file_id)
            await query.edit_message_text(
                f"🛑 *Cancelling download...*\n\n> 📄 *File:* `{safe_file_name}`",
                parse_mode="Markdown",
            )
        else:
            downloading_files.pop(file_id, None)
            _download_tasks.pop(file_id, None)
            _download_cancel_tokens.pop(cancel_token, None)
            await query.edit_message_text("Cancel failed: download task not found or already finished.")
        return

    # 处理 /status 取消下载相关回调
    if query.data.startswith("stc_tog_"):
        parts = query.data[len("stc_tog_"):]
        last_underscore = parts.rfind("_")
        status_session_id = parts[:last_underscore]
        file_idx = int(parts[last_underscore + 1:])
        session = _status_cancel_selections.get(status_session_id)
        if session and 0 <= file_idx < len(session['selected']):
            session['selected'][file_idx] = not session['selected'][file_idx]
        await _show_status_cancel_selection(query, status_session_id)
        return

    if query.data.startswith("stc_page_"):
        parts = query.data[len("stc_page_"):]
        last_underscore = parts.rfind("_")
        status_session_id = parts[:last_underscore]
        page = int(parts[last_underscore + 1:])
        session = _status_cancel_selections.get(status_session_id)
        if session:
            session['page'] = page
        await _show_status_cancel_selection(query, status_session_id)
        return

    if query.data.startswith("stc_sall_"):
        status_session_id = query.data[len("stc_sall_"):]
        session = _status_cancel_selections.get(status_session_id)
        if session:
            for i, file_id in enumerate(session['file_ids']):
                session['selected'][i] = file_id in downloading_files
        await _show_status_cancel_selection(query, status_session_id)
        return

    if query.data.startswith("stc_dsall_"):
        status_session_id = query.data[len("stc_dsall_"):]
        session = _status_cancel_selections.get(status_session_id)
        if session:
            session['selected'] = [False] * len(session['selected'])
        await _show_status_cancel_selection(query, status_session_id)
        return

    if query.data.startswith("stc_conf_"):
        status_session_id = query.data[len("stc_conf_"):]
        session = _status_cancel_selections.pop(status_session_id, None)
        if not session:
            await query.edit_message_text("Status selection session expired.")
            return

        selected_file_ids = [
            file_id
            for i, file_id in enumerate(session['file_ids'])
            if i < len(session['selected']) and session['selected'][i] and file_id in downloading_files
        ]

        if not selected_file_ids:
            await query.answer("⚠️ Please select at least one downloading file!", show_alert=True)
            _status_cancel_selections[status_session_id] = session
            return

        cancelled_names = []
        missing_count = 0
        for file_id in selected_file_ids:
            file = downloading_files.get(file_id)
            if file:
                cancelled_names.append(file.file_name)
            cancel_started = await _cancel_download(file_id)
            if not cancel_started:
                # 如果没有可取消的任务，至少从状态列表中移除
                downloading_files.pop(file_id, None)
                _download_tasks.pop(file_id, None)
                token_to_remove = None
                for token, mapped_file_id in _download_cancel_tokens.items():
                    if mapped_file_id == file_id:
                        token_to_remove = token
                        break
                if token_to_remove:
                    _download_cancel_tokens.pop(token_to_remove, None)
                missing_count += 1

        lines = ["🛑 *Cancel request sent*\n"]
        for name in cancelled_names:
            lines.append(f"> 📄 `{escape_md(name)}`")
        if missing_count:
            lines.append(f"\n> ⚠️ Missing task records: `{missing_count}`")

        await query.edit_message_text("\n".join(lines), parse_mode="Markdown")
        return

    if query.data.startswith("stc_close_"):
        status_session_id = query.data[len("stc_close_"):]
        _status_cancel_selections.pop(status_session_id, None)
        await query.edit_message_reply_markup(reply_markup=None)
        return

    # 处理媒体组确认
    if query.data.startswith("media_group_yes_") or query.data.startswith("media_group_no_"):
        media_group_id = query.data.split("_", 3)[3]
        
        if media_group_id not in _media_group_confirmations:
            await query.edit_message_text("Media group not found or already processed.")
            return
        
        media_group_info = _media_group_confirmations.pop(media_group_id)
        files_info = media_group_info['files_info']
        group_context = media_group_info['context']
        
        await update.effective_message.edit_reply_markup(reply_markup=None)
        
        if query.data.startswith("media_group_no_"):
            logger.info(f"Media group download cancelled: {media_group_id}")
            await query.edit_message_text("Download cancelled.")
            return
        
        await query.edit_message_text(
            f"⬇️ *Batch download started*\n\n"
            f"> 📁 *Total files:* `{len(files_info)}`\n"
            f"> ✅ *Successful:* `0`\n"
            f"> ❌ *Failed:* `0`",
            parse_mode="Markdown",
        )
        
        # 开始批量下载
        logger.info(f"Starting media group download: {media_group_id}, {len(files_info)} files")
        
        success_count = 0
        fail_count = 0
        failed_files = []
        
        for index, ((file_id, file_name, file_size), message) in enumerate(files_info, start=1):
            await query.edit_message_text(
                f"⬇️ *Batch download in progress*\n\n"
                f"> 📄 *Current:* `{index}/{len(files_info)}` `{escape_md(file_name)}`\n"
                f"> ✅ *Successful:* `{success_count}`\n"
                f"> ❌ *Failed:* `{fail_count}`",
                parse_mode="Markdown",
            )
            success = await _download_single_file(
                file_id, file_name, file_size, message, group_context, status_message=query.message
            )
            if success:
                success_count += 1
            else:
                fail_count += 1
                failed_files.append((file_id, file_name, file_size, message))
            # 给每个文件下载之间一点间隔
            await asyncio.sleep(0.5)
        
        # 发送总结消息
        summary_message = (
            f"📊 *Batch download completed*\n\n"
            f"> ✅ Successful: `{success_count}`\n"
            f"> ❌ Failed: `{fail_count}`\n"
            f"> 📁 Total: `{len(files_info)}`"
        )
        
        # 如果有失败的文件，添加重试按钮
        if failed_files:
            summary_message += "\n\n🔄 *Failed files can be retried individually*"
            await query.edit_message_text(
                summary_message, 
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🔄 Retry All Failed", callback_data=f"retry_media_group_{media_group_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data="cancel_retry"),
                        ]
                    ]
                ),
            )
        else:
            await query.edit_message_text(summary_message, parse_mode="Markdown")
        
        # 存储失败文件信息用于重试
        if failed_files:
            _media_group_failed_files[media_group_id] = {
                'failed_files': failed_files,
                'context': group_context
            }
        
        return
    
    # 处理文件选择相关回调
    if query.data.startswith("mg_select_"):
        # 打开文件选择界面
        media_group_id = query.data[len("mg_select_"):]
        await _show_file_selection(query, media_group_id, page=0)
        return
    
    if query.data.startswith("mgs_tog_"):
        # 切换单个文件选中状态
        parts = query.data[len("mgs_tog_"):]
        # 最后一个 _ 后面是文件索引
        last_underscore = parts.rfind("_")
        media_group_id = parts[:last_underscore]
        file_idx = int(parts[last_underscore + 1:])
        
        if media_group_id in _media_group_file_selections:
            selections = _media_group_file_selections[media_group_id]
            if 0 <= file_idx < len(selections):
                selections[file_idx] = not selections[file_idx]
        
        # 计算当前页
        files_per_page = 8
        current_page = file_idx // files_per_page
        await _show_file_selection(query, media_group_id, page=current_page)
        return
    
    if query.data.startswith("mgs_page_"):
        # 翻页
        parts = query.data[len("mgs_page_"):]
        last_underscore = parts.rfind("_")
        media_group_id = parts[:last_underscore]
        page = int(parts[last_underscore + 1:])
        await _show_file_selection(query, media_group_id, page=page)
        return
    
    if query.data.startswith("mgs_sall_"):
        # 全选
        media_group_id = query.data[len("mgs_sall_"):]
        if media_group_id in _media_group_file_selections:
            _media_group_file_selections[media_group_id] = [True] * len(_media_group_file_selections[media_group_id])
        await _show_file_selection(query, media_group_id, page=0)
        return
    
    if query.data.startswith("mgs_dsall_"):
        # 全不选
        media_group_id = query.data[len("mgs_dsall_"):]
        if media_group_id in _media_group_file_selections:
            _media_group_file_selections[media_group_id] = [False] * len(_media_group_file_selections[media_group_id])
        await _show_file_selection(query, media_group_id, page=0)
        return
    
    if query.data.startswith("mgs_conf_"):
        # 确认选择并下载
        media_group_id = query.data[len("mgs_conf_"):]
        
        if media_group_id not in _media_group_confirmations:
            await query.edit_message_text("⚠️ Media group session expired.")
            return
        
        selections = _media_group_file_selections.get(media_group_id, [])
        if not any(selections):
            await query.answer("⚠️ Please select at least one file!", show_alert=True)
            return
        
        media_group_info = _media_group_confirmations.pop(media_group_id)
        files_info = media_group_info['files_info']
        group_context = media_group_info['context']
        
        # 过滤出选中的文件
        selected_files = [
            files_info[i] for i in range(len(files_info)) if i < len(selections) and selections[i]
        ]
        
        # 清理选择状态
        _media_group_file_selections.pop(media_group_id, None)
        
        await query.edit_message_text(
            f"⬇️ Starting download of {len(selected_files)} selected file(s)..."
        )
        
        # 开始下载选中的文件
        logger.info(f"Starting selective download: {media_group_id}, {len(selected_files)}/{len(files_info)} files")
        
        success_count = 0
        fail_count = 0
        failed_files = []
        
        for index, ((file_id, file_name, file_size), message) in enumerate(selected_files, start=1):
            await query.edit_message_text(
                f"⬇️ *Selective download in progress*\n\n"
                f"> 📄 *Current:* `{index}/{len(selected_files)}` `{escape_md(file_name)}`\n"
                f"> ✅ *Successful:* `{success_count}`\n"
                f"> ❌ *Failed:* `{fail_count}`",
                parse_mode="Markdown",
            )
            success = await _download_single_file(
                file_id, file_name, file_size, message, group_context, status_message=query.message
            )
            if success:
                success_count += 1
            else:
                fail_count += 1
                failed_files.append((file_id, file_name, file_size, message))
            await asyncio.sleep(0.5)
        
        # 发送总结消息
        summary_message = (
            f"📊 *Selective download completed*\n\n"
            f"> ✅ Successful: `{success_count}`\n"
            f"> ❌ Failed: `{fail_count}`\n"
            f"> 📁 Selected: `{len(selected_files)}/{len(files_info)}`"
        )
        
        if failed_files:
            summary_message += "\n\n🔄 *Failed files can be retried individually*"
            _media_group_failed_files[media_group_id] = {
                'failed_files': failed_files,
                'context': group_context
            }
            await query.edit_message_text(
                summary_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("🔄 Retry All Failed", callback_data=f"retry_media_group_{media_group_id}"),
                            InlineKeyboardButton("❌ Cancel", callback_data="cancel_retry"),
                        ]
                    ]
                ),
            )
        else:
            await query.edit_message_text(summary_message, parse_mode="Markdown")
        
        return
    
    if query.data.startswith("mgs_cancel_"):
        # 取消选择，清理状态
        media_group_id = query.data[len("mgs_cancel_"):]
        _media_group_file_selections.pop(media_group_id, None)
        
        # 恢复原始确认界面
        if media_group_id in _media_group_confirmations:
            media_group_info = _media_group_confirmations[media_group_id]
            files_info = media_group_info['files_info']
            
            # 重新构建文件列表
            files_list = []
            total_size = 0
            for (file_id, file_name, file_size), message in files_info:
                size_mb = file_size / 1024 / 1024
                total_size += size_mb
                safe_name = escape_md(file_name)
                files_list.append(f"> 📄 `{safe_name}` ({size_mb:.2f} MB)")
            
            files_text = "\n".join(files_list)
            
            response_message = (
                f"Are you sure you want to download {len(files_info)} files?\n\n"
                f"{files_text}\n\n"
                f"> 💾 *Total size:* `{total_size:.2f} MB`"
            )
            
            await query.edit_message_text(
                response_message,
                parse_mode="Markdown",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("Yes", callback_data=f"media_group_yes_{media_group_id}"),
                            InlineKeyboardButton("No", callback_data=f"media_group_no_{media_group_id}"),
                        ],
                        [
                            InlineKeyboardButton("📱 Select Files", callback_data=f"mg_select_{media_group_id}"),
                        ]
                    ]
                ),
            )
        else:
            await query.edit_message_text("Selection cancelled.")
        
        return

    # 处理取消重试（在单个文件确认之前拦截）
    if query.data == "cancel_retry":
        logger.info("Retry cancelled by user")
        await query.edit_message_text("Retry cancelled.")
        return
    
    # 处理媒体组重试（在单个文件确认之前拦截）
    if query.data.startswith("retry_media_group_"):
        media_group_id = query.data[len("retry_media_group_"):]
        if media_group_id in _media_group_failed_files:
            failed_info = _media_group_failed_files.pop(media_group_id)
            failed_files = failed_info['failed_files']
            retry_context = failed_info['context']
            
            logger.info(f"Retrying {len(failed_files)} failed files from media group {media_group_id}")
            await query.edit_message_text(f"🔄 Retrying {len(failed_files)} failed file(s)...")
            
            success_count = 0
            fail_count = 0
            
            for index, (file_id, file_name, file_size, message) in enumerate(failed_files, start=1):
                await query.edit_message_text(
                    f"🔄 *Retry in progress*\n\n"
                    f"> 📄 *Current:* `{index}/{len(failed_files)}` `{escape_md(file_name)}`\n"
                    f"> ✅ *Successful:* `{success_count}`\n"
                    f"> ❌ *Failed:* `{fail_count}`",
                    parse_mode="Markdown",
                )
                success = await _download_single_file(
                    file_id, file_name, file_size, message, retry_context, status_message=query.message
                )
                if success:
                    success_count += 1
                else:
                    fail_count += 1
                await asyncio.sleep(0.5)
            
            retry_summary = (
                f"🔄 *Retry completed*\n\n"
                f"> ✅ Successful: `{success_count}`\n"
                f"> ❌ Failed: `{fail_count}`\n"
                f"> 📁 Total retried: `{len(failed_files)}`"
            )
            await query.edit_message_text(retry_summary, parse_mode="Markdown")
        else:
            logger.warning(f"Media group {media_group_id} not found for retry")
            await query.edit_message_text("Retry failed: media group not found or expired.")
        return

    # 处理单个文件确认
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
        await _download_single_file(file_id, file_name, file_size, message, context, status_message=query.message)
    elif query.data.startswith("retry_"):
        # 处理单个文件重试逻辑
        short_file_id = query.data.split("_", 1)[1]
        expected_short_id = file_id[-8:] if len(file_id) > 8 else file_id
        if short_file_id == expected_short_id:
            logger.info(f"Retrying download for file -> {file_name}")
            await _download_single_file(file_id, file_name, file_size, message, context, status_message=query.message)
        else:
            logger.warning(f"Retry file ID mismatch: expected {expected_short_id}, got {short_file_id}")
            await query.edit_message_text("Retry failed: file ID mismatch.")
    else:
        logger.info("Download cancelled")
        await query.edit_message_text("Download cancelled.")
