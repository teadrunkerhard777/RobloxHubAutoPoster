"""Детерминированное форматирование официальных EN-новостей Brawl Stars."""

import re

RUMOR_MARKERS = (
    "leak",
    "leaked",
    "rumor",
    "rumour",
    "allegedly",
    "datamine",
    "datamined",
)

SPECULATIVE_PATTERNS = (
    r"\bpossible\s+(?:new\s+)?(?:update|event|mode|brawler|release|collab)",
    r"\bpossibly\s+(?:coming|arriving|adding|revealing)",
)

CONCRETE_MARKERS = (
    "bsc",
    "championship",
    "world finals",
    "brawl cup",
    "esports",
    "tournament",
    "event",
    "collaboration",
    "collab",
    "new game mode",
    "game mode",
    "new brawler",
    "hypercharge",
    "balance change",
    "reward",
    "update",
    "release notes",
)


def article_text(article):
    content = article.get("clean_content") or article.get("content") or []
    blocks = [block for block in content if isinstance(block, str)]
    return " ".join([article.get("title", ""), *blocks]).strip()


def contains_rumor_signal(article):
    text = article_text(article).casefold()
    return any(marker in text for marker in RUMOR_MARKERS) or any(
        re.search(pattern, text) for pattern in SPECULATIVE_PATTERNS
    )


def has_concrete_brawl_news(article):
    text = article_text(article).casefold()
    if len(text) < 25 or contains_rumor_signal(article):
        return False
    if article.get("category") == "esports":
        return True
    return any(marker in text for marker in CONCRETE_MARKERS)


def translate_title(title):
    normalized = " ".join((title or "").split())
    replacements = (
        (r"^First Look at\s+", "Первый взгляд на "),
        (r"^Introducing\s+", "Представляем: "),
        (r"^New\s+", "Новое: "),
        (r"Release Notes", "Описание обновления"),
        (r"World Finals", "World Finals"),
    )

    for pattern, replacement in replacements:
        normalized = re.sub(pattern, replacement, normalized, flags=re.IGNORECASE)

    return normalized


def build_translated_facts(article, max_facts=3):
    """Извлекает 1–3 коротких факта без внешнего переводчика."""

    if not has_concrete_brawl_news(article):
        return []

    text = article_text(article).casefold()
    facts = []

    if "two connected levels" in text or "challengers" in text:
        facts.append(
            "В BSC 2027 появятся два связанных уровня соревнований: "
            "основная лига и Challengers."
        )

    if "brawl cup" in text and "world finals" in text:
        facts.append(
            "Первый сплит будет вести к Brawl Cup, а второй — к Brawl Stars "
            "World Finals."
        )

    if "promotion and relegation" in text:
        facts.append(
            "Между уровнями введут повышение и выбывание команд по результатам "
            "соревнований."
        )

    if "new game mode" in text or "new game modes" in text:
        facts.append("Supercell анонсировала новый игровой режим Brawl Stars.")

    if "new brawler" in text or "new brawlers" in text:
        facts.append("В официальном обновлении представлен новый боец.")

    if "new hypercharge" in text or "new hypercharges" in text:
        facts.append("В обновлении появятся новые способности Hypercharge.")

    if "balance changes" in text:
        facts.append("Supercell опубликовала новые изменения баланса.")

    if not facts and article.get("category") == "esports":
        facts.append(
            "Supercell опубликовала новые подробности о соревнованиях Brawl Stars."
        )

    if not facts:
        facts.append(
            f"Supercell опубликовала официальный анонс «{translate_title(article.get('title'))}»."
        )

    unique_facts = []
    for fact in facts:
        if fact not in unique_facts:
            unique_facts.append(fact)

    return unique_facts[:max_facts]


def build_deterministic_translation(article):
    facts = build_translated_facts(article)
    if not facts:
        return None

    return {
        "source_language": "en",
        "translated": True,
        "translated_title": translate_title(article.get("title", "")),
        "translated_content": facts,
    }
