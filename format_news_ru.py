import json
import re

from external_news_facts import NEWS_MAX_AGE_DAYS
from news_post_formatting import format_fact_paragraph, join_fact_paragraphs

MIN_SCORE = 5
MAX_NEWS_ITEMS = 3
MAX_NEWS_ITEM_CHARS = 500

GAME_NAMES = {
    "STEAL A BRAINROT": "Steal a Brainrot",
    "99 NIGHTS IN THE FOREST": "99 Nights in the Forest",
    "BLOX FRUITS": "Blox Fruits",
    "BROOKHAVEN": "Brookhaven RP",
    "BROOKHAVEN RP": "Brookhaven RP",
    "STEAL AN EGG": "Steal An Egg",
    "ANIMAL HOSPITAL (ANOMALY)": "Animal Hospital (Anomaly)",
    "+1 SPEED KEYBOARD ESCAPE": "+1 Speed Keyboard Escape",
    "MURDER MYSTERY 2": "Murder Mystery 2",
    "ADOPT ME": "Adopt Me!",
    "RIVALS": "RIVALS",
    "GROW A GARDEN": "Grow a Garden",
    "DRESS TO IMPRESS": "Dress To Impress",
    "PET SIMULATOR 99": "Pet Simulator 99",
    "BLADE BALL": "Blade Ball",
}


GAME_EMOJIS = {
    "Blox Fruits": "🍈",
    "RIVALS": "🔫",
    "99 Nights in the Forest": "🌲",
    "Steal a Brainrot": "🧠",
    "Brookhaven": "🏡",
    "Brookhaven RP": "🏡",
    "Steal An Egg": "🥚",
    "Animal Hospital (Anomaly)": "🏥",
    "+1 Speed Keyboard Escape": "⌨️",
    "Murder Mystery 2": "🔪",
    "Adopt Me!": "🐾",
    "Grow a Garden": "🌱",
    "Dress To Impress": "👗",
    "Pet Simulator 99": "🐶",
    "Blade Ball": "⚔️",
}


def load_json(filename, default=None):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError:
        if default is not None:
            return default

        raise


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def save_text(filename, text):
    with open(filename, "w", encoding="utf-8") as file:
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
    match = re.search(r"\bUPDATE\s*#?\s*(\d+)\b", text, flags=re.IGNORECASE)

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
        r"\b([A-Za-z0-9' ]+Anniversary Event)\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)

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
    match = re.match(r"^\s*(.+?)\s*[-–—]\s*(?:NEW|UPDATE)", text, flags=re.IGNORECASE)

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
    prepared_summary = fact.get("summary_ru")

    if prepared_summary:
        return prepared_summary.strip()

    raw_text = fact.get("text", "").strip()

    kind = fact.get("kind", "")

    upper = raw_text.upper()

    if not raw_text:
        return None

    # ------------------------------------------------
    # Контракты + эксклюзивные награды
    # ------------------------------------------------

    if "CONTRACT" in upper and "EXCLUSIVE" in upper and "REWARD" in upper:
        return "Можно выполнять контракты " "и получать эксклюзивные награды."

    # ------------------------------------------------
    # Просто контракты
    # ------------------------------------------------

    if "CONTRACT" in upper:
        return "В игре появились контракты " "с дополнительными заданиями."

    # ------------------------------------------------
    # Событие
    # ------------------------------------------------

    if kind == "event":
        event_name = extract_event_name(raw_text)

        update_number = extract_update_number(raw_text)

        if event_name and update_number:
            return f"В Update {update_number} " f"проходит {event_name}."

        if event_name:
            return f"В игре проходит " f"{event_name}."

        if update_number:
            return f"В Update {update_number} " "стартовало новое событие."

        if " CASE" in upper or upper.endswith("CASE"):
            clean_name = re.sub(
                r"^[^A-Za-z0-9]+|[^A-Za-z0-9!?'& ]+$", "", raw_text
            ).strip()

            return f"В игре началось событие «{clean_name}»."

        return "В игре проходит новое событие."

    # ------------------------------------------------
    # Update с номером
    # ------------------------------------------------

    if kind == "update":
        update_number = extract_update_number(raw_text)

        if update_number:
            return f"Вышло Update {update_number}."

        topic_match = re.search(
            r"^\s*([^\-–—:]+?\bUPDATE)\s*[-–—:]", raw_text, flags=re.IGNORECASE
        )

        if topic_match:
            return f"Вышло обновление «{topic_match.group(1).strip()}»."

        return None

    # ------------------------------------------------
    # Транспорт
    # ------------------------------------------------

    if kind == "vehicle":
        object_name = extract_name_before_dash(raw_text)

        if object_name:
            text = f"Появился {object_name} — " "новый транспорт."
        else:
            text = "В игру добавили новый транспорт."

        if "UNIQUE EFFECTS" in upper or "SOUNDS" in upper or "TEXTURE" in upper:
            text = text.rstrip(".")
            text += " У него есть особые эффекты, " "звуки и оформление."

        if "VIP" in upper:
            text += " Он доступен владельцам VIP."

        return text

    # ------------------------------------------------
    # Предметы
    # ------------------------------------------------

    if kind == "items":
        object_name = extract_name_before_dash(raw_text)

        if object_name:
            return f"Появился новый предмет — " f"{object_name}."

        return "В игре появились новые предметы."

    # ------------------------------------------------
    # Питомцы
    # ------------------------------------------------

    if kind == "pets":
        egg_match = re.search(
            r"([^!\n]+?)\s+found in\s+([^!\n]+?\bEggs?)", raw_text, flags=re.IGNORECASE
        )

        if egg_match:
            return (
                f"Питомца {egg_match.group(1).strip()} теперь можно "
                f"найти в {egg_match.group(2).strip()}."
            )

        object_name = extract_name_before_dash(raw_text)

        if object_name:
            return f"Появился новый питомец — " f"{object_name}."

        return "В игре появились новые питомцы."

    # ------------------------------------------------
    # Карта
    # ------------------------------------------------

    if kind == "map":
        object_name = extract_name_before_dash(raw_text)

        if object_name:
            return f"Появилась новая карта — " f"{object_name}."

        return "В игре появилась новая карта."

    # ------------------------------------------------
    # Босс
    # ------------------------------------------------

    if kind == "boss":
        object_name = extract_name_before_dash(raw_text)

        if object_name:
            return f"Появился новый босс — " f"{object_name}."

        return "В игре появился новый босс."

    # ------------------------------------------------
    # Сезон
    # ------------------------------------------------

    if kind == "season":
        return "В игре стартовал новый сезон."

    # ------------------------------------------------
    # Limited
    # ------------------------------------------------

    if kind == "limited":
        return "Появился ограниченный " "по времени контент."

    # ------------------------------------------------
    # Задания
    # ------------------------------------------------

    if kind == "quests":
        if "REWARD" in upper or "EXCLUSIVE" in upper:
            return "Можно выполнять задания " "и получать специальные награды."

        return "В игре появились новые задания."

    # ------------------------------------------------
    # Коды
    # ------------------------------------------------

    if kind == "code":
        return "Появилась возможность получить " "бесплатную награду по коду."

    return None


# --------------------------------------------------
# Сборка блока одной игры
# --------------------------------------------------


def build_item(candidate):
    game = normalize_game_name(candidate.get("game", "Roblox"))

    facts = candidate.get("facts", [])

    if not facts:
        return None

    translated = []
    detail_translated = []
    title_translated = []

    ordered_facts = sorted(
        facts,
        key=lambda fact: (
            bool(fact.get("source_url")) and fact.get("kind") != "official_article",
            fact.get("value", 0),
            fact.get("kind") != "official_article",
        ),
        reverse=True,
    )

    for fact in ordered_facts:
        text = translate_fact(fact)

        if not text:
            continue

        text = format_fact_paragraph(fact, text)

        target = (
            title_translated
            if fact.get("kind") == "official_article"
            else detail_translated
        )

        if text not in target:
            target.append(text)

    # Главная строка объясняет событие, а следующие строки раскрывают его.
    # Держим структуру отдельно от готового текста: это не даёт форматтеру
    # снова потерять факты и позволяет будущим каналам использовать те же данные.
    headline = title_translated[0] if title_translated else None
    details = [text for text in detail_translated if text != headline][:3]

    if headline:
        translated.append(headline)
    translated.extend(details)

    if not translated:
        return None

    # Если источник объективно содержит только одну строку, публикуем одну.
    # Для подробной статьи оставляем не более четырёх подтверждённых строк и
    # сокращаем только удалением последнего факта, без обрыва имён или чисел.
    translated = translated[:4]
    while (
        len(translated) > 1
        and len(join_fact_paragraphs(translated)) > MAX_NEWS_ITEM_CHARS
    ):
        translated.pop()

    headline = translated[0]
    details = translated[1:]

    item = {
        "game": game,
        "emoji": GAME_EMOJIS.get(game, "🎮"),
        "score": candidate.get("score", 0),
        "headline": headline,
        "facts": details,
        "text": join_fact_paragraphs(translated),
    }

    player_action = next(
        (
            fact.get("player_action_ru")
            for fact in ordered_facts
            if fact.get("player_action_ru")
        ),
        None,
    )
    if player_action:
        item["player_action"] = player_action

    external_article = candidate.get("external_news_article")

    if external_article:
        item["external_article_url"] = external_article.get("url")
        if external_article.get("source_tier") == "B" and external_article.get(
            "publisher"
        ):
            # Tier B всегда остаётся явно атрибутированным, но источник не
            # встраивается в заголовок и не ломает русскую пунктуацию.
            item["source_attribution"] = f"Источник: {external_article['publisher']}"

    return item


def select_news_items(formatted_candidates, max_items=MAX_NEWS_ITEMS):
    """Selects unique games, preferring the 14-day pool globally.

    The 15–30 day emergency pool is considered only when no item from the
    primary window can be formatted. This keeps the fallback deterministic and
    makes the editorial rule independently testable.
    """

    primary_candidates = [entry for entry in formatted_candidates if not entry[2]]
    selection_pool = primary_candidates or formatted_candidates
    selection_pool = sorted(
        selection_pool,
        key=lambda entry: entry[0].get("pool") == "active",
        reverse=True,
    )
    news_items = []
    used_games = set()

    for _, item, _ in selection_pool:
        if item["game"] in used_games:
            continue

        news_items.append(item)
        used_games.add(item["game"])

        if len(news_items) == max_items:
            break

    return news_items


# --------------------------------------------------
# Основной запуск
# --------------------------------------------------

verified_news = load_json("verified_news.json")


candidates = [
    candidate for candidate in verified_news if candidate.get("score", 0) >= MIN_SCORE
]
candidates.sort(
    key=lambda item: (item.get("pool") == "active", item.get("score", 0)),
    reverse=True,
)

# Форматируем до выбора окна: официальный EN-факт не должен молча исчезнуть
# между verified и formatted_ru. Аварийные 15–30 дней используются только
# когда ни один кандидат основного 14-дневного окна не форматируется.
formatted_candidates = []

for candidate in candidates:
    item = build_item(candidate)
    if item is None:
        continue

    article = candidate.get("external_news_article") or {}
    age_days = article.get("age_days")
    is_emergency = isinstance(age_days, (int, float)) and age_days > NEWS_MAX_AGE_DAYS
    formatted_candidates.append((candidate, item, is_emergency))

news_items = select_news_items(formatted_candidates)


# --------------------------------------------------
# Диагностика финального редакционного отбора
# --------------------------------------------------

selected_games = {item["game"] for item in news_items}
pipeline_diagnostics = []

print()
print("Диагностика утреннего отбора:")

for candidate in verified_news:
    game = normalize_game_name(candidate.get("game", "Roblox"))
    source_diagnostics = candidate.get("source_diagnostics", [])
    latest_dates = [
        diagnostic.get("latest_published_at")
        for diagnostic in source_diagnostics
        if diagnostic.get("latest_published_at")
    ]
    source_names = [
        diagnostic.get("source_type")
        for diagnostic in source_diagnostics
        if diagnostic.get("source_type")
    ]

    if game in selected_games:
        status = "ПРИНЯТ"
        reason = "вошёл в утренний выпуск"
    elif candidate.get("score", 0) < MIN_SCORE:
        status = "ОТБРОШЕН"
        rejected_reasons = [
            diagnostic.get("reason", "").rstrip(".")
            for diagnostic in source_diagnostics
            if diagnostic.get("status") == "rejected" and diagnostic.get("reason")
        ]
        reason = "; ".join(rejected_reasons) or (
            candidate.get("candidate_decision", {})
            .get("reason", "нет достойного свежего факта")
            .rstrip(".")
        )
    elif build_item(candidate) is None:
        status = "ОТБРОШЕН"
        reason = "нет конкретного факта, который можно корректно изложить"
    else:
        status = "ОТБРОШЕН"
        reason = "ниже трёх более сильных разных новостей"

    print(
        f"- {game}: источники={', '.join(source_names) or 'нет'}; "
        f"последняя дата={max(latest_dates) if latest_dates else 'не найдена'}; "
        f"{status} — {reason.rstrip('.')}."
    )

    verified_status = candidate.get("score", 0) >= MIN_SCORE
    formatted_status = any(
        formatted_item["game"] == game for _, formatted_item, _ in formatted_candidates
    )
    selected_status = game in selected_games
    pipeline_diagnostics.append(
        {
            "game": game,
            "candidate": True,
            "verified": verified_status,
            "selected": selected_status,
            "formatted_ru": formatted_status,
            "scheduled": False,
            "reason": reason.rstrip("."),
        }
    )


pipeline_summary = {
    "found": len(verified_news),
    "verified": sum(item["verified"] for item in pipeline_diagnostics),
    "selected": sum(item["selected"] for item in pipeline_diagnostics),
    "formatted": sum(item["formatted_ru"] for item in pipeline_diagnostics),
    "scheduled": 0,
}

save_json(
    "generated_news_data_ru.json",
    {
        "items": news_items,
        "pipeline": pipeline_diagnostics,
        "summary": pipeline_summary,
    },
)


preview_blocks = []


for item in news_items:
    preview_blocks.append(f"{item['emoji']} " f"{item['game']}\n" f"{item['text']}")


if preview_blocks:
    preview = "\n\n".join(preview_blocks)
else:
    preview = "Сегодня нет достаточно " "содержательных игровых новостей."


save_text("generated_news_post_ru.txt", preview)


print()
print(f"Подготовлено новостей: " f"{len(news_items)}")
print(
    "Roblox pipeline: "
    f"найдено={pipeline_summary['found']}, "
    f"verified={pipeline_summary['verified']}, "
    f"selected={pipeline_summary['selected']}, "
    f"formatted={pipeline_summary['formatted']}, "
    "scheduled=0"
)


for item in news_items:
    print(f"- {item['game']}: " f"{item['text']}")
