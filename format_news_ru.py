import json
import re


MIN_SCORE = 5
MAX_NEWS_ITEMS = 4


RULES = [
    {
        "keywords": ["NEW VEHICLE"],
        "template": "🚗 В {game} появился новый транспорт."
    },
    {
        "keywords": ["NEW ITEMS", "NEW ITEM"],
        "template": "🎁 В {game} появились новые предметы."
    },
    {
        "keywords": ["NEW PETS", "NEW PET"],
        "template": "🐾 В {game} появились новые питомцы."
    },
    {
        "keywords": ["NEW MAP"],
        "template": "🗺 В {game} появилась новая карта."
    },
    {
        "keywords": ["NEW BOSS"],
        "template": "👾 В {game} появился новый босс."
    },
    {
        "keywords": ["NEW EVENT", "EVENT"],
        "template": "🎉 В {game} началось новое событие."
    },
    {
        "keywords": ["QUEST"],
        "template": "📜 В {game} появились новые задания."
    },
    {
        "keywords": ["REWARD"],
        "template": "🎁 В {game} появились новые награды."
    },
    {
        "keywords": ["LIMITED"],
        "template": "⏳ В {game} появился ограниченный по времени контент."
    },
    {
        "keywords": ["UPDATE"],
        "template": "🔥 В {game} вышло обновление."
    }
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


def save_text(filename, text):
    with open(filename, "w", encoding="utf-8") as file:
        file.write(text)


def contains_noise(text):
    text_upper = text.upper()

    return any(
        phrase in text_upper
        for phrase in NOISE_PHRASES
    )


def find_rule(text):
    text_upper = text.upper()

    for rule in RULES:
        for keyword in rule["keywords"]:
            if keyword in text_upper:
                return rule

    return None


def extract_named_content(line):
    patterns = [
        r"NEW VEHICLE[:\s-]+(.+)",
        r"NEW ITEM[S]?[:\s-]+(.+)",
        r"NEW PET[S]?[:\s-]+(.+)",
        r"NEW BOSS[:\s-]+(.+)",
        r"NEW MAP[:\s-]+(.+)"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            line,
            flags=re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

    return None


def clean_game_name(game):
    game = re.sub(
        r"^\[[^\]]+\]\s*",
        "",
        game
    )

    return game.strip()


def build_item_text(item):
    analysis = item.get(
        "official_description_analysis",
        {}
    )

    lines = analysis.get(
        "news_lines",
        []
    )

    game = clean_game_name(
        item["game"]
    )

    result = []

    used_templates = set()

    for line in lines:
        line = line.strip()

        if not line:
            continue

        if contains_noise(line):
            continue

        rule = find_rule(line)

        if not rule:
            continue

        template = rule["template"]

        if template in used_templates:
            continue

        text = template.format(
            game=game
        )

        named_content = extract_named_content(
            line
        )

        if named_content:
            text += (
                f" Разработчики упоминают: "
                f"{named_content}"
            )

        result.append(text)

        used_templates.add(
            template
        )

    return result[:2]


def get_best_news(items):
    news = []

    for item in items:
        if item.get("score", 0) < MIN_SCORE:
            continue

        texts = build_item_text(
            item
        )

        if not texts:
            continue

        news.append(
            {
                "game": clean_game_name(
                    item["game"]
                ),
                "score": item["score"],
                "texts": texts
            }
        )

    news.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return news[:MAX_NEWS_ITEMS]


def build_post(news_items):
    if not news_items:
        return (
            "🎮 Roblox Hub — утренняя сводка\n\n"
            "Сегодня пока нет достаточно подтверждённых "
            "свежих новостей.\n\n"
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

        for text in item["texts"]:
            parts.append(
                f"• {text}"
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

post_text = build_post(
    best_news
)

save_text(
    "generated_news_post_ru.txt",
    post_text
)


print(
    f"Подходящих новостей: "
    f"{len(best_news)}"
)

print()
print("Готовый русский пост:")
print()
print(post_text)
