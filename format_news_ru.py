import json
import re

from datetime import datetime, timedelta, timezone


MIN_SCORE = 5
MAX_NEWS_ITEMS = 3

LOCAL_TIMEZONE = timezone(
    timedelta(hours=5)
)


GAME_NAMES = {
    "STEAL A BRAINROT": "Steal a Brainrot",
    "99 NIGHTS IN THE FOREST": "99 Nights in the Forest",
    "BLOX FRUITS": "Blox Fruits",
    "BROOKHAVEN": "Brookhaven",
    "ADOPT ME": "Adopt Me!",
    "RIVALS": "RIVALS",
    "GROW A GARDEN": "Grow a Garden",
    "DRESS TO IMPRESS": "Dress To Impress",
    "PET SIMULATOR 99": "Pet Simulator 99",
    "BLADE BALL": "Blade Ball"
}


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


def load_json(filename, default=None):
    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except FileNotFoundError:
        if default is not None:
            return default

        raise


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


def normalize_game_name(raw_name):
    upper_name = raw_name.upper()

    for marker, clean_name in GAME_NAMES.items():
        if marker in upper_name:
            return clean_name

    return raw_name.strip()


# --------------------------------------------------
# Извлечение конкретных деталей
# --------------------------------------------------

def extract_update_number(text):
    match = re.search(
        r"\bUPDATE\s*#?\s*(\d+)\b",
        text,
        flags=re.IGNORECASE
    )

    if match:
        return match.group(1)

    return None


def extract_event_name(text):
    """
    Пример:
    UPDATE 21 - The first ever RIVALS Summer Event is here!
    -> Summer Event
    """

    patterns = [
        r"\b([A-Za-z0-9' ]+Summer Event)\b",
        r"\b([A-Za-z0-9' ]+Halloween Event)\b",
        r"\b([A-Za-z0-9' ]+Winter Event)\b",
        r"\b([A-Za-z0-9' ]+Christmas Event)\b",
        r"\b([A-Za-z0-9' ]+Easter Event)\b",
        r"\b([A-Za-z0-9' ]+Anniversary Event)\b"
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        if match:
            value = match.group(1).strip()

            # "The first ever RIVALS Summer Event"
            # не нужен целиком.
            if "SUMMER EVENT" in value.upper():
                return "Summer Event"

            if "HALLOWEEN EVENT" in value.upper():
                return "Halloween Event"

            if "WINTER EVENT" in value.upper():
                return "Winter Event"

            if "CHRISTMAS EVENT" in value.upper():
                return "Christmas Event"

            if "EASTER EVENT" in value.upper():
                return "Easter Event"

            if "ANNIVERSARY EVENT" in value.upper():
                return "Anniversary Event"

            return value

    return None


def extract_name_before_dash(text):
    match = re.match(
        r"^\s*(.+?)\s*[-–—]\s*(?:NEW|UPDATE)",
        text,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    value = match.group(1).strip()

    if value:
        return value

    return None


# --------------------------------------------------
# Перевод одного факта
# --------------------------------------------------

def translate_fact(fact):
    prepared_summary = fact.get(
        "summary_ru"
    )

    if prepared_summary:
        return prepared_summary.strip()

    raw_text = fact.get(
        "text",
        ""
    ).strip()

    kind = fact.get(
        "kind",
        ""
    )

    upper = raw_text.upper()

    if not raw_text:
        return None

    # ------------------------------------------------
    # Контракты + эксклюзивные награды
    # ------------------------------------------------

    if (
        "CONTRACT" in upper
        and "EXCLUSIVE" in upper
        and "REWARD" in upper
    ):
        return (
            "Можно выполнять контракты "
            "и получать эксклюзивные награды."
        )

    # ------------------------------------------------
    # Просто контракты
    # ------------------------------------------------

    if "CONTRACT" in upper:
        return (
            "В игре появились контракты "
            "с дополнительными заданиями."
        )

    # ------------------------------------------------
    # Событие
    # ------------------------------------------------

    if kind == "event":
        event_name = extract_event_name(
            raw_text
        )

        update_number = extract_update_number(
            raw_text
        )

        if event_name and update_number:
            return (
                f"В Update {update_number} "
                f"проходит {event_name}."
            )

        if event_name:
            return (
                f"В игре проходит "
                f"{event_name}."
            )

        if update_number:
            return (
                f"В Update {update_number} "
                "стартовало новое событие."
            )

        return (
            "В игре проходит новое событие."
        )

    # ------------------------------------------------
    # Update с номером
    # ------------------------------------------------

    if kind == "update":
        update_number = extract_update_number(
            raw_text
        )

        if update_number:
            return (
                f"Вышло Update {update_number}."
            )

        return None

    # ------------------------------------------------
    # Транспорт
    # ------------------------------------------------

    if kind == "vehicle":
        object_name = extract_name_before_dash(
            raw_text
        )

        if object_name:
            text = (
                f"Появился {object_name} — "
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
                " У него есть особые эффекты, "
                "звуки и оформление."
            )

        if "VIP" in upper:
            text += (
                " Он доступен владельцам VIP."
            )

        return text

    # ------------------------------------------------
    # Предметы
    # ------------------------------------------------

    if kind == "items":
        object_name = extract_name_before_dash(
            raw_text
        )

        if object_name:
            return (
                f"Появился новый предмет — "
                f"{object_name}."
            )

        return (
            "В игре появились новые предметы."
        )

    # ------------------------------------------------
    # Питомцы
    # ------------------------------------------------

    if kind == "pets":
        object_name = extract_name_before_dash(
            raw_text
        )

        if object_name:
            return (
                f"Появился новый питомец — "
                f"{object_name}."
            )

        return (
            "В игре появились новые питомцы."
        )

    # ------------------------------------------------
    # Карта
    # ------------------------------------------------

    if kind == "map":
        object_name = extract_name_before_dash(
            raw_text
        )

        if object_name:
            return (
                f"Появилась новая карта — "
                f"{object_name}."
            )

        return (
            "В игре появилась новая карта."
        )

    # ------------------------------------------------
    # Босс
    # ------------------------------------------------

    if kind == "boss":
        object_name = extract_name_before_dash(
            raw_text
        )

        if object_name:
            return (
                f"Появился новый босс — "
                f"{object_name}."
            )

        return (
            "В игре появился новый босс."
        )

    # ------------------------------------------------
    # Сезон
    # ------------------------------------------------

    if kind == "season":
        return (
            "В игре стартовал новый сезон."
        )

    # ------------------------------------------------
    # Limited
    # ------------------------------------------------

    if kind == "limited":
        return (
            "Появился ограниченный "
            "по времени контент."
        )

    # ------------------------------------------------
    # Задания
    # ------------------------------------------------

    if kind == "quests":
        if (
            "REWARD" in upper
            or "EXCLUSIVE" in upper
        ):
            return (
                "Можно выполнять задания "
                "и получать специальные награды."
            )

        return (
            "В игре появились новые задания."
        )

    # ------------------------------------------------
    # Коды
    # ------------------------------------------------

    if kind == "code":
        return (
            "Появилась возможность получить "
            "бесплатную награду по коду."
        )

    return None


# --------------------------------------------------
# Сборка блока одной игры
# --------------------------------------------------

def build_item(candidate):
    game = normalize_game_name(
        candidate.get(
            "game",
            "Roblox"
        )
    )

    facts = candidate.get(
        "facts",
        []
    )

    if not facts:
        return None

    translated = []

    for fact in facts:
        text = translate_fact(
            fact
        )

        if (
            text
            and text not in translated
        ):
            translated.append(
                text
            )

    if not translated:
        return None

    # Не раздуваем один блок:
    # максимум две сильные конкретные фразы.
    translated = translated[:2]

    item = {
        "game": game,
        "emoji": GAME_EMOJIS.get(
            game,
            "🎮"
        ),
        "score": candidate.get(
            "score",
            0
        ),
        "text": " ".join(
            translated
        )
    }

    external_article = candidate.get(
        "external_news_article"
    )

    if external_article:
        item["external_article_url"] = (
            external_article.get("url")
        )

    return item


# --------------------------------------------------
# Основной запуск
# --------------------------------------------------

verified_news = load_json(
    "verified_news.json"
)


candidates = [
    candidate
    for candidate in verified_news
    if candidate.get(
        "score",
        0
    ) >= MIN_SCORE
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


save_json(
    "generated_news_data_ru.json",
    {
        "items": news_items
    }
)


# --------------------------------------------------
# История официальных статей
# --------------------------------------------------

external_history = load_json(
    "external_news_history.json",
    []
)

selected_date = datetime.now(
    LOCAL_TIMEZONE
).date().isoformat()


for item in news_items:
    article_url = item.get(
        "external_article_url"
    )

    if not article_url:
        continue

    existing_record = None

    for record in external_history:
        if record.get("url") == article_url:
            existing_record = record
            break

    if existing_record:
        existing_record[
            "selected_date"
        ] = selected_date
    else:
        external_history.append(
            {
                "url": article_url,
                "game": item["game"],
                "selected_date": selected_date
            }
        )


save_json(
    "external_news_history.json",
    external_history[-100:]
)


preview_blocks = []


for item in news_items:
    preview_blocks.append(
        f"{item['emoji']} "
        f"{item['game']}\n"
        f"{item['text']}"
    )


if preview_blocks:
    preview = "\n\n".join(
        preview_blocks
    )
else:
    preview = (
        "Сегодня нет достаточно "
        "содержательных игровых новостей."
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
