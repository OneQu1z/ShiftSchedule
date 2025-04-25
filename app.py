import streamlit as st
import pandas as pd
from google_utils import GoogleSheetsManager  # Измененный импорт
from scheduler import generate_schedule, build_schedule_table, count_shifts
from storage import load_shifts, save_shifts
from utils import save_schedule_image

# Инициализация менеджера Google Sheets
gs_manager = GoogleSheetsManager()

# Настройка страницы
st.set_page_config(page_title="График смен сотрудников", layout="wide")
st.title("📅 График смен сотрудников")

# Боковая панель для административных функций
with st.sidebar:
    st.header("Администрирование")
    if st.button("🧹 Полный сброс формы"):
        if gs_manager.clear_responses():
            st.success("Данные успешно очищены! Новые ответы будут добавляться с 2-й строки.")
            st.rerun()  # Обновляем страницу
        else:
            st.error("Ошибка при очистке данных. Проверьте логи.")

    st.markdown("---")
    st.info("""
    **Инструкция:**
    1. Настройте количество смен
    2. Нажмите "Сохранить"
    3. Нажмите "Составить график"
    """)

# Основной интерфейс
def main():
    # Загрузка данных
    try:
        # Получаем данные через менеджер
        data = gs_manager.get_clean_data()
        df = pd.DataFrame(data)

        # Проверка и обработка дубликатов ФИО
        if df["ФИО"].duplicated().any():
            st.warning("Обнаружены дубликаты ФИО. Добавляем идентификаторы...")
            df["ФИО"] = df["ФИО"].apply(lambda x: f"{x}_{pd.util.hash_pandas_object([x])[0]}")

        shifts = load_shifts()

        # Интерфейс настройки смен
        st.subheader("🛠 Настройка количества смен")
        updated = {}
        cols = st.columns(4)

        days_order = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
        for idx, day in enumerate(days_order):
            with cols[idx % 4]:
                updated[day] = st.number_input(
                    day,
                    min_value=0,
                    max_value=50,
                    value=shifts.get(day, 0),
                    step=1
                )

        if st.button("💾 Сохранить количество смен"):
            save_shifts(updated)
            st.success("Настройки сохранены!")

        if st.button("📋 Составить график"):
            if df.empty:
                st.error("Нет данных для формирования графика")
                return

            try:
                # Генерация расписания
                schedule, unfilled_days = generate_schedule(df, updated)
                availability = {row["ФИО"]: row["Дни"] for _, row in df.iterrows()}

                # Построение таблицы
                table = build_schedule_table(schedule, df["ФИО"].tolist(), availability)

                # Стилизация
                def highlight(val):
                    if val == "✅":
                        return "background-color: #c8e6c9; color: black; font-weight: bold"
                    elif val == "❌":
                        return "background-color: #ffcdd2; color: black; font-weight: bold"
                    return ""

                # Отображение результатов
                if unfilled_days:
                    st.warning("⚠ Не удалось заполнить все смены:")
                    for day, missing in unfilled_days:
                        st.markdown(f"- **{day}**: не хватает {missing} сотрудников")

                st.dataframe(table.style.applymap(highlight), use_container_width=True)

                # Генерация и скачивание изображения
                save_schedule_image(table, "schedule.png")
                st.image("schedule.png", use_container_width=True)

                with open("schedule.png", "rb") as f:
                    st.download_button(
                        "📥 Скачать график",
                        f,
                        file_name="График_смен.png",
                        mime="image/png"
                    )

                # Статистика по сменам
                shifts_count = count_shifts(schedule)
                stats = []
                for name in df["ФИО"]:
                    requested_days = df[df["ФИО"] == name]["Дни"].values[0]
                    total_requested = len(requested_days)
                    assigned = shifts_count.get(name, 0)
                    missed = total_requested - assigned
                    stats.append({
                        "Сотрудник": name,
                        "Запрошено смен": total_requested,
                        "Назначено смен": assigned,
                        "Не назначено": missed,
                    })

                st.subheader("📊 Статистика по сотрудникам")
                st.dataframe(
                    pd.DataFrame(stats).sort_values("Не назначено", ascending=False),
                    use_container_width=True
                )

            except Exception as e:
                st.error(f"Ошибка при формировании графика: {str(e)}")


    except Exception as e:

        st.error(f"Ошибка при загрузке данных: {str(e)}")

if __name__ == "__main__":
    main()