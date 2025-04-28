import os
from dotenv import load_dotenv
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from src.bot.handlers import start, help_command, schedule
from src.core.storage import load_notification_time
from src.bot.admin import *

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Безопасное получение токена

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    try:
        app = ApplicationBuilder().token(TOKEN).build()
        app.bot_data['user_manager'] = UserManager()

        # Регистрация обработчиков
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("schedule", schedule))
        app.add_handler(CommandHandler("admin", admin_panel))
        app.add_handler(CommandHandler("clear_sheet", clear_sheet_command))
        app.add_handler(CommandHandler("accept", accept_command))
        app.add_handler(CommandHandler("deny", deny_command))

        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        # Загрузка времени уведомления
        notify_time = load_notification_time()
        tz = pytz.timezone('Europe/Moscow')
        app.job_queue.run_daily(
            auto_send_schedule,
            time=time(hour=notify_time['hours'], minute=notify_time['minutes'], tzinfo=tz),
            days=(notify_time['day'],)
        )

        app.run_polling()
    except Exception as e:
        logger.critical(f"Ошибка запуска: {e}")
        raise

if __name__ == '__main__':
    main()
