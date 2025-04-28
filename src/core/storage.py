import json
import os

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

def save_admin(chat_id):
    admins = load_admins()
    if str(chat_id) not in admins:
        admins.append(str(chat_id))
        with open("../../data/admins.json", "w") as f:
            json.dump({'data/admins': admins}, f)

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

def save_exchange_offer(offer):
    """Сохраняет предложение обмена"""
    offers = load_exchange_offers()
    offers.append(offer)
    with open("../../data/exchange_offers.json", "w", encoding="utf-8") as f:
        json.dump(offers, f, ensure_ascii=False, indent=2)

def load_exchange_offers():
    """Загружает все предложения обмена"""
    if os.path.exists("../../data/exchange_offers.json"):
        with open("../../data/exchange_offers.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def find_exchange_offer(from_chat_id, to_chat_id):
    """Находит предложение обмена"""
    offers = load_exchange_offers()
    for offer in offers:
        if offer['from_chat_id'] == from_chat_id and offer['to_chat_id'] == to_chat_id and offer['status'] == 'pending':
            return offer
    return None

def remove_exchange_offer(offer):
    """Удаляет предложение обмена"""
    offers = load_exchange_offers()
    new_offers = [o for o in offers if not (
            o['from_chat_id'] == offer['from_chat_id'] and
            o['to_chat_id'] == offer['to_chat_id'] and
            o['from_shift'] == offer['from_shift'] and
            o['to_shift'] == offer['to_shift']
    )]
    with open("../../data/exchange_offers.json", "w", encoding="utf-8") as f:
        json.dump(new_offers, f, ensure_ascii=False, indent=2)