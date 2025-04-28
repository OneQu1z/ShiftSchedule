from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes
)
import logging

from src.bot.user_manager import UserManager
from src.bot.utils import send_schedule_to_user
from src.core.google_utils import GoogleSheetsManager
from src.core.storage import load_shifts, save_shifts

logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()

HELP_TEXT = """
 Доступные команды:

/start - Зарегистрироваться
/schedule - Получить расписание
/help - Помощь
/add_slots - Добавить слоты к общему расписанию, которыми готов поделиться с другими участниками.
Админ-команды:
/admin - Панель управления
"""

# Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /start. Регистрирует пользователя и отправляет ему сообщение с приветствием.
    """
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id
        username = update.effective_user.username or "не указан"
        full_name = update.effective_user.full_name or "не указано"

        # Сохраняем пользователя (если его еще нет)
        is_new_user = user_manager.save_user(chat_id, username, full_name)

        # Добавляем в ожидающие одобрения
        user_manager.save_pending_user(chat_id)

        if is_new_user:
            response = (
                f"✅ Вы подали заявку на доступ к функционалу бота.\n\n"
                f"Ваши данные:\n"
                f"ID: {chat_id}\n"
                f"Ожидайте одобрения администратором."
            )
        else:
            user_info = user_manager.get_user_info(chat_id)
            status = "одобрен" if user_info.get('approved') else "ожидает одобрения"

            response = (
                f"ℹ️ Вы уже зарегистрированы в системе.\n\n"
                f"Ваши данные:\n"
                f"ID: {chat_id}\n"
                f"Статус: {status}\n\n"
                f"{HELP_TEXT}"
            )

        await update.message.reply_text(response)

    except Exception as e:
        logger.error(f"Ошибка в /start: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")

# Обработчик команды /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /help. Отправляет пользователю сообщение с доступными командами.
    """
    await update.message.reply_text(HELP_TEXT)

# Обработчик команды /schedule
async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /schedule. Отправляет пользователю расписание.
    """
    try:
        user_manager = UserManager()
        chat_id = update.effective_chat.id

        if user_manager.is_approved(chat_id):
            await send_schedule_to_user(update.effective_chat.id, context)
        else:
            await update.message.reply_text("⛔ Вы не одобрены для использования этой команды")

    except Exception as e:
        logger.error(f"Ошибка при отправке расписания: {e}")
        await update.message.reply_text("⚠️ Ошибка при формировании расписания")

async def add_slots(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.callback_query:
        query = update.callback_query
        day_idx = int(query.data.split("_")[1])
        shifts = load_shifts()
        day = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"][day_idx]
        shifts[day] += 1
        save_shifts(shifts)
        await query.edit_message_text(f"✅ Добавлен слот для {day}. Теперь: {shifts[day]}")
    else:
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        keyboard = [[InlineKeyboardButton(day, callback_data=f"add_{i}")] for i, day in enumerate(days)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(" Выберите день для добавления слота:", reply_markup=reply_markup)

















