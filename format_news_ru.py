import json


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def save_text(filename, text):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(text)


def translate_line(game, line):
    line_upper = line.upper()

    if game.startswith("Brookhaven"):
        if "ROCKET CAR" in line_upper:
            return (
                "🚀 В Brookhaven добавили Rocket Car — "
                "новую машину с особыми эффектами, звуками "
                "и текстурой. Она доступна владельцам VIP."
            )

        if "LATEST UPDATE" in line_upper:
            return None

    if "Dress To Impress" in game:
        if "NEW ITEMS" in line_upper:
            return (
                "👗 В Dress To Impress появились новые предметы. "
                "Подробности разработчики пока не расписали."
            )

    return None


def build_russian_news():
    verified_news = load_json(
        "verified_news.json",
        []
    )

    parts = [
        "🎮 Roblox Hub — утренняя сводка",
        ""
    ]

    news_count = 0

    for item in verified_news:
        analysis = item.get(
            "official_description_analysis",
            {}
        )

        lines = analysis.get(
            "news_lines",
            []
        )

        translated_lines = []

        for line in lines:
            translated = translate_line(
                item["game"],
                line
            )

            if translated:
                translated_lines.append(
                    translated
                )

        if not translated_lines:
            continue

        news_count += 1

        parts.append(
            f"{news_count}. 🔥 {item['game']}"
        )

        for translated_line in translated_lines:
            parts.append(
                f"• {translated_line}"
            )

        parts.append("")

    if news_count == 0:
        return (
            "🎮 Roblox Hub — утренняя сводка\n\n"
            "Сегодня пока нет достаточно подтверждённых "
            "свежих новостей.\n\n"
            "Лучше без новости, чем с выдуманной 🙂\n\n"
            "🎮 Roblox Hub"
        )

    parts.append(
        "🎮 Roblox Hub"
    )

    return "\n".join(parts)


post_text = build_russian_news()

save_text(
    "generated_news_post_ru.txt",
    post_text
)

print("Готовый русский пост:")
print()
print(post_text)
