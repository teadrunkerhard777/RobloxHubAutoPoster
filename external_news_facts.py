import re
from datetime import datetime, timezone

from news_fact_utils import (
    classify_content_line,
    clean_content_line,
    summarize_content_line_ru,
)

# Основное окно официальных новостей. История использованных URL по-прежнему
# обязательна и не позволяет расширенному окну превращаться в повторы.
NEWS_MAX_AGE_DAYS = 14

# Если в основном окне нет ни одной пригодной новости, финальный отбор может
# использовать ещё не публиковавшийся материал не старше 30 дней.
SECONDARY_NEWS_MAX_AGE_DAYS = 30

# Старое имя сохраняем для совместимости остальных этапов и тестов.
MAX_ARTICLE_AGE_DAYS = NEWS_MAX_AGE_DAYS

RUMOR_MARKERS = (
    "leak",
    "leaked",
    "rumor",
    "rumour",
    "allegedly",
    "datamine",
    "datamined",
    "утечк",
    "слух",
)

SPECULATIVE_PATTERNS = (
    r"\bpossible\s+(?:new\s+)?(?:update|event|mode|item|pet|release|collab)",
    r"\bpossibly\s+(?:coming|arriving|adding|revealing)",
)

GAME_NEWS_MARKERS = (
    "update",
    "event",
    "mode",
    "map",
    "item",
    "pet",
    "reward",
    "season",
    "tournament",
    "championship",
    "competition",
    "esports",
    "world finals",
    "bsc",
    "collab",
    "release",
    "patch",
    "balance",
    "new ",
    "обновлен",
    "событ",
    "режим",
    "карт",
    "предмет",
    "питом",
    "наград",
    "сезон",
    "турнир",
    "анонс",
)


def contains_rumor_signal(article):
    text = " ".join([article.get("title", ""), article.get("text", "")]).casefold()
    return any(marker in text for marker in RUMOR_MARKERS) or any(
        re.search(pattern, text) for pattern in SPECULATIVE_PATTERNS
    )


def has_game_news_meaning(article):
    body = article.get("text", "").strip()
    if len(body) < 25:
        return False
    text = " ".join([article.get("title", ""), body]).casefold()
    return any(marker in text for marker in GAME_NEWS_MARKERS)


def parse_published_at(value):
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        result = datetime.fromisoformat(normalized)
    except ValueError:
        return None

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)

    return result.astimezone(timezone.utc)


def get_article_age_days(article, now=None):
    published_at = parse_published_at(article.get("published_at"))

    if published_at is None:
        return None

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    age = now.astimezone(timezone.utc) - published_at

    return age.total_seconds() / 86400


def is_fresh_article(article, now=None, max_age_days=MAX_ARTICLE_AGE_DAYS):
    if not article:
        return False

    if article.get("success") is not True:
        return False

    if not article.get("url"):
        return False

    age_days = get_article_age_days(article, now=now)

    if age_days is None:
        return False

    # Небольшой допуск на часы серверов,
    # но не на статьи из далёкого будущего.
    return age_days >= -1 and age_days <= max_age_days


def make_external_fact(article, text, summary_ru, kind, value):
    return {
        "text": text,
        "summary_ru": summary_ru,
        "kind": kind,
        "value": value,
        "specific": True,
        "reason": ("Факт из официальной новостной статьи"),
        "is_new_line": True,
        "source_url": article["url"],
    }


def clean_article_title(game, title):
    result = title.strip()

    if game == "Adopt Me!":
        result = re.sub(r"\s*-\s*Adopt Me!\s*$", "", result, flags=re.IGNORECASE)

    result = re.sub(r"\s+Notes!?\s*$", "", result, flags=re.IGNORECASE)

    return result.strip()


def is_concrete_article_title(game, title):
    cleaned = clean_article_title(game, title)
    without_game = re.sub(re.escape(game), " ", cleaned, flags=re.IGNORECASE)
    without_game = re.sub(r"\b(?:19|20)\d{2}\b|\b\d{1,2}\b", " ", without_game)
    without_game = re.sub(r"\s+", " ", without_game).strip(" -–—:!?")

    if not classify_content_line(without_game):
        return False

    # Эти заголовки называют лишь тип публикации. Конкретным исключением
    # считается заголовок с игровой сущностью: например Prison Landmark
    # или Backpack Storage, но не просто New Pets / Items Update.
    generic_title = re.fullmatch(
        r"(?:new\s+|updated\s+)?"
        r"(?:pets?|items?|tools?|vehicles?|events?|"
        r"updates?|patch(?: notes?)?)"
        r"(?:\s+updates?)?",
        without_game,
        flags=re.IGNORECASE,
    )

    return generic_title is None


def build_title_fact(game, article):
    title = clean_article_title(game, article.get("title", ""))

    if not title:
        return None

    body_contains_specific_fact = False

    if game == "Blox Fruits":
        patch_match = re.search(
            r"(.+?)\s+Patch Notes\s*-\s*" r"Balance Patch\s*(\d+)",
            article.get("text", ""),
            flags=re.IGNORECASE,
        )

        if patch_match:
            body_contains_specific_fact = True
            patch_name = patch_match.group(1).strip()
            patch_number = patch_match.group(2)

            summary = (
                "В Blox Fruits вышел "
                f"балансный патч {patch_name} "
                f"#{patch_number}."
            )
        else:
            summary = "Blox Fruits опубликовала " f"новость «{title}»."

    elif article.get("source_tier") == "B":
        publisher = article.get("publisher") or "игрового издания"
        summary = f"По данным {publisher}, в {game} вышел материал «{title}»."

    elif game == "Adopt Me!":
        summary = "В Adopt Me! вышло обновление " f"«{title}»."

    else:
        summary = f"В {game} вышло обновление " f"«{title}»."

    fact = make_external_fact(
        article=article,
        text=title,
        summary_ru=summary,
        kind="official_article",
        value=6,
    )

    fact["title_is_concrete"] = (
        body_contains_specific_fact
        or is_concrete_article_title(game, article.get("title", ""))
    )

    return fact


def extract_pet_entries(text):
    entries = []
    pattern = re.compile(
        r"(?:[^A-Za-z0-9\n]*)([A-Z][A-Za-z0-9' ]{1,40}?)\s*"
        r"(?:,|-)\s*\n?\s*"
        r"(Legendary|Ultra Rare|Rare|Uncommon|Common)\b",
        flags=re.IGNORECASE,
    )

    for match in pattern.finditer(text):
        name = match.group(1).strip()
        rarity = match.group(2).title()

        if name.lower().startswith(("hatch from", "collecting the")):
            continue

        entry = (name, rarity)
        if entry not in entries:
            entries.append(entry)

    return entries


def extract_adopt_me_facts(article):
    text = article.get("text", "")

    facts = []

    pet_match = re.search(
        r"(?:🐶\s*)?"
        r"([A-Za-z][A-Za-z ]+?)\s*-\s*"
        r"Hatch from the\s+(.+?)\s*-\s*\n"
        r"([A-Za-z ]+)",
        text,
        flags=re.IGNORECASE,
    )

    if pet_match:
        pet_name = pet_match.group(1).strip()
        egg_names = pet_match.group(2).strip()
        rarity = pet_match.group(3).strip()

        facts.append(
            make_external_fact(
                article=article,
                text=pet_match.group(0).strip(),
                summary_ru=(
                    f"Из {egg_names} теперь можно "
                    f"получить питомца {pet_name} "
                    f"редкости {rarity}."
                ),
                kind="pets",
                value=8,
            )
        )

    pet_entries = extract_pet_entries(text)

    # Статья может перечислять несколько питомцев отдельными строками.
    # Собираем их в один полезный факт, а не публикуем каждую сырую строку.
    if pet_entries and not pet_match:
        names = [name for name, _ in pet_entries]
        all_legendary = all(rarity.lower() == "legendary" for _, rarity in pet_entries)
        rarity_ru = "легендарных " if all_legendary else ""
        names_ru = (
            names[0] if len(names) == 1 else ", ".join(names[:-1]) + " и " + names[-1]
        )
        egg_context = "В Releaser Eggs" if "RELEASER" in text.upper() else "В игре"

        facts.append(
            make_external_fact(
                article=article,
                text="; ".join(f"{name} — {rarity}" for name, rarity in pet_entries),
                summary_ru=(
                    f"{egg_context} добавили {len(names)} "
                    f"{rarity_ru}питомцев: {names_ru}."
                ),
                kind="pets",
                value=10,
            )
        )

    storage_lines = [
        clean_content_line(line)
        for line in text.splitlines()
        if (
            "storage" in line.lower()
            or "backpack" in line.lower()
            or "multiple items" in line.lower()
        )
        and len(clean_content_line(line)) >= 12
    ]

    if storage_lines:
        lower_storage = " ".join(storage_lines).lower()
        features = []

        if "outside" in lower_storage or "between your backpack" in lower_storage:
            features.append("предметы можно хранить отдельно от рюкзака")
        if "multiple items" in lower_storage or "all at once" in lower_storage:
            features.append("переносить сразу по несколько штук")
        if "tabs" in lower_storage:
            features.append("раскладывать по вкладкам")

        if features:
            feature_text = (
                features[0]
                if len(features) == 1
                else ", ".join(features[:-1]) + " и " + features[-1]
            )
            facts.append(
                make_external_fact(
                    article=article,
                    text=" ".join(storage_lines[:6]),
                    summary_ru=("Появилось Backpack Storage: " f"{feature_text}."),
                    kind="mechanics_storage",
                    value=10,
                )
            )

    task_match = re.search(
        r"Bring the Mysterious Stranger\s+"
        r"(\d+) Bundles of Forks\s+"
        r"in exchange for\s+(\d+) Bucks",
        text,
        flags=re.IGNORECASE,
    )

    if task_match:
        bundle_count = task_match.group(1)
        bucks_count = task_match.group(2)

        facts.append(
            make_external_fact(
                article=article,
                text=task_match.group(0),
                summary_ru=(
                    "У Mysterious Stranger можно "
                    f"обменять {bundle_count} связок "
                    f"вилок на {bucks_count} Bucks."
                ),
                kind="quests",
                value=8,
            )
        )

    return facts


def extract_pet_simulator_facts(article):
    """Извлекает факты из длинных update-постов BIG Games.

    На сайте важные фразы часто разбиты HTML-тегами на отдельные строки:
    ``Lucky Blocks`` / ``spawn in`` / ``waves``. Поэтому для устойчивого
    анализа сначала соединяем пробельные фрагменты, но используем только
    явно присутствующие в статье названия и числа.
    """

    text = re.sub(r"\s+", " ", article.get("text", "")).strip()

    if not text:
        return []

    facts = []
    title = clean_article_title("Pet Simulator 99", article.get("title", ""))

    # Заголовок события подтверждаем характерными деталями тела статьи.
    if (
        title
        and title.casefold() in text.casefold()
        and re.search(
            r"\b(?:EVENT|BOARD|LIMITED PETS?|CLAN BATTLE)\b", text, flags=re.IGNORECASE
        )
    ):
        facts.append(
            make_external_fact(
                article=article,
                text=title,
                summary_ru=("В Pet Simulator 99 стартовало событие " f"«{title}»."),
                kind="event",
                value=10,
            )
        )

    board_names = re.findall(
        r"\b([A-Z][A-Za-z0-9']*(?:\s+[A-Z][A-Za-z0-9']*){0,2}\s+Board)\b", text
    )
    board_name = next(
        (
            name
            for name in board_names
            if re.search(
                rf"{re.escape(name)}\s*!?.{{0,80}}?spawn in\s+waves",
                text,
                flags=re.IGNORECASE,
            )
        ),
        None,
    )

    if board_name:
        facts.append(
            make_external_fact(
                article=article,
                text=board_name,
                summary_ru=(
                    f"Добавлен режим {board_name}: блоки появляются "
                    "волнами, а питомцы разбивают их на поле."
                ),
                kind="game_mode",
                value=9,
            )
        )

    pets_match = re.search(
        r"Collect all\s+(\d+)\s+brand-new\s+([A-Za-z0-9' ]+?)\s+pets",
        text,
        flags=re.IGNORECASE,
    )

    if pets_match:
        count = pets_match.group(1)
        collection_name = pets_match.group(2).strip()
        facts.append(
            make_external_fact(
                article=article,
                text=pets_match.group(0),
                summary_ru=(
                    f"В коллекцию добавили {count} новых питомцев "
                    f"серии {collection_name}."
                ),
                kind="pets",
                value=9,
            )
        )

    leaderboard_match = re.search(
        r"(?:up the\s+)?([A-Z][A-Za-z0-9' ]+ Leaderboard)\s*!?",
        text,
        flags=re.IGNORECASE,
    )

    if leaderboard_match:
        leaderboard_name = leaderboard_match.group(1).strip()
        facts.append(
            make_external_fact(
                article=article,
                text=leaderboard_match.group(0),
                summary_ru=(f"Открыт {leaderboard_name} с наградами за места."),
                kind="leaderboard",
                value=8,
            )
        )

    gamepass_match = re.search(
        r"([A-Z][A-Za-z0-9' ]+ Gamepass).*?boosts your egg luck.*?(\d+)%",
        text,
        flags=re.IGNORECASE,
    )

    if gamepass_match:
        gamepass_name = gamepass_match.group(1).strip()
        boost = gamepass_match.group(2)
        facts.append(
            make_external_fact(
                article=article,
                text=gamepass_match.group(0)[:300],
                summary_ru=(
                    f"Добавлен {gamepass_name}, повышающий удачу яиц " f"на {boost}%."
                ),
                kind="gamepass",
                value=8,
            )
        )

    facts.sort(key=lambda item: item["value"], reverse=True)

    return facts[:3]


ARTICLE_NOISE = {
    "DISCOVER",
    "NEWS",
    "MEDIA",
    "SUPPORT",
    "MERCH",
    "WATCH",
    "PLAY",
    "BLOG",
    "UPDATES",
    "READ MORE",
    "VIEW ALL",
    "CONTACT",
    "PRIVACY POLICY",
    "TERMS OF SERVICE",
    "PLAY NOW",
}


GENERIC_SUMMARIES = {
    "В игре появилась новая локация.",
    "В игру добавили новый транспорт.",
    "В игре появились новые инструменты и оружие.",
    "В игре появились новые предметы.",
    "Добавили новый реквизит для ролевых сцен.",
    "В игре появилась новая полезная механика.",
    "В игре появились новые питомцы.",
    "В игре появились новые задания.",
    "Появились новые задания с наградами.",
    "В игре началось новое событие.",
}


def extract_generic_article_facts(article, excluded_kinds=None):
    if excluded_kinds is None:
        excluded_kinds = set()

    grouped = {}

    for raw_line in article.get("text", "").splitlines():
        line = clean_content_line(raw_line)
        upper = line.upper()

        if upper in {
            "LATEST UPDATES",
            "LATEST UPDATE",
            "LATEST NEWS",
            "LATEST BLOGS",
            "OUR TERMS OF SERVICE HAVE BEEN UPDATED.",
        }:
            break

        if not line or upper in ARTICLE_NOISE or len(line) < 5 or len(line) > 180:
            continue

        kind = classify_content_line(line)

        if not kind or kind in excluded_kinds:
            continue

        line_summary = summarize_content_line_ru(line, kind)

        # Статья содержит меню и общие рекламные фразы. Для факта нужен
        # маркер изменения либо короткая предметная строка из списка.
        has_change_signal = bool(
            re.search(r"\b(?:NEW|UPDATED|ADDED|INCLUDES?|APPEARED|NOW|CAN)\b", upper)
        )
        list_like = line_summary not in GENERIC_SUMMARIES

        if not has_change_signal and not list_like:
            continue

        if line_summary in GENERIC_SUMMARIES and (
            not has_change_signal or len(line.split()) < 3
        ):
            continue

        group_key = kind
        if kind == "items" and "PROP" in upper:
            group_key = "items_props"

        grouped.setdefault(group_key, []).append(line)

    values = {
        "locations": 9,
        "pets": 9,
        "mechanics_storage": 7,
        "vehicle": 8,
        "items": 8,
        "items_props": 8,
        "quests": 8,
        "event": 8,
    }
    facts = []

    for group_key, lines in grouped.items():
        kind = "items" if group_key == "items_props" else group_key
        evidence = " ".join(lines[:6])
        summary_ru = summarize_content_line_ru(evidence, kind)

        if not summary_ru:
            continue

        facts.append(
            make_external_fact(
                article=article,
                text=evidence,
                summary_ru=summary_ru,
                kind=kind,
                value=values[group_key],
            )
        )

    return facts


def extract_external_facts(
    game,
    article,
    now=None,
    max_age_days=MAX_ARTICLE_AGE_DAYS,
):
    if not is_fresh_article(article, now=now, max_age_days=max_age_days):
        return []

    if contains_rumor_signal(article):
        return []

    facts = []

    title_fact = build_title_fact(game, article)

    if title_fact:
        facts.append(title_fact)

    if game == "Adopt Me!":
        adopt_facts = extract_adopt_me_facts(article)
        facts.extend(adopt_facts)
        excluded_kinds = {fact["kind"] for fact in adopt_facts}
    else:
        excluded_kinds = set()

    if game == "Pet Simulator 99":
        pet_simulator_facts = extract_pet_simulator_facts(article)
        facts.extend(pet_simulator_facts)
        excluded_kinds.update(fact["kind"] for fact in pet_simulator_facts)

    facts.extend(extract_generic_article_facts(article, excluded_kinds=excluded_kinds))

    facts.sort(key=lambda item: item["value"], reverse=True)

    detail_facts = [fact for fact in facts if fact.get("kind") != "official_article"]

    if not detail_facts and title_fact and not title_fact.get("title_is_concrete"):
        # Для официального источника нормальный игровой смысл в теле статьи
        # достаточен: сложная semantic verification здесь не нужна.
        if article.get("source_tier", "A") == "A" and has_game_news_meaning(article):
            title_fact["title_is_concrete"] = True
            title_fact["reason"] = "Свежий игровой анонс из официального источника"
        else:
            return []

    # Одна статья даёт компактный набор: не более трёх ключевых изменений.
    # Заголовок остаётся допустимым запасным фактом, но детали выше него.
    return facts[:3]
