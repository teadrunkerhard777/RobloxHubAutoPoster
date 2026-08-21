import json


MIN_SCORE = 5
MAX_NEWS_ITEMS = 3


STRONG_NEWS_PHRASES = [
    "LATEST UPDATE",
    "NEW ITEM",
    "NEW ITEMS",
    "NEW VEHICLE",
    "NEW PET",
    "NEW PETS",
    "NEW MAP",
    "NEW BOSS",
    "NEW EVENT",
    "LIMITED",
    "EVENT",
    "QUEST",
    "REWARD",
    "SEASON",
    "UPDATE"
]


NOISE_PHRASES = [
    "TECH DIRECTOR",
    "NOTIFY",
    "EXPERIENCE NEW UPDATES",
    "ROLEPLAY WITH FRIENDS",
    "BUILD YOUR DREAM HOME",
    "TRADE AND COLLECT",
    "CURRENTLY",
    "CREATE AN ARMY",
    "HELP YOU GET RICH"
]


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def contains_any(text, phrases):
    text_upper = text.upper()

    return any(
        phrase in text_upper
        for phrase in phrases
    )


def is_noise_line(line):
    return contains_any(
        line,
        NOISE_PHRASES
    )


def is_news_line(line):
    if is_noise_line(line):
        return False

    return contains_any(
        line,
        STRONG_NEWS_PHRASES
    )


def get_clean_news_lines(item):
    analysis = item.get(
        "official_description_analysis",
        {}
    )

    lines = analysis.get(
        "news_lines",
        []
    )

    clean_lines = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if is_news_line(line):
            clean_lines.append(
                line
            )

    return clean_lines[:3]


def get_best_news(candidates):
    suitable = []

    for item in candidates:
        score = item.get(
            "score",
            0
        )

        if score < MIN_SCORE:
            continue

        clean_lines = get_clean_news_lines(
            item
        )

        if not clean_lines:
            continue

        item_copy = item.copy()

        item_copy[
            "clean_news_lines"
        ] = clean_lines

        suitable.append(
            item_copy
        )

    suitable.sort(
        key=lambda item: item.get(
            "score",
            0
        ),
        reverse=True
    )

    return suitable[:MAX_NEWS_ITEMS]


def build_news_post(news_items):
    if not news_items:
        return (
            "🎮 Roblox Hub — утренняя сводка\n\n"
            "Сегодня пока нет достаточно "
            "подтверждённых свежих новостей.\n\n"
            "Лучше без новости, чем с выдуманной 🙂\n\n"
            "🎮 Roblox Hub"
        )

    parts = [
        "🎮 Roblox Hub — утренняя сводка",
        ""
    ]

    for index, item in enumerate(
        news_items,
        start=1
    ):
        parts.append(
            f"{index}. 🔥 {item['game']}"
        )

        for line in item[
            "clean_news_lines"
        ]:
            parts.append(
                f"• {line}"
            )

        parts.append("")

    parts.append(
        "🎮 Roblox Hub"
    )

    return "\n".join(
        parts
    )


verified_news = load_json(
    "verified_news.json",
    []
)


best_news = get_best_news(
    verified_news
)


post_text = build_news_post(
    best_news
)


with open(
    "generated_news_post.txt",
    "w",
    encoding="utf-8"
) as file:
    file.write(
        post_text
    )


print(
    f"Подходящих новостей после фильтрации: "
    f"{len(best_news)}"
)

print()
print("Готовый пост:")
print()
print(post_text)
