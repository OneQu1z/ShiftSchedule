import os
import pandas as pd
from telegram.ext import ContextTypes

from src.core.google_utils import GoogleSheetsManager
from src.core.scheduler import generate_schedule, build_schedule_table
from src.core.storage import load_shifts, save_schedule
from src.utils.utils import save_schedule_image
import logging

gs_manager = GoogleSheetsManager()
logger = logging.getLogger(__name__)

async def auto_send_schedule(context: ContextTypes.DEFAULT_TYPE):
    try:
        # Получаем данные и генерируем расписание один раз
        data = gs_manager.get_clean_data()
        if not data:
            raise ValueError("Нет данных для формирования графика")

        if not gs_manager.remove_duplicates():
            raise ValueError("Не удалось очистить дубликаты")

        # Обновляем данные после удаления дубликатов (на всякий случай)
        data = gs_manager.get_clean_data()

        df = pd.DataFrame(data)
        shifts = load_shifts()
        schedule_data, unfilled = generate_schedule(df, shifts)

        # Сохраняем расписание
        save_schedule(schedule_data)

        # Формируем таблицу
        table = build_schedule_table(
            schedule_data,
            df["ФИО"].tolist(),
            {row["ФИО"]: row["Дни"] for row in data}
        )

        # Создаем временный файл с уникальным именем
        temp_filename = "temp_schedule_shared.png"
        save_schedule_image(table, temp_filename)

        # Формируем подпись
        caption = "📅 Актуальное расписание смен\n✅ - работаете\n❌ - могли бы работать\n\n"
        if unfilled:
            caption += "⚠ Не заполнены смены:\n" + "\n".join(f"- {day}: {count}" for day, count in unfilled)

        # Читаем файл один раз в память
        with open(temp_filename, "rb") as photo:
            photo_data = photo.read()

        # Отправляем всем пользователям
        for chat_id in context.bot_data['user_manager'].get_approved_users():
            try:
                await context.bot.send_photo(
                    chat_id=chat_id,
                    photo=photo_data,
                    caption=caption
                )
            except Exception as e:
                logger.error(f"Ошибка отправки {chat_id}: {e}")

        # Удаляем временный файл
        os.unlink(temp_filename)

    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")

async def send_saved_schedule(chat_id, context, schedule_data):
    """
    Отправляет сохранённое расписание без пересчёта
    """
    try:
        # Получаем данные из Google Sheets только для информации о доступных днях
        data = gs_manager.get_clean_data()
        df = pd.DataFrame(data) if data else pd.DataFrame()

        # Формируем таблицу
        table = build_schedule_table(
            schedule_data,
            df["ФИО"].tolist() if not df.empty else [],
            {row["ФИО"]: row["Дни"] for row in data} if data else {}
        )

        # Сохраняем и отправляем изображение
        temp_filename = f"temp_schedule_{chat_id}.png"
        save_schedule_image(table, temp_filename)

        caption = "📅 Текущее расписание смен\n✅ - работаете\n❌ - могли бы работать"

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
            text=f"⚠️ Не удалось загрузить расписание: {error_msg}"
        )