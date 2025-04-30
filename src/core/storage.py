import json
import os
from pathlib import Path

DEFAULT_SHIFTS = {
    "Понедельник": 0,
    "Вторник": 0,
    "Среда": 0,
    "Четверг": 0,
    "Пятница": 0,
    "Суббота": 0,
    "Воскресенье": 0
}
def reset_shifts():
    """Сбрасывает слоты к значениям по умолчанию"""
    save_shifts(DEFAULT_SHIFTS.copy())

def load_shifts():
    if os.path.exists("../../data/shifts.json"):
        with open("../../data/shifts.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SHIFTS.copy()

def save_shifts(shifts):
    with open("../../data/shifts.json", "w", encoding="utf-8") as f:
        json.dump(shifts, f, ensure_ascii=False, indent=2)

def load_admins():
    if os.path.exists("../../data/admins.json"):
        with open("../../data/admins.json", "r") as f:
            return json.load(f).get('admins', [])
    return []

def load_notification_time():
    if os.path.exists("../../config/notification_time.json"):
        with open("../../config/notification_time.json", "r") as f:
            data = json.load(f)
            return data['hours'], data['minutes'], data['day']
    return 18, 0, 4  # Возвращаем значения по умолчанию, если файл не существует

def save_notification_time(hours, minutes, day):
    with open("../../config/notification_time.json", "w") as f:
        json.dump({'hours': hours, 'minutes': minutes, 'day': day}, f)

def save_schedule(schedule):
    """Сохраняет текущее расписание в файл"""
    with open("../../data/current_schedule.json", "w", encoding="utf-8") as f:
        json.dump(schedule, f, ensure_ascii=False, indent=2)

def load_schedule():
    """Загружает текущее расписание из файла"""
    if os.path.exists("../../data/current_schedule.json"):
        with open("../../data/current_schedule.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_exchange_offers_file():
    """Возвращает путь к файлу с предложениями обмена"""
    return Path(__file__).parent.parent.parent / "data" / "exchange_offers.json"

def save_exchange_offer(offer):
    """Сохраняет предложение обмена в файл"""
    print(f"Пытаюсь сохранить предложение: {offer}")
    file_path = get_exchange_offers_file()
    file_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # Загружаем существующие предложения
        if file_path.exists():
            with open(file_path, "r", encoding="utf-8") as f:
                offers = json.load(f)
        else:
            offers = []

        # Добавляем новое предложение
        offers.append(offer)

        # Сохраняем обратно
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(offers, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"Ошибка при сохранении предложения обмена: {e}")
        return False

def find_exchange_offer(from_user_id, to_user_id):
    """Находит предложение обмена по ID пользователей"""
    file_path = get_exchange_offers_file()

    if not file_path.exists():
        return None

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            offers = json.load(f)

        for offer in offers:
            if (offer.get('from_user') == from_user_id and
                    offer.get('to_user') == to_user_id and
                    offer.get('status') == 'pending'):
                return offer

    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Ошибка при поиске предложения обмена: {e}")

    return None

def remove_exchange_offer(offer_to_remove):
    """Удаляет предложение обмена"""
    file_path = get_exchange_offers_file()

    if not file_path.exists():
        return False

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            offers = json.load(f)

        # Удаляем предложение (сравниваем по всем полям)
        new_offers = [
            o for o in offers
            if not (o.get('from_user') == offer_to_remove.get('from_user') and
                    o.get('to_user') == offer_to_remove.get('to_user') and
                    o.get('day_to_give') == offer_to_remove.get('day_to_give') and
                    o.get('day_to_get') == offer_to_remove.get('day_to_get'))
        ]

        with open(file_path, "w", encoding="utf-8") as f: \
            json.dump(new_offers, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"Ошибка при удалении предложения обмена: {e}")
        return False