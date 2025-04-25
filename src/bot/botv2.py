import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
import json
import os
from datetime import time
import pytz
import pandas as pd  # Добавляем обратно pandas
from src.utils.utils import save_schedule_image
from dotenv import load_dotenv
from src.core.google_utils import GoogleSheetsManager
from src.core.scheduler import generate_schedule, build_schedule_table
from src.core.storage import load_shifts, save_shifts, load_admins, load_notification_time, save_notification_time
load_dotenv()  # Загружает переменные из .env
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")  # Безопасное получение токена

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Инициализация менеджера Google Sheets
gs_manager = GoogleSheetsManager()

USERS_FILE = "data/users.json"
ADMINS_FILE = "data/admins.json"
TIME_FILE = "config/notification_time.json"

HELP_TEXT = """
📚 Доступные команды:

/start - Зарегистрироваться
/schedule - Получить расписание
/help - Помощь

Админ-команды:
/admin - Панель управления
/clear_sheet - Очистить Google-таблицу
"""


class UserManager:
    def __init__(self):
        self.users_file = USERS_FILE
        self._ensure_file(self.users_file)

    def _ensure_file(self, filename):
        if not os.path.exists(filename):
            with open(filename, "w") as f:
                json.dump([] if "admin" not in filename else {"time": "21:56", "day": 2}, f)

    def load_users(self):
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_user(self, chat_id):
        users = self.load_users()
        if chat_id not in users:
            users.append(chat_id)
            with open(self.users_file, "w") as f:
                json.dump(users, f)
            return True
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        if user_manager.save_user(chat_id):
            await update.message.reply_text(f"✅ Вы успешно зарегистрированы!\n\n{HELP_TEXT}")
        else:
            await update.message.reply_text(f"ℹ️ Вы уже зарегистрированы.\n\n{HELP_TEXT}")

    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка при регистрации")
        logger.error(f"Ошибка в /start: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(HELP_TEXT)


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await send_schedule_to_user(update.effective_chat.id, context)
    except Exception as e:
        logger.error(f"Ошибка при отправке расписания: {e}")
        await update.message.reply_text("⚠️ Ошибка при формировании расписания")


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return

    keyboard = [
        [InlineKeyboardButton("🕒 Изменить время уведомления", callback_data="change_time")],
        [InlineKeyboardButton("➕ Добавить слоты", callback_data="add_slots")],
        [InlineKeyboardButton("🧹 Очистить таблицу", callback_data="clear_sheet")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("🔧 Админ-панель:", reply_markup=reply_markup)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "change_time":
        await query.edit_message_text("⏰ Введите новое время в формате ЧЧ:ММ (например, 21:30):")
        context.user_data['awaiting_time'] = True
    elif query.data == "add_slots":
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        keyboard = [[InlineKeyboardButton(day, callback_data=f"add_{i}")] for i, day in enumerate(days)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📅 Выберите день для добавления слота:", reply_markup=reply_markup)
    elif query.data.startswith("add_"):
        day_idx = int(query.data.split("_")[1])
        shifts = load_shifts()
        day = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][day_idx]
        shifts[day] += 1
        save_shifts(shifts)
        await query.edit_message_text(f"✅ Добавлен слот для {day}. Теперь: {shifts[day]}")
    elif query.data == "clear_sheet":
        try:
            if gs_manager.clear_responses():  # Используем новый метод
                await query.edit_message_text("✅ Google-таблица очищена")
            else:
                await query.edit_message_text("⚠️ Ошибка при очистке таблицы")
        except Exception as e:
            logger.error(f"Ошибка очистки таблицы: {e}")
            await query.edit_message_text("⚠️ Ошибка при очистке таблицы")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('awaiting_time'):
        try:
            time_str = update.message.text
            hours, minutes = map(int, time_str.split(':'))
            if 0 <= hours < 24 and 0 <= minutes < 60:
                save_notification_time(hours, minutes, 3)  # По умолчанию среда
                context.user_data.pop('awaiting_time')
                await update.message.reply_text(f"✅ Время уведомления изменено на {time_str}")

                # Перезапускаем задачу
                context.job_queue.stop()
                tz = pytz.timezone('Europe/Moscow')
                context.job_queue.run_daily(
                    auto_send_schedule,
                    time=time(hour=hours, minute=minutes, tzinfo=tz),
                    days=(3,)
                )
            else:
                await update.message.reply_text("⚠️ Неверный формат времени. Используйте ЧЧ:ММ")
        except ValueError:
            await update.message.reply_text("⚠️ Неверный формат. Используйте ЧЧ:ММ")


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


async def send_schedule_to_user(chat_id, context):
    try:
        # Получаем данные через gs_manager
        data = gs_manager.get_clean_data()
        if not data:
            raise ValueError("Нет данных для формирования графика")

        # Преобразуем в DataFrame
        df = pd.DataFrame(data)

        # Остальная часть функции остается без изменений
        shifts = load_shifts()
        schedule_data, unfilled = generate_schedule(df, shifts)

        table = build_schedule_table(
            schedule_data,
            df["ФИО"].tolist(),
            {row["ФИО"]: row["Дни"] for row in data}
        )

        # Сохраняем и отправляем изображение
        temp_filename = f"temp_schedule_{chat_id}.png"
        save_schedule_image(table, temp_filename)

        caption = "📅 Актуальное расписание смен\n✅ - работаете\n❌ - могли бы работать\n\n"
        if unfilled:
            caption += "⚠ Не заполнены смены:\n" + "\n".join(f"- {day}: {count}" for day, count in unfilled)

        with open(temp_filename, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption
            )

        os.unlink(temp_filename)

    except Exception as e:
        error_msg = str(e) if str(e) else "Неизвестная ошибка"
        logger.error(f"Ошибка отправки расписания для {chat_id}: {error_msg}")
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"⚠️ Не удалось сформировать расписание: {error_msg}"
        )


async def auto_send_schedule(context: ContextTypes.DEFAULT_TYPE):
    try:
        for chat_id in context.bot_data['user_manager'].load_users():
            try:
                await send_schedule_to_user(chat_id, context)
            except Exception as e:
                logger.error(f"Ошибка отправки {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")


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