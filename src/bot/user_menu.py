from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.bot.handlers import (
    show_schedule,
    add_slots,
    help_command, start_shift_exchange
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обрабатывает команду /start. Регистрирует пользователя и показывает меню.
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
            await update.message.reply_text(response)
        else:
            user_info = user_manager.get_user_info(chat_id)
            status = "одобрен" if user_info.get('approved') else "ожидает одобрения"

            response = (
                f"ℹ️ Вы уже зарегистрированы в системе.\n\n"
                f"Ваши данные:\n"
                f"ID: {chat_id}\n"
                f"Статус: {status}"
            )
            await update.message.reply_text(response)

        # Показываем меню (из user_menu.py)
        keyboard = [
            ["📅 Посмотреть расписание"],
            ["➕ Запросить добавление смен"],
            ["🔄 Запросить обмен сменами"],
            ["📝 Установить ФИО"],
            ["ℹ Помощь"]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Добро пожаловать! Выберите действие:",
            reply_markup=reply_markup
        )

    except Exception as e:
        logger.error(f"Ошибка в /start: {e}", exc_info=True)
        await update.message.reply_text("⚠️ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже.")

# В user_menu.py
async def handle_user_menu_selection(update, context):
    text = update.message.text

    if text == "📅 Посмотреть расписание":
        await show_schedule(update, context)
    elif text == "➕ Запросить добавление смен":
        await add_slots(update, context)
    elif text == "🔄 Запросить обмен сменами":
        await start_shift_exchange(update, context)  # Теперь реализовано
    elif text == "📝 Установить ФИО":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Введите ваше ФИО в формате: /set_fio Иванов Иван Иванович"
        )
    elif text == "ℹ Помощь":
        await help_command(update, context)
    else:
        await update.message.reply_text("Пожалуйста, выберите действие из меню.")