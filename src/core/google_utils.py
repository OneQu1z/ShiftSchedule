import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging
from typing import List, Dict, Any, Optional

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class GoogleSheetsManager:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(GoogleSheetsManager, cls).__new__(cls)
            cls._instance.sheet = cls._instance._connect()
        return cls._instance

    def __init__(self):
        pass

    def _connect(self) -> Optional[gspread.Worksheet]:
        """Подключение к Google Sheets с детальным логированием."""
        try:
            scope = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive"
            ]
            creds = ServiceAccountCredentials.from_json_keyfile_name("../../config/credentials.json", scope)
            client = gspread.authorize(creds)

            # Проверка существования таблицы "Ответы"
            try:
                spreadsheet = client.open("Ответы")
                logger.info(f"Таблица 'Ответы' найдена. Доступные листы: {[ws.title for ws in spreadsheet.worksheets()]}")
            except gspread.SpreadsheetNotFound:
                logger.error("Таблица 'Ответы' не найдена. Проверьте название и доступ.")
                return None

            # Попытка подключения к листу
            try:
                worksheet = spreadsheet.worksheet("Form_Responses1")
                logger.info(f"Успешно подключено к листу: {worksheet.title}")
                return worksheet
            except gspread.WorksheetNotFound:
                logger.error("Лист 'Form_Responses1' не найден. Доступные листы: "
                             f"{[ws.title for ws in spreadsheet.worksheets()]}")
                return None

        except Exception as e:
            logger.error(f"Критическая ошибка подключения: {str(e)}", exc_info=True)
            return None

    def get_clean_data(self) -> List[Dict[str, Any]]:
        """Получает данные, игнорируя полностью пустые строки и очищенные строки"""
        if not self.sheet:
            return []

        try:
            # Получаем все строки (включая пустые)
            all_rows = self.sheet.get_all_values()

            # Фильтруем строки:
            # 1. Пропускаем заголовок (первую строку)
            # 2. Оставляем только строки, где есть хотя бы одно заполненное поле
            clean_data = []
            headers = all_rows[0] if all_rows else []

            for row in all_rows[1:]:
                if any(cell.strip() for cell in row):  # Если есть хоть одно непустое значение
                    clean_data.append(dict(zip(headers, row)))

            # Дополнительная проверка структуры
            if clean_data and not all(col in headers for col in ["ФИО", "Дни"]):
                logger.error("Отсутствуют обязательные столбцы 'ФИО' или 'Дни'")
                return []

            logger.info(f"Загружено {len(clean_data)} записей (пустые строки игнорируются)")
            return clean_data

        except Exception as e:
            logger.error(f"Ошибка загрузки данных: {str(e)}", exc_info=True)
            return []

    def clear_responses(self) -> bool:
        """Очищает все данные в листе, кроме заголовков"""
        if not self.sheet:
            return False

        try:
            # Получаем все данные
            all_values = self.sheet.get_all_values()

            # Если есть только заголовок или вообще нет данных
            if len(all_values) <= 1:
                return True

            # Определяем диапазон для очистки (со 2-й строки до последней)
            range_to_clear = f"A2:Z{len(all_values)}"

            # Очищаем данные
            self.sheet.batch_clear([range_to_clear])
            logger.info(f"Очищено {len(all_values) - 1} строк")
            return True

        except Exception as e:
            logger.error(f"Ошибка при очистке листа: {e}")
            return False

