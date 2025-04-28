from datetime import time

import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.bot.scheduler import auto_send_schedule
from src.bot.user_manager import UserManager
from src.core.google_utils import GoogleSheetsManager
from src.core.storage import load_admins, load_shifts, save_shifts, save_notification_time, load_notification_time
import logging

logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()

# Обработчик команды /admin
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /admin. Отправляет пользователю админ-панель с кнопками для управления ботом.
    """
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return

    keyboard = [
        [InlineKeyboardButton(" Изменить время уведомления", callback_data="change_time")],
        [InlineKeyboardButton(" Изменить день уведомления", callback_data="change_day")],
        [InlineKeyboardButton("➕ Добавить слоты", callback_data="add_slots")],
        [InlineKeyboardButton(" Очистить таблицу", callback_data="clear_sheet")],
        [InlineKeyboardButton(" Управление", callback_data="management")]  # Новая кнопка
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(" Админ-панель:", reply_markup=reply_markup)

# Обработчик нажатий кнопок
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает нажатия кнопок. Обрабатывает нажатия кнопок в админ-панели и другие кнопки.
    """
    query = update.callback_query
    await query.answer()

    if query.data == "change_time":
        await query.edit_message_text("⏰ Введите новое время в формате ЧЧ:ММ (например, 21:30):")
        context.user_data['awaiting_time'] = True
    elif query.data == "change_day":
        await query.edit_message_text(" Введите новый день недели (1-7):")
        context.user_data['awaiting_day'] = True
    elif query.data == "add_slots":
        days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        keyboard = [[InlineKeyboardButton(day, callback_data=f"add_{i}")] for i, day in enumerate(days)]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(" Выберите день для добавления слота:", reply_markup=reply_markup)
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
    elif query.data == "management":  # Новая функция для обработки нажатия кнопки "Управление"
        try:
            user_manager = UserManager()
            users = user_manager.load_users()

            message = "Список пользователей:\n"
            for user in users:
                message += f"Ник: {user['username']}\nИмя: {user['name']}\nЧат ID: {user['chat_id']}\n\n"

            await query.edit_message_text(message)
            await query.message.reply_text("Введите /accept или /deny и Chat ID пользователя для одобрения или отказа")
        except Exception as e:
            logger.error(f"Ошибка в button_handler: {e}")
            await query.edit_message_text("⚠️ Ошибка при обработке нажатия кнопки")


# Обработчик сообщений от пользователя
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает сообщения от пользователя. Обрабатывает сообщения, которые пользователь отправляет боту.
    """
    if context.user_data.get('awaiting_time'):
        try:
            time_str = update.message.text
            hours, minutes = map(int, time_str.split(':'))
            if 0 <= hours < 24 and 0 <= minutes < 60:
                day = load_notification_time()[2]  # Получаем текущий день уведомления

                save_notification_time(hours, minutes, day)
                context.user_data.pop('awaiting_time')
                await update.message.reply_text(f"✅ Время уведомления изменено на {time_str}")

                # Перезапускаем задачу
                context.job_queue.stop()
                tz = pytz.timezone('Europe/Moscow')
                context.job_queue.run_daily(
                    auto_send_schedule,
                    time=time(hour=hours, minute=minutes, tzinfo=tz),
                    days=(day,)
                )
            else:
                await update.message.reply_text("⚠️ Неверный формат времени. Используйте ЧЧ:ММ")
        except ValueError:
            await update.message.reply_text("⚠️ Неверный формат. Используйте ЧЧ:ММ")

    if context.user_data.get('awaiting_day'):
        try:
            day_num = int(update.message.text)
            if 1 <= day_num <= 7:
                hours = load_notification_time()[0]
                minutes = load_notification_time()[1]

                save_notification_time(hours, minutes, day_num % 7)  # Сохраняем день недели (0-6)
                context.user_data.pop('awaiting_day')
                await update.message.reply_text(f"✅ День уведомления изменен на {day_num} день недели")
            else:
                await update.message.reply_text("⚠️ Неверный формат дня недели. Используйте число от 1 до 7")
        except ValueError:
            await update.message.reply_text("⚠️ Неверный формат. Используйте число от 1 до 7")

# Обработчик команды /accept
async def accept_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /accept. Одобряет пользователя.
    """
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return

    try:
        chat_id = int(context.args[0])
        user_manager = UserManager()
        user_manager.accept_user(chat_id)
        await update.message.reply_text(f"✅ Пользователь с Chat ID {chat_id} одобрен")
    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка при одобрении пользователя")
        logger.error(f"Ошибка в /accept: {e}")

# Обработчик команды /deny
async def deny_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /deny. Отклоняет пользователя и отправляет ему сообщение.
    """
    if not is_admin(update.effective_chat.id):
        await update.message.reply_text("⛔ У вас нет прав доступа!")
        return

    try:
        chat_id = int(context.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("⚠️ Неверный формат команды. Используйте /deny <Chat ID>")
        return

    user_manager = UserManager()
    if not user_manager.deny_user(chat_id):
        await update.message.reply_text("⚠️ Пользователь не найден.")
        return

    await context.bot.send_message(chat_id, "К сожалению, мы не можем одобрить доступ к нашим функциям, попробуйте ещё раз, введите /start")
    await update.message.reply_text("✅ Пользователь отклонен.")

# Обработчик команды /clear_sheet
async def clear_sheet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /clear_sheet. Очищает Google-таблицу.
    """
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
        await update.message.reply_text(f" Критическая ошибка: {str(e)}")


def is_admin(chat_id):
    admins = load_admins()
    return str(chat_id) in admins


