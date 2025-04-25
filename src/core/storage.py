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

def load_shifts():
    if os.path.exists("data/shifts.json"):
        with open("data/shifts.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return DEFAULT_SHIFTS.copy()

def save_shifts(shifts):
    with open("data/shifts.json", "w", encoding="utf-8") as f:
        json.dump(shifts, f, ensure_ascii=False, indent=2)

def load_admins():
    if os.path.exists("data/admins.json"):
        with open("data/admins.json", "r") as f:
            return json.load(f).get('admins', [])
    return []

def save_admin(chat_id):
    admins = load_admins()
    if str(chat_id) not in admins:
        admins.append(str(chat_id))
        with open("data/admins.json", "w") as f:
            json.dump({'data/admins': admins}, f)

def load_notification_time():
    if os.path.exists("config/notification_time.json"):
        with open("config/notification_time.json", "r") as f:
            return json.load(f)
    return {'hours': 21, 'minutes': 56, 'day': 2}  # По умолчанию среда 21:56

def save_notification_time(hours, minutes, day):
    with open("config/notification_time.json", "w") as f:
        json.dump({'hours': hours, 'minutes': minutes, 'day': day}, f)