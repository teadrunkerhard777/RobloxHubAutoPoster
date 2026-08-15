import json
import re


MIN_SCORE = 5
MAX_NEWS_ITEMS = 3


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


NOISE_PHRASES = (
    "TECH DIRECTOR",
    "NOTIFY",
    "EXPERIENCE NEW UPDATES",
    "ROLEPLAY WITH FRIENDS",
    "BUILD YOUR DREAM HOME",
    "TRADE AND COLLECT",
    "CREATE AN ARMY",
    "HELP YOU GET RICH"
)


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


def normalize_game_name(raw_name):
    upper_name = raw_name.upper()

    for marker, clean_name in GAME_NAMES.items():
        if marker in upper_name:
            return clean_name

    # На случай новой игры.
    name = re.sub(
        r"^\[[^\]]+\]\s*",
        "",
        raw_name
    )

    return name.strip()


def contains_noise(line):
    upper_line = line.upper()

    return any(
        phrase in upper_line
        for phrase in NOISE_PHRASES
    )


def extract_name_before_new(line):
    """
    Rocket Car - New vehicle with ...
    -> Rocket Car
    """

    match = re.match(
        r"^\s*(.+?)\s*[-–—]\s*NEW\s+",
        line,
        flags=re.IGNORECASE
    )

    if not match:
        return None

    value = match.group(1).strip()

    if not value:
        return None

    return value


def translate_news_line(line):
    line = line.strip()

    if not line:
        return None

    if contains_noise(line):
        return None

    upper = line.upper()

    # Просто заголовки.
    if upper in {
        "LATEST UPDATE",
        "LATEST UPDATE:",
        "UPDATE",
        "UPDATE:"
    }:
        return None

    object_name = extract_name_before_new(
        line
    )

    # ------------------------------------------------
    # Новый транспорт
    # ------------------------------------------------

    if "NEW VEHICLE" in upper:
        if object_name:
            text = (
                f"Появился {object_name} — "
                "новый транспорт"
            )
        else:
            text = (
                "В игру добавили новый транспорт"
            )

        details = []

        if "UNIQUE EFFECTS" in upper:
            details.append(
                "особыми эффектами"
            )

        if "SOUNDS" in upper:
            details.append(
                "звуками"
            )

        if "TEXTURE" in upper:
            details.append(
                "оформлением"
            )

        if details:
            text += " с " + ", ".join(
                details
            )

        text += "."

        if "VIP" in upper:
            text += (
                " Он доступен владельцам VIP."
            )

        return {
            "text": text,
            "kind": "vehicle",
            "specific": True
        }

    # ------------------------------------------------
    # Предметы
    # ------------------------------------------------

    if (
        "NEW ITEMS" in upper
        or "NEW ITEM" in upper
    ):
        if object_name:
            text = (
                f"Появился новый предмет — "
                f"{object_name}."
            )
        else:
            text = (
                "В игре появились новые предметы."
            )

        return {
            "text": text,
            "kind": "items",
            "specific": True
        }

    # ------------------------------------------------
    # Питомцы
    # ------------------------------------------------

    if (
        "NEW PETS" in upper
        or "NEW PET" in upper
    ):
        if object_name:
            text = (
                f"Появился новый питомец — "
                f"{object_name}."
            )
        else:
            text = (
                "В игру добавили новых питомцев."
            )

        return {
            "text": text,
            "kind": "pets",
            "specific": True
        }

    # ------------------------------------------------
    # Карта
    # ------------------------------------------------

    if "NEW MAP" in upper:
        if object_name:
            text = (
                f"Появилась новая карта — "
                f"{object_name}."
            )
        else:
            text = (
                "В игре появилась новая карта."
            )

        return {
            "text": text,
            "kind": "map",
            "specific": True
        }

    # ------------------------------------------------
    # Босс
    # ------------------------------------------------

    if "NEW BOSS" in upper:
        if object_name:
            text = (
                f"Появился новый босс — "
                f"{object_name}."
            )
        else:
            text = (
                "В игре появился новый босс."
            )

        return {
            "text": text,
            "kind": "boss",
            "specific": True
        }

    # ------------------------------------------------
    # Событие
    # ------------------------------------------------

    if (
        "NEW EVENT" in upper
        or re.search(
            r"\bEVENT\b",
            upper
        )
    ):
        return {
            "text": (
                "В игре началось новое событие."
            ),
            "kind": "event",
            "specific": True
        }

    # ------------------------------------------------
    # Задания
    # ------------------------------------------------

    if re.search(
        r"\bQUESTS?\b",
        upper
    ):
        return {
            "text": (
                "В игре появились новые задания."
            ),
            "kind": "quests",
            "specific": True
        }

    # ------------------------------------------------
    # Награды
    # ------------------------------------------------

    if re.search(
        r"\bREWARDS?\b",
        upper
    ):
        return {
            "text": (
                "В игре появились новые награды."
            ),
            "kind": "rewards",
            "specific": True
        }

    # ------------------------------------------------
    # Сезон
    # ------------------------------------------------

    if "SEASON" in upper:
        return {
            "text": (
                "В игре стартовал новый сезон."
            ),
            "kind": "season",
            "specific": True
        }

    # ------------------------------------------------
    # Limited
    # ------------------------------------------------

    if "LIMITED" in upper:
        return {
            "text": (
                "Появился ограниченный "
                "по времени контент."
            ),
            "kind": "limited",
            "specific": True
        }

    # ------------------------------------------------
    # Generic update — только запасной вариант
    # ------------------------------------------------

    if "UPDATE" in upper:
        return {
            "text": (
                "В игре вышло новое обновление."
            ),
            "kind": "update",
            "specific": False
        }

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
    game = normalize_game_name(
        candidate.get(
            "game",
            "Roblox"
        )
    )

    results = []

    for line in get_news_lines(
        candidate
    ):
        translated = translate_news_line(
            line
        )

        if translated is not None:
            results.append(
                translated
            )

    if not results:
        return None

    # Если есть конкретная новость,
    # generic "вышло обновление" удаляем.
    specific_results = [
        result
        for result in results
        if result["specific"]
    ]

    if specific_results:
        results = specific_results

    unique_results = []

    for result in results:
        if result["text"] not in [
            item["text"]
            for item in unique_results
        ]:
            unique_results.append(
                result
            )

    if not unique_results:
        return None

    texts = [
        result["text"]
        for result in unique_results[:2]
    ]

    return {
        "game": game,
        "emoji": GAME_EMOJIS.get(
            game,
            "🎮"
        ),
        "score": candidate.get(
            "score",
            0
        ),
        "kind": unique_results[0][
            "kind"
        ],
        "specific": unique_results[0][
            "specific"
        ],
        "text": " ".join(texts)
    }


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


preview = []


for item in news_items:
    preview.append(
        f"{item['emoji']} "
        f"{item['game']}\n"
        f"{item['text']}"
    )


if not preview:
    preview.append(
        "Сегодня не нашлось достаточно "
        "подтверждённых игровых новостей."
    )


save_text(
    "generated_news_post_ru.txt",
    "\n\n".join(preview)
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
