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

RELEASE_NOTES_DETAIL_MARKERS = (
    "brawler blast",
    "new brawler",
    "new brawlers",
    "new hypercharge",
    "new hypercharges",
    "new buffies",
    "balance changes",
    "duolingo event",
    "brawl-o-ween event",
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


def is_substantive_official_release_notes(article):
    """Recognizes official release notes with several concrete game changes."""

    if article.get("category") != "release-notes":
        return False
    if (
        article.get("official", True) is not True
        or article.get("fresh", True) is not True
    ):
        return False
    if contains_rumor_signal(article):
        return False

    text = article_text(article).casefold()
    matched_markers = {
        marker for marker in RELEASE_NOTES_DETAIL_MARKERS if marker in text
    }
    return len(matched_markers) >= 2


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


def build_release_notes_facts(article, max_facts=5):
    """Builds a short factual digest from large official release notes.

    The rules intentionally match explicit phrases and named sections from the
    source. They never infer a feature from the article title or call an LLM.
    """

    if not is_substantive_official_release_notes(article):
        return []

    text = article_text(article)
    lower = text.casefold()
    facts = []

    if "starr road has been reworked into brawler blast" in lower:
        facts.append(
            "🔹 Starr Road переработана в Brawler Blast: Credits открывают "
            "следующего бойца через тир с мишенями."
        )

    brawler_names = []
    for block in article.get("clean_content") or article.get("content") or []:
        if not isinstance(block, str):
            continue
        match = re.fullmatch(
            r"([A-Za-z][A-Za-z' -]+)\s+-\s+"
            r"(?:Mythic|Legendary|Epic|Ultra|Super Rare|Rare)\s+-\s+.+",
            " ".join(block.split()),
            flags=re.IGNORECASE,
        )
        if match:
            name = match.group(1).strip()
            if name not in brawler_names:
                brawler_names.append(name)

    if brawler_names:
        names = " и ".join(brawler_names[:2])
        facts.append(f"🔹 Появятся новые бойцы {names}.")

    hypercharge_match = re.search(
        r"([A-Za-z]+)\s+and\s+([A-Za-z]+)\s+are getting " r"brand-new Hypercharges",
        text,
        flags=re.IGNORECASE,
    )
    if hypercharge_match:
        facts.append(
            f"🔹 {hypercharge_match.group(1)} и {hypercharge_match.group(2)} "
            "получают новые Hypercharge."
        )

    if "duolingo event" in lower and "brand-new boss fight" in lower:
        facts.append(
            "🔹 В коллаборации с Duolingo появятся Boss Fight, общее событие "
            "и ежедневные награды."
        )

    if "brawl-o-ween event" in lower and "month-long event" in lower:
        facts.append(
            "🔹 Brawl-O-Ween продлится месяц: будут этапы, загадки, выбор "
            "сообщества и возвращение боссов."
        )

    if "new buffies" in lower and len(facts) < max_facts:
        facts.append("🔹 В обновлении добавят новые Buffies.")

    if "balance changes" in lower and len(facts) < max_facts:
        facts.append("🔹 Также опубликованы изменения способностей и баланса бойцов.")

    return facts[:max_facts]


def build_translated_facts(article, max_facts=5):
    """Извлекает до пяти коротких фактов без внешнего переводчика."""

    if not has_concrete_brawl_news(article):
        return []

    release_notes_facts = build_release_notes_facts(article, max_facts=max_facts)
    if release_notes_facts:
        return release_notes_facts

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
