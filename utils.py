import matplotlib.pyplot as plt
import pandas as pd
import matplotlib.font_manager as fm

# Пути к шрифтам
emoji_font_path = "C:/Windows/Fonts/seguiemj.ttf"  # Шрифт для эмодзи
cyrillic_font_path = "C:/Windows/Fonts/arial.ttf"  # Шрифт для кириллицы

# Загрузка шрифтов
emoji_font = fm.FontProperties(fname=emoji_font_path, size=12)
cyrillic_font = fm.FontProperties(fname=cyrillic_font_path, size=12)


# Функция для определения, содержит ли строка эмодзи
def contains_emoji(text):
    return any(char in "❌✅" for char in text)


# Код для генерации изображения с графиком
def save_schedule_image(schedule_df: pd.DataFrame, filename="schedule.png"):
    fig, ax = plt.subplots(figsize=(12, len(schedule_df) * 0.5 + 2))
    ax.axis("off")

    table = ax.table(
        cellText=schedule_df.values,
        colLabels=schedule_df.columns,
        rowLabels=schedule_df.index,
        loc="center",
        cellLoc="center"
    )

    table.auto_set_font_size(False)

    # Обработка ячеек таблицы
    for key, cell in table.get_celld().items():
        val = cell.get_text().get_text()

        # Установка шрифта в зависимости от содержания (эмодзи или кириллица)
        if contains_emoji(val):
            cell.get_text().set_fontproperties(emoji_font)  # Шрифт для эмодзи
        else:
            cell.get_text().set_fontproperties(cyrillic_font)  # Шрифт для кириллицы

        # Установка размера шрифта
        cell.get_text().set_fontsize(10)

        # Установка цвета фона в зависимости от значений
        if val == "✅":
            cell.set_facecolor("#c8e6c9")
        elif val == "❌":
            cell.set_facecolor("#ffcdd2")

    plt.tight_layout()
    plt.savefig(filename, dpi=300)
    plt.close()
