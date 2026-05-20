import asyncio
import logging
from collections import defaultdict
from typing import Dict, List, Optional, Tuple

from telegram import Message, Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# 存储待处理的媒体组
_pending_media_groups: Dict[str, List[Message]] = defaultdict(list)
_media_group_timers: Dict[str, asyncio.Task] = {}


def get_media_info(message: Message) -> Optional[Tuple[str, str, int]]:
    """
    从消息中提取媒体信息
    返回: (file_id, file_name, file_size) 或 None
    """
    media = message.document or message.video or message.audio
    if not media:
        return None
    
    raw_name = getattr(media, "file_name", None)
    if not raw_name:
        ext = ".mp4" if getattr(message, "video", None) else ".file"
        try:
            ext = "." + media.mime_type.split("/")[-1]
        except:
            pass
        file_name = f"{media.file_id}{ext}"
    else:
        file_name = raw_name
    
    return (media.file_id, file_name, media.file_size)


async def process_media_group(
    update: Update, 
    context: ContextTypes.DEFAULT_TYPE,
    callback_func
) -> bool:
    """
    处理媒体组消息
    
    Args:
        update: Telegram 更新
        context: 上下文
        callback_func: 处理单个文件的回调函数
        
    Returns:
        bool: 如果是媒体组的一部分返回 True，否则返回 False
    """
    message = update.message
    if not message:
        return False
    
    media_group_id = message.media_group_id
    if not media_group_id:
        return False
    
    # 添加到待处理列表
    _pending_media_groups[media_group_id].append(message)
    logger.info(f"Added message to media group {media_group_id}, total: {len(_pending_media_groups[media_group_id])}")
    
    # 如果已经有定时器，取消它
    if media_group_id in _media_group_timers:
        _media_group_timers[media_group_id].cancel()
    
    # 设置新的定时器
    _media_group_timers[media_group_id] = asyncio.create_task(
        _delayed_process(media_group_id, context, callback_func)
    )
    
    return True


async def _delayed_process(
    media_group_id: str,
    context: ContextTypes.DEFAULT_TYPE,
    callback_func
):
    """
    延迟处理媒体组，等待所有消息到达
    """
    try:
        # 等待一小段时间，确保所有消息都到达
        await asyncio.sleep(1.0)
        
        messages = _pending_media_groups.pop(media_group_id, [])
        _media_group_timers.pop(media_group_id, None)
        
        if not messages:
            return
        
        # 提取所有文件信息
        files_info = []
        for msg in messages:
            info = get_media_info(msg)
            if info:
                files_info.append((info, msg))
        
        if not files_info:
            logger.warning(f"No valid files found in media group {media_group_id}")
            return
        
        logger.info(f"Processing media group {media_group_id} with {len(files_info)} files")
        
        # 使用回调函数处理所有文件
        await callback_func(files_info, context)
        
    except asyncio.CancelledError:
        # 定时器被取消，说明还有消息到来
        pass
    except Exception as e:
        logger.error(f"Error processing media group {media_group_id}: {e}")
        import traceback
        traceback.print_exc()