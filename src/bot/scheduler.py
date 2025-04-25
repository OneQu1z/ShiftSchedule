from telegram.ext import ContextTypes
from src.bot.utils import send_schedule_to_user
import logging

logger = logging.getLogger(__name__)

async def auto_send_schedule(context: ContextTypes.DEFAULT_TYPE):
    try:
        for chat_id in context.bot_data['user_manager'].load_users():
            try:
                await send_schedule_to_user(chat_id, context)
            except Exception as e:
                logger.error(f"Ошибка отправки {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")


