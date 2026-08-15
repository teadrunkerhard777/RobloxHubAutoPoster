import json
import re


MIN_SCORE = 5
MAX_NEWS_ITEMS = 2


NOISE_PHRASES = (
    "TECH DIRECTOR",
    "NOTIFY",
    "EXPERIENCE NEW UPDATES",
    "ROLEPLAY WITH FRIENDS",
    "BUILD YOUR DREAM HOME",
    "TRADE AND COLLECT",
    "CURRENTLY",
    "CREATE AN ARMY",
    "HELP YOU GET RICH"
)


GAME_EMOJIS = {
    "Blox Fruits": "🍈",
    "RIVALS": "🔫",
    "99 Nights in the Forest": "🌲",
    "Steal a Brainrot": "🧠",
    "Brookhaven": "🏡",
    "Adopt Me!": "🐾",
    "Grow a Garden": "🌱",
    "Dress To Impress": "👗",
    "Pet Simulator 99": "🐶",
    "Blade Ball": "⚔️"
}


def load_json(filename):
    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(filename, data):
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def save_text(filename, text):
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        file.write(text)


def clean_game_name(name):
    name = re.sub(
        r"^\[[^\]]+\]\s*",
        "",
        name
    )

    return name.strip()


def contains_noise(line):
    upper_line = line.upper()

    return any(
        phrase in upper_line
        for phrase in NOISE_PHRASES
    )


def extract_name_before_dash(line):
    match = re.match(
        r"^\s*(.+?)\s*[-–—]\s*NEW\s+",
        line,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    name = match.group(1).strip()

    if not name:
        return None

    return name


def translate_news_line(line):
    line = line.strip()

    if not line:
        return None

    if contains_noise(line):
        return None

    upper = line.upper()

    # Заголовки сами по себе не являются новостью.
    if upper in {
        "LATEST UPDATE:",
        "LATEST UPDATE",
        "UPDATE:",
        "UPDATE"
    }:
        return None

    item_name = extract_name_before_dash(
        line
    )

    # ----------------------------------------------
    # Новый транспорт
    # ----------------------------------------------

    if "NEW VEHICLE" in upper:
        if item_name:
            text = (
                f"Появился {item_name} — "
                "новый транспорт."
            )
        else:
            text = (
                "В игру добавили новый транспорт."
            )

        if (
            "UNIQUE EFFECTS" in upper
            or "SOUNDS" in upper
            or "TEXTURE" in upper
        ):
            text = text.rstrip(".")
            text += (
                " с особыми эффектами, "
                "звуками и оформлением."
            )

        if "VIP" in upper:
            text += " Доступен владельцам VIP."

        return text

    # ----------------------------------------------
    # Новые предметы
    # ----------------------------------------------

    if (
        "NEW ITEMS" in upper
        or "NEW ITEM" in upper
    ):
        if item_name:
            return (
                f"Появился новый предмет — "
                f"{item_name}."
            )

        return "Появились новые предметы."

    # ----------------------------------------------
    # Новые питомцы
    # ----------------------------------------------

    if (
        "NEW PETS" in upper
        or "NEW PET" in upper
    ):
        if item_name:
            return (
                f"Появился новый питомец — "
                f"{item_name}."
            )

        return "В игру добавили новых питомцев."

    # ----------------------------------------------
    # Новая карта
    # ----------------------------------------------

    if "NEW MAP" in upper:
        if item_name:
            return (
                f"Появилась новая карта — "
                f"{item_name}."
            )

        return "В игре появилась новая карта."

    # ----------------------------------------------
    # Новый босс
    # ----------------------------------------------

    if "NEW BOSS" in upper:
        if item_name:
            return (
                f"Появился новый босс — "
                f"{item_name}."
            )

        return "В игре появился новый босс."

    # ----------------------------------------------
    # Событие
    # ----------------------------------------------

    if (
        "NEW EVENT" in upper
        or re.search(
            r"\bEVENT\b",
            upper
        )
    ):
        return "В игре проходит новое событие."

    # ----------------------------------------------
    # Задания
    # ----------------------------------------------

    if (
        "NEW QUEST" in upper
        or re.search(
            r"\bQUESTS?\b",
            upper
        )
    ):
        return "В игре появились новые задания."

    # ----------------------------------------------
    # Награды
    # ----------------------------------------------

    if re.search(
        r"\bREWARDS?\b",
        upper
    ):
        return "В игру добавили новые награды."

    # ----------------------------------------------
    # Ограниченный контент
    # ----------------------------------------------

    if "LIMITED" in upper:
        return (
            "Появился ограниченный по времени "
            "контент."
        )

    # ----------------------------------------------
    # Новый сезон
    # ----------------------------------------------

    if "SEASON" in upper:
        return "В игре стартовал новый сезон."

    # ----------------------------------------------
    # Просто UPDATE используем только как fallback
    # ----------------------------------------------

    if "UPDATE" in upper:
        return "В игре вышло новое обновление."

    return None


def get_news_lines(candidate):
    analysis = candidate.get(
        "official_description_analysis",
        {}
    )

    return analysis.get(
        "news_lines",
        []
    )


def build_item(candidate):
    game = clean_game_name(
        candidate.get(
            "game",
            "Roblox"
        )
    )

    score = candidate.get(
        "score",
        0
    )

    lines = get_news_lines(
        candidate
    )

    translated = []

    for line in lines:
        result = translate_news_line(
            line
        )

        if (
            result
            and result not in translated
        ):
            translated.append(result)

    if not translated:
        return None

    # Если нашли конкретную новость,
    # убираем бесполезное "вышло обновление".
    specific = [
        text
        for text in translated
        if text != "В игре вышло новое обновление."
    ]

    if specific:
        translated = specific

    text = " ".join(
        translated[:2]
    )

    return {
        "game": game,
        "emoji": GAME_EMOJIS.get(
            game,
            "🎮"
        ),
        "score": score,
        "text": text
    }


verified_news = load_json(
    "verified_news.json"
)


candidates = [
    candidate
    for candidate in verified_news
    if candidate.get("score", 0) >= MIN_SCORE
]


candidates.sort(
    key=lambda item: item.get(
        "score",
        0
    ),
    reverse=True
)


news_items = []
used_games = set()


for candidate in candidates:
    item = build_item(
        candidate
    )

    if item is None:
        continue

    if item["game"] in used_games:
        continue

    news_items.append(
        item
    )

    used_games.add(
        item["game"]
    )

    if len(news_items) == MAX_NEWS_ITEMS:
        break


output = {
    "items": news_items
}


save_json(
    "generated_news_data_ru.json",
    output
)


# Оставляем txt как удобный файл-превью.
preview_blocks = []


for item in news_items:
    preview_blocks.append(
        f"{item['emoji']} {item['game']}\n"
        f"{item['text']}"
    )


if preview_blocks:
    preview = "\n\n".join(
        preview_blocks
    )
else:
    preview = (
        "Сегодня не нашлось достаточно "
        "подтверждённых игровых новостей."
    )


save_text(
    "generated_news_post_ru.txt",
    preview
)


print()
print(
    f"Подготовлено новостей: "
    f"{len(news_items)}"
)

for item in news_items:
    print(
        f"- {item['game']}: "
        f"{item['text']}"
    )
