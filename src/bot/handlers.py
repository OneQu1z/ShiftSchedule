from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes, CallbackContext
)
import logging

from src.bot.user_manager import UserManager
from src.bot.utils import send_schedule_to_user, send_saved_schedule
from src.core.google_utils import GoogleSheetsManager
from src.core.storage import load_shifts, save_shifts, load_schedule, save_exchange_offer, find_exchange_offer, \
    save_schedule, remove_exchange_offer

logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()

HELP_TEXT = """
Доступные команды:

/start - Зарегистрироваться
/schedule - Получить расписание
/set_fio <ФИО> - Установить ваше ФИО (должно совпадать с ФИО в таблице)
/exchange - Обменяться сменами с другим сотрудником
/help - Помощь
/add_slots - Добавить слоты к общему расписанию

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
async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показывает текущее сохранённое расписание (без пересчёта)
    """
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        if not user_manager.is_approved(chat_id):
            await update.message.reply_text("⛔ Вы не одобрены для использования этой команды")
            return

        # Загружаем сохранённое расписание
        schedule = load_schedule()
        if not schedule:
            await update.message.reply_text("ℹ️ Расписание ещё не сгенерировано. Обратитесь к администратору.")
            return

        # Формируем и отправляем расписание
        await send_saved_schedule(chat_id, context, schedule)

    except Exception as e:
        logger.error(f"Ошибка при отправке расписания: {e}")
        await update.message.reply_text("⚠️ Ошибка при загрузке расписания")

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

async def start_shift_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager = context.bot_data['user_manager']
    chat_id = update.effective_chat.id

    if not user_manager.is_approved(chat_id):
        await update.message.reply_text("⛔ Вы не одобрены для использования этой команды")
        return

    user_info = user_manager.get_user_info(chat_id)
    if not user_info.get('fio'):
        await update.message.reply_text("ℹ️ Сначала укажите ваше ФИО с помощью команды /set_fio")
        return

    schedule = load_schedule()
    user_shifts = []

    for day, names in schedule.items():
        if user_info['fio'] in names:
            user_shifts.append(day)

    if not user_shifts:
        await update.message.reply_text("ℹ️ У вас нет смен для обмена")
        return

    keyboard = [[InlineKeyboardButton(shift, callback_data=f"exch_my_{shift}")] for shift in user_shifts]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите смену, которую хотите отдать:", reply_markup=reply_markup)

async def handle_exchange_callback(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()

    data = query.data.split('_')
    user_manager = context.bot_data['user_manager']
    chat_id = query.message.chat_id

    if data[1] == 'my':
        # Пользователь выбрал свою смену для обмена
        my_shift = data[2]
        context.user_data['exchange_my_shift'] = my_shift

        # Получаем список всех пользователей кроме текущего
        users = user_manager.load_users()
        approved_users = [u for u in users if u.get('approved') and u.get('chat_id') != chat_id and u.get('fio')]

        if not approved_users:
            await query.edit_message_text("ℹ️ Нет других пользователей для обмена")
            return

        keyboard = [[InlineKeyboardButton(u['fio'], callback_data=f"exch_user_{u['chat_id']}")] for u in approved_users]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Вы выбрали смену {my_shift}. Теперь выберите пользователя:", reply_markup=reply_markup)

    elif data[1] == 'user':
        # Пользователь выбрал пользователя для обмена
        target_chat_id = int(data[2])
        target_user = user_manager.get_user_info(target_chat_id)

        if not target_user:
            await query.edit_message_text("ℹ️ Пользователь не найден")
            return

        schedule = load_schedule()
        target_shifts = []

        for day, names in schedule.items():
            if target_user['fio'] in names:
                target_shifts.append(day)

        if not target_shifts:
            await query.edit_message_text(f"ℹ️ У пользователя {target_user['fio']} нет смен для обмена")
            return

        context.user_data['exchange_target_user'] = target_user
        keyboard = [[InlineKeyboardButton(shift, callback_data=f"exch_their_{shift}")] for shift in target_shifts]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(f"Выберите смену пользователя {target_user['fio']}, которую хотите получить:", reply_markup=reply_markup)

    elif data[1] == 'their':
        # Пользователь выбрал смену, которую хочет получить
        their_shift = data[2]
        my_shift = context.user_data['exchange_my_shift']
        target_user = context.user_data['exchange_target_user']

        # Сохраняем предложение обмена
        exchange_offer = {
            'from_chat_id': chat_id,
            'from_shift': my_shift,
            'to_chat_id': target_user['chat_id'],
            'to_shift': their_shift,
            'status': 'pending'
        }

        # Сохраняем предложение (можно использовать временное хранилище или файл)
        save_exchange_offer(exchange_offer)

        # Отправляем предложение целевому пользователю
        user_info = user_manager.get_user_info(chat_id)
        await context.bot.send_message(
            chat_id=target_user['chat_id'],
            text=f"🔔 Вам поступило предложение обмена смен:\n\n"
                 f"От: {user_info['fio']}\n"
                 f"Предлагает: {my_shift}\n"
                 f"Взамен на: {their_shift}\n\n"
                 f"Для подтверждения введите /accept_exchange {chat_id}"
        )

        await query.edit_message_text("✅ Предложение обмена отправлено. Ожидайте подтверждения.")

async def accept_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager = context.bot_data['user_manager']
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("ℹ️ Укажите ID пользователя: /accept_exchange <user_id>")
        return

    from_chat_id = int(context.args[0])
    offer = find_exchange_offer(from_chat_id, chat_id)

    if not offer:
        await update.message.reply_text("ℹ️ Предложение обмена не найдено или уже обработано")
        return

    # Проверяем, что смены все еще актуальны
    schedule = load_schedule()
    if (offer['from_shift'] not in schedule or
            offer['to_shift'] not in schedule or
            user_manager.get_user_info(from_chat_id)['fio'] not in schedule[offer['from_shift']] or
            user_manager.get_user_info(chat_id)['fio'] not in schedule[offer['to_shift']]):
        await update.message.reply_text("ℹ️ Одна из смен больше не актуальна. Обмен невозможен.")
        return

    # Меняем смены местами
    from_fio = user_manager.get_user_info(from_chat_id)['fio']
    to_fio = user_manager.get_user_info(chat_id)['fio']

    schedule[offer['from_shift']].remove(from_fio)
    schedule[offer['from_shift']].append(to_fio)

    schedule[offer['to_shift']].remove(to_fio)
    schedule[offer['to_shift']].append(from_fio)

    save_schedule(schedule)

    # Уведомляем обоих пользователей
    await context.bot.send_message(
        chat_id=from_chat_id,
        text=f"✅ Обмен сменами подтвержден:\n"
             f"Ваша смена {offer['from_shift']} теперь у {to_fio}\n"
             f"Вы получили смену {offer['to_shift']}"
    )

    await update.message.reply_text(
        f"✅ Обмен сменами подтвержден:\n"
        f"Ваша смена {offer['to_shift']} теперь у {from_fio}\n"
        f"Вы получили смену {offer['from_shift']}"
    )

    # Удаляем предложение
    remove_exchange_offer(offer)

async def set_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_manager = context.bot_data['user_manager']
    chat_id = update.effective_chat.id

    if not context.args:
        await update.message.reply_text("ℹ️ Укажите ваше ФИО: /set_fio <Ваше ФИО>")
        return

    fio = ' '.join(context.args)
    user_manager.update_user_fio(chat_id, fio)
    await update.message.reply_text(f"✅ Ваше ФИО установлено: {fio}")









