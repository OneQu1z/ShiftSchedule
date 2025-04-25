import logging
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
import json
import os
from datetime import time
import pytz
import pandas as pd
from google_utils import get_clean_schedule_data
from scheduler import generate_schedule, build_schedule_table
from storage import load_shifts
from utils import save_schedule_image
import tempfile

# Настройка логгирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = "7660267218:AAG48JMVEkciCwdHYdTNKoUVrLHMxzG8o7I"
USERS_FILE = "users.json"

HELP_TEXT = """
📚 Доступные команды:

/start - Зарегистрироваться для получения уведомлений
/schedule - Получить текущее расписание смен
/help - Показать это сообщение с подсказками

Расписание автоматически отправляется по средам в 21:56
"""


class UserManager:
    def __init__(self):
        self.users_file = USERS_FILE
        self._ensure_users_file()

    def _ensure_users_file(self):
        """Создает файл users.json если его нет"""
        if not os.path.exists(self.users_file):
            with open(self.users_file, "w") as f:
                json.dump([], f)

    def load_users(self):
        """Загружает список chat_id из файла"""
        try:
            with open(self.users_file, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return []

    def save_user(self, chat_id):
        """Добавляет новый chat_id в файл"""
        users = self.load_users()
        if chat_id not in users:
            users.append(chat_id)
            with open(self.users_file, "w") as f:
                json.dump(users, f)
            return True
        return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    try:
        user_manager = context.bot_data['user_manager']
        chat_id = update.effective_chat.id

        if user_manager.save_user(chat_id):
            await update.message.reply_text(
                "✅ Вы успешно зарегистрированы!\n"
                "Теперь вы будете получать автоматические уведомления.\n\n"
                f"{HELP_TEXT}"
            )
            logger.info(f"Новый пользователь: {chat_id}")
        else:
            await update.message.reply_text(
                "ℹ️ Вы уже зарегистрированы.\n\n"
                f"{HELP_TEXT}"
            )

    except Exception as e:
        await update.message.reply_text("⚠️ Произошла ошибка при регистрации")
        logger.error(f"Ошибка в /start: {e}")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    await update.message.reply_text(HELP_TEXT)


async def schedule(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /schedule - отправляет текущее расписание"""
    try:
        await send_schedule_to_user(update.effective_chat.id, context)
    except Exception as e:
        logger.error(f"Ошибка при отправке расписания: {e}")
        await update.message.reply_text("⚠️ Произошла ошибка при формировании расписания")


async def send_schedule_to_user(chat_id, context):
    """Функция для отправки расписания конкретному пользователю"""
    try:
        # Получаем данные
        df = get_clean_schedule_data()
        shifts = load_shifts()

        # Генерируем расписание
        schedule_data, unfilled = generate_schedule(df, shifts)
        availability = {row["ФИО"]: row["Дни"] for _, row in df.iterrows()}
        table = build_schedule_table(schedule_data, df["ФИО"].tolist(), availability)

        # Создаем временный файл
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            temp_filename = tmp.name

        # Сохраняем изображение
        save_schedule_image(table, temp_filename)

        # Формируем подпись
        caption = "📅 Актуальное расписание смен\n\n"
        caption += "✅ - вы работаете в этот день\n"
        caption += "❌ - вы могли бы работать, но не назначены\n\n"

        if unfilled:
            caption += "⚠ Не заполнены смены:\n"
            for day, count in unfilled:
                caption += f"- {day}: {count} не хватает\n"

        caption += "\nДля обновления расписания используйте /schedule"

        # Отправляем фото
        with open(temp_filename, "rb") as photo:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=caption
            )

        # Удаляем временный файл
        os.unlink(temp_filename)

    except Exception as e:
        logger.error(f"Ошибка при отправке расписания для {chat_id}: {e}")
        raise


async def auto_send_schedule(context: ContextTypes.DEFAULT_TYPE):
    """Автоматическая рассылка расписания по средам в 21:56"""
    try:
        user_manager = context.bot_data['user_manager']
        users = user_manager.load_users()

        if not users:
            logger.warning("Нет зарегистрированных пользователей для рассылки")
            return

        logger.info(f"Начинаю рассылку расписания для {len(users)} пользователей")

        for chat_id in users:
            try:
                await send_schedule_to_user(chat_id, context)
                logger.info(f"Расписание успешно отправлено пользователю {chat_id}")
            except Exception as e:
                logger.error(f"Не удалось отправить расписание {chat_id}: {e}")

    except Exception as e:
        logger.error(f"Ошибка автоматической рассылки расписания: {e}")


def main():
    """Запуск бота"""
    try:
        app = ApplicationBuilder().token(TOKEN).build()

        # Инициализация менеджера пользователей
        app.bot_data['user_manager'] = UserManager()

        # Регистрация обработчиков команд
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("schedule", schedule))
        app.add_handler(CommandHandler("help", help_command))

        # Настройка автоматической рассылки расписания по средам в 21:56
        tz = pytz.timezone('Europe/Moscow')
        app.job_queue.run_daily(
            auto_send_schedule,
            time=time(hour=22, minute=11, tzinfo=tz),
            days=(3,)  # Только среда (0-пн, 1-вт, 2-ср и т.д.)
        )

        logger.info("Бот запущен и работает")
        app.run_polling()

    except Exception as e:
        logger.critical(f"Ошибка запуска бота: {e}")
        raise


if __name__ == '__main__':
    main()