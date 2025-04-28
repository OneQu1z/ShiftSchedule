import os
import pandas as pd
from telegram.ext import ContextTypes

from src.core.google_utils import GoogleSheetsManager
from src.core.scheduler import generate_schedule, build_schedule_table
from src.core.storage import load_shifts
from src.utils.utils import save_schedule_image
import logging

gs_manager = GoogleSheetsManager()
logger = logging.getLogger(__name__)

async def auto_send_schedule(context: ContextTypes.DEFAULT_TYPE):
    try:
        for chat_id in context.bot_data['user_manager'].load_pen_users():
            try:
                await send_schedule_to_user(chat_id, context)
            except Exception as e:
                logger.error(f"Ошибка отправки {chat_id}: {e}")
    except Exception as e:
        logger.error(f"Ошибка рассылки: {e}")

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