import html
import logging
import traceback

from telegram import Update
from telegram.ext import ContextTypes

from ..utils import env, trancute_message

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log the error and send a telegram message to notify the developer."""
    logger.error("Exception while handling an update:", exc_info=context.error)

    # Join the traceback error
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)

    # Build the error messages
    # update_str = update.to_dict() if isinstance(update, Update) else str(update)
    # update_html = f"<pre>update = {html.escape(json.dumps(update_str, indent=2, ensure_ascii=False))}</pre>\n\n"

    message_intro = "⚠️ An exception was raised while handling an update\n"
    message_chat_data = trancute_message(
        f"<pre>context.chat_data = {html.escape(str(context.chat_data))}</pre>\n\n"
    )
    message_user_data = trancute_message(
        f"<pre>context.user_data = {html.escape(str(context.user_data))}</pre>\n\n"
    )
    message_error = trancute_message(
        message=f"<pre>{html.escape(tb_string)}</pre>",
        reverse=True,
    )

    error_messages = [
        message_intro,
        message_chat_data,
        message_user_data,
        message_error,
    ]

    for message in error_messages:
        await context.bot.send_message(
            chat_id=env.USER_ID, text=message, parse_mode="HTML"
        )


 # 判断 update 是否具备发送消息的能力
    if update:
        # effective_message 会自动优先寻找消息、edited_channel_post、callback_query.message 等中的 message
        target = update.effective_message
        
        # 如果实在没有任何有效消息体，但存在 chat id（极少见情况：残留的消息），直接用 bot 发
        if not target and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="An error occurred while processing the request. Please check the logs."
            )
        elif target:
            await target.reply_text(
                "An error occurred while processing the request. Please check the logs."
            )
        else:
            logger.warning("无法找到任何有效的 message/chat 向用户回复错误。")
    else:
        logger.warning("Update 本体为 None，无法向用户回复错误信息。")
