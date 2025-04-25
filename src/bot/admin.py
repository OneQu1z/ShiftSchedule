from telegram import Update
from telegram.ext import ContextTypes
from src.core.google_utils import GoogleSheetsManager
from src.core.storage import load_admins
import logging

logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()


async def clear_sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return

    try:
        # Создаём новый экземпляр менеджера для гарантии актуального подключения
        manager = GoogleSheetsManager()
        if manager.clear_responses():
            await update.message.reply_text("✅ Таблица успешно очищена!")
        else:
            await update.message.reply_text("⚠️ Не удалось очистить таблицу. Проверьте логи.")
    except Exception as e:
        logger.error(f"Ошибка очистки: {e}", exc_info=True)
        await update.message.reply_text(f"🚨 Критическая ошибка: {str(e)}")


def is_admin(chat_id):
    admins = load_admins()
    return str(chat_id) in admins


