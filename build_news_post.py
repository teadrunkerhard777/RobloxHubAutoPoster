import json


MIN_SCORE = 5
MAX_NEWS_ITEMS = 4


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def get_best_news(candidates):
    suitable = [
        item
        for item in candidates
        if item.get("score", 0) >= MIN_SCORE
    ]

    suitable.sort(
        key=lambda item: item.get("score", 0),
        reverse=True
    )

    return suitable[:MAX_NEWS_ITEMS]


def get_news_lines(item):
    analysis = item.get(
        "official_description_analysis",
        {}
    )

    lines = analysis.get(
        "news_lines",
        []
    )

    return lines[:3]


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

        news_lines = get_news_lines(
            item
        )

        if news_lines:
            for line in news_lines:
                parts.append(
                    f"• {line}"
                )

        else:
            parts.append(
                "• Игра недавно обновлялась, "
                "но подробности пока не подтверждены."
            )

        parts.append("")

    parts.append("🎮 Roblox Hub")

    return "\n".join(parts)


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
    f"Подходящих новостей: "
    f"{len(best_news)}"
)

print()
print("Готовый пост:")
print()
print(post_text)
