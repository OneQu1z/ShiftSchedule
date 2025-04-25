import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from datetime import time
import logging
from src.bot.utils import send_schedule_to_user
from src.core.storage import load_admins, load_notification_time, save_notification_time, load_shifts, save_shifts
from src.core.google_utils import GoogleSheetsManager
from src.bot.scheduler import auto_send_schedule
logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()

HELP_TEXT = """
📚 Доступные команды:

/start - Зарегистрироваться
/schedule - Получить расписание
/help - Помощь

Админ-команды:
/admin - Панель управления
/clear_sheet - Очистить Google-таблицу
"""


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

