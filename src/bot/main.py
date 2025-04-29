import os
import logging
from dotenv import load_dotenv
import pytz
from datetime import time

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from src.bot.handlers import set_fio, add_slots, handle_exchange_day_selection, handle_exchange_user_selection, \
    handle_exchange_target_day_selection, handle_exchange_response
from src.bot.admin import admin_panel, clear_sheet_command, accept_command, deny_command, button_handler, handle_message
from src.bot.user_manager import UserManager
from src.bot.user_menu import handle_user_menu_selection, start
from src.bot.utils import auto_send_schedule
from src.core.storage import load_notification_time

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# В main.py добавим новые обработчики
async def combined_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Сначала проверяем админские запросы
    if (context.user_data.get('awaiting_time') or
            context.user_data.get('awaiting_day') or
            context.user_data.get('awaiting_slots')):
        await handle_message(update, context)
    else:
        # Если это не админский запрос, обрабатываем как обычное меню
        await handle_user_menu_selection(update, context)

def main():
    if not TOKEN:
        logger.critical("TELEGRAM_BOT_TOKEN не найден в .env файле.")
        raise ValueError("Нет токена Telegram бота")

    try:
        app = ApplicationBuilder().token(TOKEN).build()
        app.bot_data['user_manager'] = UserManager()

        # Регистрация обработчиков
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CommandHandler("admin", admin_panel))
        app.add_handler(CommandHandler("clear_sheet", clear_sheet_command))
        app.add_handler(CommandHandler("accept", accept_command))
        app.add_handler(CommandHandler("deny", deny_command))
        app.add_handler(CommandHandler("set_fio", set_fio))

        # Обработка обмена сменами
        app.add_handler(CallbackQueryHandler(handle_exchange_day_selection, pattern="^exchange_day_"))
        app.add_handler(CallbackQueryHandler(handle_exchange_user_selection, pattern="^exchange_user_"))
        app.add_handler(CallbackQueryHandler(handle_exchange_target_day_selection, pattern="^exchange_target_day_"))
        app.add_handler(CallbackQueryHandler(handle_exchange_response, pattern="^(accept|reject)_exchange_"))

        # Обработчик для обычных пользователей (префикс user_day_)
        app.add_handler(CallbackQueryHandler(add_slots, pattern="^user_day_"))
        # Обработчик для админов (префикс admin_day_)
        app.add_handler(CallbackQueryHandler(button_handler, pattern="^admin_day_"))

        # Обработчики админ-панели
        app.add_handler(CallbackQueryHandler(button_handler))

        # Объединенный обработчик текстовых сообщений
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, combined_message_handler))

        # Загрузка времени уведомления
        notify_time = load_notification_time()
        tz = pytz.timezone('Europe/Moscow')
        app.job_queue.run_daily(
            auto_send_schedule,
            time=time(hour=notify_time[0], minute=notify_time[1], tzinfo=tz),
            days=(notify_time[2],)
        )

        app.run_polling()
    except Exception as e:
        logger.critical(f"Ошибка запуска: {e}")
        raise
if __name__ == '__main__':
    main()
