from collections import defaultdict
import pandas as pd
import logging

# Настройка логгера
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_schedule(df: pd.DataFrame, shifts_per_day: dict):
    """Генерирует расписание смен"""
    # Проверка входных данных
    if df.empty or "ФИО" not in df.columns or "Дни" not in df.columns:
        raise ValueError("Некорректные входные данные")

    employees = df["ФИО"].tolist()
    availability = {row["ФИО"]: row["Дни"] for _, row in df.iterrows()}

    total_shifts = sum(shifts_per_day.values())
    average_shifts = total_shifts // len(employees) if employees else 0

    schedule = defaultdict(list)
    shifts_count = {name: 0 for name in employees}

    # Первичное распределение
    for day, required in shifts_per_day.items():
        if not day:  # Пропускаем пустые дни
            continue

        available_today = [emp for emp in employees if day in availability.get(emp, [])]
        preferred = [emp for emp in available_today if shifts_count[emp] < average_shifts]
        preferred.sort(key=lambda name: shifts_count[name])
        assigned = preferred[:required]

        if len(assigned) < required:
            remaining_needed = required - len(assigned)
            others = [emp for emp in available_today if emp not in assigned]
            others.sort(key=lambda name: shifts_count[name])
            assigned += others[:remaining_needed]

        schedule[day] = assigned
        for name in assigned:
            shifts_count[name] += 1

    # Финальная проверка незаполненных смен
    unfilled_days = []
    for day, required in shifts_per_day.items():
        if day:  # Проверяем только непустые дни
            current_shifts = len(schedule.get(day, []))
            if current_shifts < required:
                unfilled_days.append((day, required - current_shifts))  # Исправленная строка

    return schedule, unfilled_days


def build_schedule_table(schedule: dict, employee_names: list, availability: dict = None) -> pd.DataFrame:
    """Строит таблицу расписания"""
    days = list(schedule.keys())
    table = pd.DataFrame(index=employee_names, columns=days)

    for day in days:
        for name in employee_names:
            if name in schedule[day]:
                table.at[name, day] = "✅"
            elif availability and day in availability.get(name, []):
                table.at[name, day] = "❌"
            else:
                table.at[name, day] = ""

    return table.fillna("")