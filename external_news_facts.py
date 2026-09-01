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

# Tier B публикует не только новости, но и регулярно обновляемые справочники.
# Свежая дата и упоминание игры поэтому недостаточны: сначала отсекаем формат
# guide/reference, затем требуем конкретное событие или изменение самой игры.
TIER_B_REFERENCE_TITLE_PATTERNS = (
    r"\bhow to\b",
    r"\b(?:beginner|farming|strategy|complete|ultimate)\s+guide\b",
    r"\bguide\b",
    r"\btier\s+list\b",
    r"\bvalues?\s+list\b",
    r"\btrading\s+values?\b",
    r"\brarity\s+list\b",
    r"\ball\s+(?:pets?|weapons?|items?)\b",
    r"\b(?:redeem\s+)?codes?\b",
    r"\bwiki\b",
    r"\bwalkthrough\b",
    r"\b(?:price|value)\s+calculators?\b",
    r"\bbest\b",
    r"\btips?\b",
)

TIER_B_REFERENCE_BODY_PATTERNS = (
    *TIER_B_REFERENCE_TITLE_PATTERNS,
    r"\b(?:rarity|income|price|value)\s+(?:table|chart|database)\b",
    r"\btrade\s+calculator\b",
)

TIER_B_NEWS_EVENT_PATTERNS = (
    # Действие и игровая сущность должны находиться рядом: отдельного слова
    # pet/item/update недостаточно для признания материала новостью.
    (
        r"\b(?:adds?|added|introduc(?:e[ds]?|ing)|releas(?:e[ds]?|ing)|"
        r"launch(?:e[ds]?|ing)|unveil(?:e[ds]?|ing)|announc(?:e[ds]?|ing)|"
        r"brings?|arriv(?:e[ds]?|ing))\b.{0,100}\b(?:new\s+)?"
        r"(?:event|map|mode|pet|weapon|item|mechanic|feature|season|"
        r"collaboration|collab|vehicle|location|gameplay)\b"
    ),
    (
        r"\b(?:new\s+)?(?:event|map|mode|pet|weapon|item|mechanic|feature|"
        r"season|collaboration|collab|vehicle|location)\b.{0,100}\b"
        r"(?:adds?|added|introduc(?:e[ds]?|ing)|releas(?:e[ds]?|ing)|"
        r"launch(?:e[ds]?|ing)|unveil(?:e[ds]?|ing)|announc(?:e[ds]?|ing)|"
        r"coming|arriv(?:e[ds]?|ing)|live)\b"
    ),
    (
        r"\b(?:update|patch)\b.{0,80}\b(?:adds?|added|brings?|"
        r"introduc(?:e[ds]?)|releas(?:e[ds]?)|launch(?:e[ds]?)|"
        r"changes?|live|out now)\b"
    ),
    (
        r"\b(?:event|season)\b.{0,50}\b(?:starts?|begins?|"
        r"launch(?:e[ds]?)|goes live|is live)\b"
    ),
    r"\b(?:balance changes?|gameplay changes?|buff(?:ed|s)?|nerf(?:ed|s)?)\b",
    r"\b(?:update|patch)\s+(?:v?\d+(?:\.\d+)*|[a-z][a-z0-9'-]+)\b",
    r"\b[A-Za-z0-9][A-Za-z0-9 '&-]{2,45}\s+update\b",
    (
        r"\bnew\s+(?:event|map|mode|pet|weapon|item|mechanic|feature|"
        r"season|collaboration|collab|vehicle|location)\b"
    ),
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


def classify_news_event(article):
    """Classifies whether a Tier B article describes a real game news event.

    The title is authoritative for obvious reference formats. For everything
    else the combined title/body must describe a concrete launch, addition,
    announcement, event, patch, or gameplay/balance change.
    """

    title = " ".join(article.get("title", "").casefold().split())
    body = " ".join(article.get("text", "").casefold().split())
    combined = f"{title} {body}".strip()

    if any(re.search(pattern, title) for pattern in TIER_B_REFERENCE_TITLE_PATTERNS):
        return False, "guide/reference по заголовку"

    if any(re.search(pattern, combined) for pattern in TIER_B_NEWS_EVENT_PATTERNS):
        return True, "найдено конкретное игровое событие или изменение"

    if any(re.search(pattern, combined) for pattern in TIER_B_REFERENCE_BODY_PATTERNS):
        return False, "guide/reference по содержанию"

    return False, "нет конкретного нового события или изменения игры"


def is_news_event(article):
    """Boolean helper for Tier B discovery and verification."""

    accepted, _ = classify_news_event(article)
    return accepted


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

            summary = f"⚔️ Вышел балансный патч {patch_name} " f"#{patch_number}."
        else:
            summary = "Blox Fruits опубликовала " f"новость «{title}»."

    elif article.get("source_tier") == "B":
        publisher = article.get("publisher") or "игрового издания"
        title_kind = classify_content_line(title)
        concrete_summary = (
            summarize_content_line_ru(title, title_kind) if title_kind else None
        )
        summary = (
            f"По данным {publisher}, {concrete_summary}"
            if concrete_summary
            else f"По данным {publisher}, в {game} вышло обновление «{title}»."
        )

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


BALANCE_METRICS_RU = (
    ("dodge regeneration time", "время восстановления уклонений"),
    ("damage over time", "периодический урон"),
    ("all damage", "весь урон"),
    ("hitbox size", "размер хитбокса"),
    ("travel speed", "скорость полёта атаки"),
    ("flight speed", "скорость полёта"),
    ("stun duration", "длительность оглушения"),
    ("energy cost", "затраты энергии"),
    ("cast time", "время применения"),
    ("wind-up", "подготовка атаки"),
    ("end-lag", "задержка после атаки"),
    ("lifesteal", "вампиризм"),
    ("cooldown", "кулдаун"),
    ("duration", "длительность"),
    ("damage", "урон"),
    ("range", "дальность"),
)


def translate_balance_clause(clause):
    """Translates one numeric balance clause without changing names/numbers."""

    clean = clause.strip().rstrip(".")
    lower = clean.casefold()

    metric_ru = None
    metric_en = None
    for english, russian in BALANCE_METRICS_RU:
        if lower.startswith(english):
            metric_en = english
            metric_ru = russian
            break

    if metric_ru is None:
        return None

    remainder = clean[len(metric_en) :].strip()
    quantity = r"\d+(?:\.\d+)?(?:%|\s+seconds?)"
    change_match = re.fullmatch(
        rf"(increased|decreased|reduced)\s+"
        rf"(?:(by|to)\s+({quantity})|from\s+({quantity})\s+to\s+({quantity}))"
        r"(?:,.*)?",
        remainder,
        flags=re.IGNORECASE,
    )
    if not change_match:
        return None

    direction = change_match.group(1).casefold()

    def translate_units(value):
        return re.sub(r"\bseconds?\b", "секунд", value, flags=re.IGNORECASE)

    relation = change_match.group(2)
    if relation == "by":
        value = translate_units(change_match.group(3))
        sign = "+" if direction == "increased" else "−"
        return f"{metric_ru}: {sign}{value}"
    if relation == "to":
        value = translate_units(change_match.group(3))
        return f"{metric_ru}: теперь {value}"

    old_value = translate_units(change_match.group(4))
    new_value = translate_units(change_match.group(5))
    return f"{metric_ru}: {old_value} → {new_value}"


def extract_structured_balance_facts(article):
    """Selects up to three concrete changes from embedded official patch JSON."""

    rows = article.get("structured_content", [])
    if not isinstance(rows, list):
        return []

    candidates_by_category = {}
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue

        translated_clauses = [
            translated
            for clause in str(row.get("change", "")).split(";")
            if (translated := translate_balance_clause(clause))
        ]
        if not translated_clauses:
            continue

        category = str(row.get("category", "")).strip()
        name = str(row.get("name", "")).strip()
        group = str(row.get("group", "")).strip()
        ability = str(row.get("ability", "")).strip()
        if not category or not name or not ability:
            continue

        subject = f"{name} — {group}" if group else name
        summary = f"🔹 {subject} ({ability}): " + "; ".join(translated_clauses) + "."
        candidate = (
            len(translated_clauses),
            len(re.findall(r"\d+(?:\.\d+)?%?", row.get("change", ""))),
            -index,
            make_external_fact(
                article=article,
                text=(f"{category} | {name} | {ability} | " f"{row.get('change', '')}"),
                summary_ru=summary,
                kind="balance_change",
                value=10,
            ),
        )
        current = candidates_by_category.get(category)
        if current is None or candidate[:3] > current[:3]:
            candidates_by_category[category] = candidate

    # Берём разные части патча, чтобы один фрукт с десятком строк не вытеснил
    # системную механику или боевой стиль. Порядок стабилен и бесплатен.
    preferred_categories = (
        "Fruits",
        "Systems",
        "Fighting Styles",
        "Swords",
        "Guns",
        "Races",
    )
    selected = [
        candidates_by_category[category][3]
        for category in preferred_categories
        if category in candidates_by_category
    ]
    return selected[:3]


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

    # Defense in depth: даже сохранённый ранее Tier B результат не должен
    # пройти extraction только из-за свежей даты и слов pet/item/update.
    if article.get("source_tier") == "B" and not is_news_event(article):
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

    structured_balance_facts = extract_structured_balance_facts(article)
    facts.extend(structured_balance_facts)
    if structured_balance_facts:
        excluded_kinds.add("balance_change")

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

    # Главная новость и до трёх деталей образуют компактный блок. Заголовок
    # не вытесняет конкретные факты, но всегда объясняет, к чему они относятся.
    selected_facts = detail_facts[:3]
    if title_fact:
        selected_facts.insert(0, title_fact)
    return selected_facts[:4]
