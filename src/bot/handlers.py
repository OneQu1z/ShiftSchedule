from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes
)
import logging
from src.bot.utils import send_saved_schedule
from src.core.google_utils import GoogleSheetsManager
from src.core.storage import load_shifts, save_shifts, load_schedule, remove_exchange_offer, save_exchange_offer, \
    find_exchange_offer, save_schedule

logger = logging.getLogger(__name__)
gs_manager = GoogleSheetsManager()

HELP_TEXT = """
 🤖 Добро пожаловать! Вот что я умею:\n
    /start — Показать меню\n
    /help — Помощь по командам\n
    /set_fio <ФИО> — Установить ваше ФИО\n
"""

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
    """Обработчик добавления слотов с проверкой прав доступа"""
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        # Проверяем, что пользователь одобрен
        if not user_manager.is_approved(chat_id):
            await update.message.reply_text("⛔ Вы не одобрены для использования этой функции")
            return

        if update.callback_query:
            query = update.callback_query
            try:
                # Разбираем callback_data (формат "user_day_0", "user_day_1" и т.д.)
                parts = query.data.split('_')
                if len(parts) != 3 or parts[0] != 'user' or parts[1] != 'day':
                    logger.error(f"Неверный формат callback_data: {query.data}")
                    return

                day_idx = int(parts[2])  # Получаем индекс дня из третьей части
                shifts = load_shifts()
                days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]

                if day_idx < 0 or day_idx >= len(days):
                    logger.error(f"Неверный индекс дня: {day_idx}")
                    return

                day = days[day_idx]
                shifts[day] += 1
                save_shifts(shifts)
                await query.edit_message_text(f"✅ Добавлен слот для {day}. Теперь: {shifts[day]}")

            except Exception as e:
                logger.error(f"Ошибка в add_slots: {e}")
                await query.answer("⚠️ Произошла ошибка при обработке запроса")
        else:
            # Показываем кнопки выбора дня
            days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
            keyboard = [[InlineKeyboardButton(day, callback_data=f"user_day_{i}")] for i, day in enumerate(days)]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Выберите день для добавления слота:", reply_markup=reply_markup)

    except Exception as e:
        logger.error(f"Ошибка в add_slots: {e}")
        if update.callback_query:
            await update.callback_query.answer("⚠️ Произошла ошибка")
        else:
            await update.message.reply_text("⚠️ Произошла ошибка при обработке запроса")

async def set_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Устанавливает ФИО пользователя с проверкой:
    - Если ФИО уже установлено - запрещает изменение
    - Проверяет, что ФИО не занято другим пользователем
    """
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        if not context.args:
            await update.message.reply_text("ℹ️ Укажите ваше ФИО: /set_fio <Ваше ФИО>")
            return

        # Получаем текущего пользователя
        user_info = user_manager.get_user_info(chat_id)
        if not user_info:
            await update.message.reply_text("⚠️ Пользователь не найден. Введите /start")
            return

        # Проверяем, есть ли уже ФИО
        if user_info.get('fio'):
            await update.message.reply_text("⛔ Изменение ФИО запрещено. Обратитесь к администратору.")
            return

        fio = ' '.join(context.args).strip()

        # Проверяем, что ФИО не пустое
        if not fio:
            await update.message.reply_text("⚠️ ФИО не может быть пустым")
            return

        # Проверяем, что ФИО не занято другим пользователем
        existing_user = user_manager.get_user_by_fio(fio)
        if existing_user and existing_user['chat_id'] != chat_id:
            await update.message.reply_text("⚠️ Это ФИО уже используется другим пользователем")
            return

        # Обновляем ФИО
        if user_manager.update_user_fio(chat_id, fio):
            await update.message.reply_text(f"✅ Ваше ФИО установлено: {fio}")
        else:
            await update.message.reply_text("⚠️ Не удалось установить ФИО. Попробуйте позже")

    except Exception as e:
        logger.error(f"Ошибка в set_fio: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при установке ФИО")

# Добавим в handlers.py
async def start_shift_exchange(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Начинает процесс обмена сменами
    """
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        if not user_manager.is_approved(chat_id):
            await update.message.reply_text("⛔ Вы не одобрены для использования этой команды")
            return

        # Получаем текущее расписание пользователя
        schedule = load_schedule()
        user_info = user_manager.get_user_info(chat_id)
        user_fio = user_info.get('fio')

        if not user_fio:
            await update.message.reply_text("⚠️ Сначала установите ваше ФИО с помощью /set_fio")
            return

        # Получаем дни, которые пользователь может отдать (где он работает)
        user_days = []
        for day, names in schedule.items():
            if user_fio in names:
                user_days.append(day)

        if not user_days:
            await update.message.reply_text("ℹ️ У вас нет смен для обмена")
            return

        # Создаем клавиатуру для выбора дня
        keyboard = [[InlineKeyboardButton(day, callback_data=f"exchange_day_{day}")] for day in user_days]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "Выберите день, который хотите отдать:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка в start_shift_exchange: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при запуске обмена")

async def handle_exchange_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор дня для обмена
    """
    query = update.callback_query
    await query.answer()

    try:
        day_to_give = query.data.split("_")[-1]
        context.user_data['exchange_day_to_give'] = day_to_give

        # Получаем список всех пользователей (кроме текущего)
        user_manager = context.bot_data['user_manager']
        current_user = user_manager.get_user_info(query.from_user.id)
        all_users = user_manager.load_users()

        # Фильтруем только одобренных пользователей с ФИО (исключая текущего)
        valid_users = [
            user for user in all_users
            if user.get('approved') and user.get('fio') and user['chat_id'] != current_user['chat_id']
        ]

        if not valid_users:
            await query.edit_message_text("ℹ️ Нет других пользователей для обмена")
            return

        # Создаем клавиатуру для выбора пользователя
        keyboard = [
            [InlineKeyboardButton(user['fio'], callback_data=f"exchange_user_{user['chat_id']}")]
            for user in valid_users
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Вы выбрали день: {day_to_give}\n\nВыберите пользователя для обмена:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка в handle_exchange_day_selection: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при выборе дня")

async def handle_exchange_user_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор пользователя для обмена
    """
    query = update.callback_query
    await query.answer()

    try:
        target_user_id = int(query.data.split("_")[-1])
        context.user_data['exchange_target_user_id'] = target_user_id

        # Получаем расписание и информацию о пользователях
        schedule = load_schedule()
        user_manager = context.bot_data['user_manager']

        current_user = user_manager.get_user_info(query.from_user.id)
        target_user = user_manager.get_user_info(target_user_id)

        if not target_user or not target_user.get('fio'):
            await query.edit_message_text("⚠️ Выбранный пользователь не найден")
            return

        target_fio = target_user['fio']

        # Получаем дни, которые можно получить у целевого пользователя
        target_days = []
        for day, names in schedule.items():
            if target_fio in names and current_user['fio'] not in names:
                target_days.append(day)

        if not target_days:
            await query.edit_message_text(f"ℹ️ У пользователя {target_fio} нет доступных для обмена смен")
            return

        # Создаем клавиатуру для выбора дня для получения
        keyboard = [
            [InlineKeyboardButton(day, callback_data=f"exchange_target_day_{day}")]
            for day in target_days
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"Вы хотите обменять день {context.user_data['exchange_day_to_give']} "
            f"с пользователем {target_fio}\n\nВыберите день, который хотите получить:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка в handle_exchange_user_selection: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при выборе пользователя")

async def handle_exchange_target_day_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает выбор дня для получения и отправляет предложение обмена
    """
    query = update.callback_query
    await query.answer()

    try:
        target_day = query.data.split("_")[-1]
        day_to_give = context.user_data['exchange_day_to_give']
        target_user_id = context.user_data['exchange_target_user_id']

        # Получаем информацию о пользователях
        user_manager = context.bot_data['user_manager']
        current_user = user_manager.get_user_info(query.from_user.id)
        target_user = user_manager.get_user_info(target_user_id)

        if not current_user or not target_user:
            await query.edit_message_text("⚠️ Ошибка: пользователь не найден")
            return

        # Сохраняем предложение обмена
        exchange_offer = {
            'from_user': query.from_user.id,
            'from_user_fio': current_user['fio'],
            'day_to_give': day_to_give,
            'to_user': target_user_id,
            'to_user_fio': target_user['fio'],
            'day_to_get': target_day,
            'status': 'pending'
        }

        save_exchange_offer(exchange_offer)

        # Отправляем предложение целевому пользователю
        # Изменяем формат callback_data
        keyboard = [
            [
                InlineKeyboardButton("✅ Принять", callback_data=f"accept_exchange_{query.from_user.id}_{day_to_give}_{target_day}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_exchange_{query.from_user.id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await context.bot.send_message(
            chat_id=target_user_id,
            text=f"🔔 Предложение обмена сменами:\n\n"
                 f"Пользователь: {current_user['fio']}\n"
                 f"Предлагает: день {day_to_give}\n"
                 f"Взамен хочет получить: день {target_day}\n\n"
                 f"Вы согласны на обмен?",
            reply_markup=reply_markup
        )

        await query.edit_message_text(
            f"✅ Предложение обмена отправлено пользователю {target_user['fio']}\n\n"
            f"Вы отдаете: день {day_to_give}\n"
            f"Получаете: день {target_day}"
        )

        # Очищаем временные данные
        context.user_data.pop('exchange_day_to_give', None)
        context.user_data.pop('exchange_target_user_id', None)

    except Exception as e:
        logger.error(f"Ошибка в handle_exchange_target_day_selection: {e}")
        await query.edit_message_text("⚠️ Произошла ошибка при отправке предложения")

async def handle_exchange_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает ответ на предложение обмена (принять/отклонить)
    """
    query = update.callback_query
    await query.answer()

    try:
        # Разбираем callback_data
        data_parts = query.data.split("_")
        action = data_parts[0]  # "accept" или "reject"

        user_manager = context.bot_data['user_manager']
        to_user = user_manager.get_user_info(query.from_user.id)

        if action == "accept":
            # Формат: accept_exchange_<from_user_id>_<day_to_give>_<day_to_get>
            if len(data_parts) < 5:
                raise ValueError("Неверный формат callback_data для принятия")

            from_user_id = int(data_parts[2])
            day_to_give = data_parts[3]
            day_to_get = "_".join(data_parts[4:])

            # Находим предложение обмена
            offer = find_exchange_offer(from_user_id, query.from_user.id)

            if not offer or offer['day_to_give'] != day_to_give or offer['day_to_get'] != day_to_get:
                await query.edit_message_text("⚠️ Предложение обмена не найдено или устарело")
                return

            from_user = user_manager.get_user_info(from_user_id)

            if not from_user or not to_user:
                await query.edit_message_text("⚠️ Информация о пользователях не найдена")
                return

            # Проверяем, что смены все еще актуальны
            schedule = load_schedule()

            if (from_user['fio'] not in schedule.get(day_to_give, []) or
                    to_user['fio'] not in schedule.get(day_to_get, [])):
                await query.edit_message_text("⚠️ Одна из смен больше не доступна для обмена")
                remove_exchange_offer(offer)
                return

            # Выполняем обмен
            try:
                schedule[day_to_give].remove(from_user['fio'])
                schedule[day_to_give].append(to_user['fio'])

                schedule[day_to_get].remove(to_user['fio'])
                schedule[day_to_get].append(from_user['fio'])
            except ValueError as e:
                logger.error(f"Ошибка при обмене сменами: {e}")
                await query.edit_message_text("⚠️ Ошибка при обмене сменами")
                return

            # Сохраняем новое расписание
            save_schedule(schedule)

            # Удаляем предложение
            remove_exchange_offer(offer)

            # Уведомляем пользователей
            await query.edit_message_text("✅ Вы приняли предложение обмена. Расписание обновлено!")

            await context.bot.send_message(
                chat_id=from_user_id,
                text=f"✅ Пользователь {to_user['fio']} принял ваше предложение обмена:\n\n"
                     f"Вы отдаете: день {day_to_give}\n"
                     f"Получаете: день {day_to_get}\n\n"
                     f"Расписание обновлено!"
            )

        elif action == "reject":
            # Формат: reject_exchange_<from_user_id>
            if len(data_parts) < 3:
                raise ValueError("Неверный формат callback_data для отклонения")

            from_user_id = int(data_parts[2])
            offer = find_exchange_offer(from_user_id, query.from_user.id)

            if not offer:
                await query.edit_message_text("⚠️ Предложение обмена не найдено или устарело")
                return

            from_user = user_manager.get_user_info(from_user_id)

            if not from_user or not to_user:
                await query.edit_message_text("⚠️ Информация о пользователях не найдена")
                return

            # Удаляем предложение
            remove_exchange_offer(offer)
            await query.edit_message_text("❌ Вы отклонили предложение обмена")

            await context.bot.send_message(
                chat_id=from_user_id,
                text=f"❌ Пользователь {to_user['fio']} отклонил ваше предложение обмена:\n\n"
                     f"Вы предлагали: день {offer['day_to_give']}\n"
                     f"Взамен хотели получить: день {offer['day_to_get']}"
            )
        else:
            await query.edit_message_text("⚠️ Неизвестное действие")

    except Exception as e:
        logger.error(f"Ошибка в handle_exchange_response: {e}", exc_info=True)
        await query.edit_message_text("⚠️ Произошла ошибка при обработке ответа")