import json
import re
from datetime import datetime, timedelta, timezone

import requests

from external_news_facts import (
    MAX_ARTICLE_AGE_DAYS,
    SECONDARY_NEWS_MAX_AGE_DAYS,
    contains_rumor_signal,
    extract_external_facts,
    get_article_age_days,
    has_game_news_meaning,
)
from source_health import (
    ALREADY_USED,
    EXTRACTION_FAILED,
    FOUND_REJECTED,
    FOUND_VERIFIED,
    NO_NEW_CONTENT,
    SOURCE_STALE,
    SOURCE_UNAVAILABLE,
    print_source_health_report,
)

LOCAL_TIMEZONE = timezone(timedelta(hours=5))


NEWS_KEYWORDS = [
    "UPDATE",
    "NEW",
    "EVENT",
    "CODE",
    "CODES",
    "BOSS",
    "ITEM",
    "ITEMS",
    "MAP",
    "PET",
    "PETS",
    "LIMITED",
    "REWARD",
    "REWARDS",
    "QUEST",
    "QUESTS",
    "SEASON",
    "CONTRACT",
    "CONTRACTS",
]


# --------------------------------------------------
# JSON
# --------------------------------------------------


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


# --------------------------------------------------
# Текстовый анализ
# --------------------------------------------------


def find_keywords(text):
    if not text:
        return []

    text_upper = text.upper()

    return [keyword for keyword in NEWS_KEYWORDS if keyword in text_upper]


def extract_news_lines(text):
    if not text:
        return []

    result = []

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        if find_keywords(clean_line):
            result.append(clean_line)

    return result


# --------------------------------------------------
# Roblox Groups API
# --------------------------------------------------


def fetch_groups(group_ids):
    url = "https://groups.roblox.com/v2/groups"

    response = requests.get(
        url,
        params={"groupIds": ",".join(str(group_id) for group_id in group_ids)},
        timeout=15,
    )

    response.raise_for_status()

    return {group["id"]: group for group in response.json().get("data", [])}


# --------------------------------------------------
# Источники
# --------------------------------------------------


def add_source(candidate, source_type, verified=True, **extra):
    sources = candidate.setdefault("sources", [])

    source = {"type": source_type, "verified": verified}

    source.update(extra)

    # Не создаём дубликаты одного типа.
    for existing in sources:
        if existing.get("type") == source_type:
            existing.update(source)
            return

    sources.append(source)


# --------------------------------------------------
# Официальное описание игры
# --------------------------------------------------


def verify_official_description(candidate):
    description = candidate.get("description", "")

    facts = candidate.get("facts", [])

    fact_lines = [fact.get("text", "") for fact in facts if fact.get("text")]

    if fact_lines:
        news_lines = fact_lines
    else:
        news_lines = extract_news_lines(description)

    candidate["official_description_analysis"] = {
        "keywords": find_keywords(description),
        "news_lines": news_lines,
    }

    if description:
        add_source(candidate, "official_game_description", verified=True)

    return candidate


# --------------------------------------------------
# Поиск записи игры в реестре
# --------------------------------------------------


def find_source_config(candidate, source_registry):
    game = candidate.get("game", "")

    if game in source_registry:
        return source_registry[game]

    # Небольшая страховка от регистра.
    game_lower = game.lower()

    for name, config in source_registry.items():
        if name.lower() == game_lower:
            return config

    return None


# --------------------------------------------------
# Официальная Roblox-группа
# --------------------------------------------------


def verify_registry_group(
    candidate, source_registry, group_lookup, group_fetch_error=None
):
    config = find_source_config(candidate, source_registry)

    if not config:
        candidate["source_registry_note"] = (
            "Игра отсутствует " "в official_sources.json"
        )

        return candidate

    group_id = config.get("roblox_group_id")

    expected_name = config.get("roblox_group_name")

    candidate["source_registry"] = {
        "universe_id": config.get("universe_id"),
        "root_place_id": config.get("root_place_id"),
        "roblox_game_url": config.get("roblox_game_url"),
        "roblox_group_id": group_id,
        "roblox_group_name": (expected_name),
        "roblox_group_url": config.get("roblox_group_url"),
        "news_strategy": config.get("news_strategy"),
        "website": config.get("website"),
        "news_url": config.get("news_url"),
        "discord": config.get("discord"),
        "youtube": config.get("youtube"),
        "x": config.get("x"),
    }

    # Например Blade Ball пока
    # без подтверждённого group_id.
    if not group_id:
        candidate["group_verification_note"] = (
            "В реестре пока нет " "подтверждённого group_id."
        )

        return candidate

    if group_fetch_error:
        candidate["group_verification_note"] = group_fetch_error

        return candidate

    group = group_lookup.get(group_id)

    if not group:
        candidate["group_verification_note"] = (
            "Группа отсутствует в ответе " "пакетного Roblox Groups API."
        )

        return candidate

    actual_name = group.get("name", "")

    name_matches = True

    if expected_name:
        name_matches = actual_name.strip().lower() == expected_name.strip().lower()

    candidate["official_group"] = {
        "id": group.get("id"),
        "name": actual_name,
        "expected_name": expected_name,
        "name_matches_registry": (name_matches),
        "description": group.get("description", ""),
        "has_verified_badge": group.get("hasVerifiedBadge", False),
        "news_lines": [],
    }

    add_source(
        candidate,
        "official_roblox_group",
        verified=name_matches,
        group_id=group_id,
        group_name=actual_name,
    )

    return candidate


# --------------------------------------------------
# Официальные статьи с сайтов игр
# --------------------------------------------------


def find_external_results(game, external_results):
    game_lower = game.strip().lower()

    return [
        result
        for result in external_results
        if (result.get("game", "").strip().lower() == game_lower)
    ]


def article_used_on_another_day(article_url, external_history, local_date):
    for record in external_history:
        if record.get("url") != article_url:
            continue

        return record.get("selected_date") != local_date.isoformat()

    return False


def articles_describe_same_news(first_article, second_article):
    """Detects a syndicated Tier B copy of an already used official update."""

    ignored_words = {
        "roblox",
        "update",
        "updates",
        "patch",
        "notes",
        "news",
        "the",
        "and",
        "for",
        "with",
    }

    def title_words(article):
        return {
            word
            for word in re.findall(r"[a-z0-9]+", article.get("title", "").casefold())
            if len(word) >= 4 and word not in ignored_words
        }

    shared_words = title_words(first_article).intersection(title_words(second_article))
    return len(shared_words) >= 2


def evaluate_external_result(candidate, result, external_history, now):
    """Проводит один официальный источник по всем этапам проверки."""

    source_tier = result.get("source_tier", "A")

    diagnostic = {
        "source_type": result.get("source_type", "official_news_website"),
        "source_url": result.get("url"),
        "latest_published_at": None,
        "status": "rejected",
        "result_code": NO_NEW_CONTENT,
        "reason": "Источник не вернул подходящую публикацию.",
        "available": result.get("success") is True,
        "article_found": False,
        "date_found": False,
        "content_found": False,
        "extraction_success": False,
        "verification_passed": False,
        "source_tier": source_tier,
        "official": source_tier == "A",
        "selected": False,
        "formatted": False,
        "scheduled": False,
    }
    candidate["external_source_diagnostic"] = diagnostic

    if result.get("success") is not True:
        diagnostic["result_code"] = SOURCE_UNAVAILABLE
        diagnostic["reason"] = "Источник недоступен: " + (
            result.get("error") or "неизвестная ошибка"
        )
        return diagnostic, None, []

    article = result.get("latest_article")

    if not article:
        diagnostic["reason"] = (
            result.get("error")
            or "Не найдена публикация со стабильной датой и содержанием."
        )
        return diagnostic, None, []

    diagnostic["article_found"] = True
    diagnostic["latest_published_at"] = article.get("published_at")
    diagnostic["latest_url"] = article.get("url")
    diagnostic["date_found"] = bool(article.get("published_at"))
    diagnostic["content_found"] = bool(
        article.get("title") and article.get("text", "").strip()
    )
    article["source_tier"] = source_tier
    article["publisher"] = result.get("publisher")

    if contains_rumor_signal(article):
        diagnostic["result_code"] = FOUND_REJECTED
        diagnostic["reason"] = "Материал содержит признаки слуха или утечки."
        return diagnostic, article, []

    if article.get("success") is not True:
        diagnostic["result_code"] = SOURCE_UNAVAILABLE
        diagnostic["reason"] = "Публикация не загружена: " + (
            article.get("error") or "неизвестная ошибка"
        )
        return diagnostic, article, []

    age_days = get_article_age_days(article, now=now)

    if age_days is None:
        diagnostic["result_code"] = FOUND_REJECTED
        diagnostic["reason"] = "У публикации нет стабильной даты."
        return diagnostic, article, []

    if age_days < -1:
        diagnostic["result_code"] = FOUND_REJECTED
        diagnostic["reason"] = "Дата публикации находится в будущем."
        return diagnostic, article, []

    if age_days > SECONDARY_NEWS_MAX_AGE_DAYS:
        diagnostic["result_code"] = SOURCE_STALE
        diagnostic["reason"] = (
            f"Публикация устарела: {age_days:.1f} дн. "
            f"(аварийный лимит {SECONDARY_NEWS_MAX_AGE_DAYS})."
        )
        return diagnostic, article, []

    if source_tier == "B" and not has_game_news_meaning(article):
        diagnostic["result_code"] = FOUND_REJECTED
        diagnostic["reason"] = "Tier B не содержит конкретного игрового изменения."
        return diagnostic, article, []

    article_url = article.get("url", "")

    if article_used_on_another_day(
        article_url, external_history, now.astimezone(LOCAL_TIMEZONE).date()
    ):
        diagnostic["result_code"] = ALREADY_USED
        diagnostic["reason"] = "Публикация уже использовалась в выпуске другого дня."
        return diagnostic, article, []

    external_facts = extract_external_facts(
        candidate.get("game", ""),
        article,
        now=now,
        max_age_days=SECONDARY_NEWS_MAX_AGE_DAYS,
    )

    if not external_facts:
        diagnostic["result_code"] = EXTRACTION_FAILED
        diagnostic["reason"] = (
            "В публикации не найдено достаточно конкретного содержания."
        )
        return diagnostic, article, []

    diagnostic["extraction_success"] = True

    diagnostic["status"] = "accepted"
    diagnostic["result_code"] = FOUND_VERIFIED
    diagnostic["verification_passed"] = True
    diagnostic["freshness_window"] = (
        "primary_14_day" if age_days <= MAX_ARTICLE_AGE_DAYS else "emergency_30_day"
    )
    reliability = "официальная" if source_tier == "A" else "Tier B"
    diagnostic["reason"] = (
        f"{reliability.capitalize()} публикация ({age_days:.1f} дн.) "
        f"с датой и игровым содержанием; окно {diagnostic['freshness_window']}."
    )

    return diagnostic, article, external_facts


def enrich_with_external_news(candidate, external_results, external_history, now):
    candidate.pop("external_news_article", None)
    candidate["external_source_diagnostics"] = []
    results = find_external_results(candidate.get("game", ""), external_results)

    if not results:
        return candidate

    local_date = now.astimezone(LOCAL_TIMEZONE).date()
    used_official_articles = [
        result.get("latest_article")
        for result in results
        if result.get("source_tier", "A") == "A"
        and result.get("latest_article")
        and article_used_on_another_day(
            result["latest_article"].get("url", ""),
            external_history,
            local_date,
        )
    ]

    accepted_articles = []
    for result in results:
        diagnostic, article, external_facts = evaluate_external_result(
            candidate, result, external_history, now
        )
        candidate["external_source_diagnostics"].append(diagnostic)

        if (
            external_facts
            and result.get("source_tier") == "B"
            and any(
                articles_describe_same_news(article, used_article)
                for used_article in used_official_articles
            )
        ):
            diagnostic["status"] = "rejected"
            diagnostic["result_code"] = ALREADY_USED
            diagnostic["verification_passed"] = False
            diagnostic["reason"] = (
                "Tier B повторяет уже использованную официальную новость."
            )
            external_facts = []

        if not external_facts:
            continue

        accepted_articles.append(
            (
                1 if result.get("source_tier", "A") == "B" else 0,
                1 if result.get("source_type") == "official_youtube_feed" else 0,
                get_article_age_days(article, now=now),
                article,
                result,
                external_facts,
            )
        )

    if accepted_articles:
        _, _, _, article, result, external_facts = min(
            accepted_articles, key=lambda item: (item[0], item[1], item[2])
        )
        current_facts = candidate.setdefault("facts", [])
        known_fact_keys = {
            (fact.get("text", ""), fact.get("source_url", "")) for fact in current_facts
        }

        for fact in external_facts:
            fact_key = (fact.get("text", ""), fact.get("source_url", ""))
            if fact_key not in known_fact_keys:
                current_facts.append(fact)
                known_fact_keys.add(fact_key)

        current_facts.sort(key=lambda fact: fact.get("value", 0), reverse=True)
        candidate["score"] = max(
            candidate.get("score", 0),
            max(fact.get("value", 0) for fact in external_facts),
        )
        add_source(
            candidate,
            result.get("source_type", "official_news_website"),
            verified=True,
            url=article.get("url", ""),
        )
        candidate["external_news_article"] = {
            "url": article.get("url", ""),
            "title": article.get("title", ""),
            "published_at": article.get("published_at"),
            "age_days": get_article_age_days(article, now=now),
            "source_tier": result.get("source_tier", "A"),
            "publisher": result.get("publisher"),
            "freshness_window": (
                "primary_14_day"
                if get_article_age_days(article, now=now) <= MAX_ARTICLE_AGE_DAYS
                else "emergency_30_day"
            ),
        }

    return candidate


# --------------------------------------------------
# Проверяем, подтверждает ли shout
# уже найденные факты
# --------------------------------------------------


def compare_group_with_facts(candidate):
    group = candidate.get("official_group")

    if not group:
        return candidate

    shout_text = group.get("shout", "").lower()

    if not shout_text:
        return candidate

    facts = candidate.get("facts", [])

    confirmations = []

    for fact in facts:
        fact_text = fact.get("text", "")

        kind = fact.get("kind", "")

        matched = False

        # Сравниваем не всю строку,
        # а ключевые сущности.
        keywords = find_keywords(fact_text)

        for keyword in keywords:
            if keyword.lower() in shout_text:
                matched = True
                break

        if matched:
            confirmations.append(
                {
                    "kind": kind,
                    "fact": fact_text,
                    "confirmed_by": ("official_roblox_group"),
                }
            )

    candidate["cross_source_confirmations"] = confirmations

    # --------------------------------------------------
    # Если один и тот же сигнал
    # есть и в description,
    # и в официальной группе,
    # это действительно усиливает уверенность.
    # --------------------------------------------------

    if confirmations:
        candidate["score"] = min(candidate.get("score", 0) + 1, 10)

    return candidate


# --------------------------------------------------
# Confidence
# --------------------------------------------------


def update_confidence(candidate):
    score = candidate.get("score", 0)

    confirmations = candidate.get("cross_source_confirmations", [])

    if score >= 8 or (score >= 6 and confirmations):
        candidate["confidence"] = "high"

    elif score >= 5:
        candidate["confidence"] = "medium"

    else:
        candidate["confidence"] = "low"

    return candidate


# --------------------------------------------------
# Проверка одного кандидата
# --------------------------------------------------


def verify_candidate(
    candidate,
    source_registry,
    group_lookup,
    group_fetch_error,
    external_results,
    external_history,
    now,
):
    # Каждый запуск формирует sources
    # заново, без мусора от старых запусков.
    candidate["sources"] = []

    candidate["cross_source_confirmations"] = []

    candidate["source_diagnostics"] = [
        {
            "source_type": "official_game_description",
            "source_url": candidate.get("roblox_game_url"),
            "latest_published_at": candidate.get("updated"),
            "status": ("accepted" if candidate.get("facts") else "rejected"),
            "result_code": (
                FOUND_VERIFIED if candidate.get("facts") else NO_NEW_CONTENT
            ),
            "available": bool(candidate.get("description")),
            "article_found": bool(candidate.get("added_lines")),
            "date_found": bool(candidate.get("updated")),
            "content_found": bool(candidate.get("description")),
            "extraction_success": bool(candidate.get("facts")),
            "verification_passed": bool(candidate.get("facts")),
            "reason": (
                "Найдена новая конкретная строка описания."
                if candidate.get("facts")
                else "Нет новой конкретной строки со времени прошлого снимка."
            ),
        }
    ]

    candidate = verify_official_description(candidate)

    candidate = verify_registry_group(
        candidate, source_registry, group_lookup, group_fetch_error
    )

    if candidate.get("source_diagnostics"):
        candidate["source_diagnostics"][0]["source_url"] = candidate.get(
            "source_registry", {}
        ).get("roblox_game_url")

    registry = candidate.get("source_registry", {})
    group = candidate.get("official_group")
    candidate["source_diagnostics"].append(
        {
            "source_type": "official_roblox_group",
            "source_url": registry.get("roblox_group_url"),
            "latest_published_at": None,
            "status": "checked",
            "result_code": NO_NEW_CONTENT,
            "available": bool(group),
            "article_found": False,
            "date_found": False,
            "content_found": bool(group and group.get("description")),
            "extraction_success": False,
            "verification_passed": False,
            "reason": (
                "Официальная группа подтверждена; датированной новости нет."
                if group and group.get("name_matches_registry")
                else candidate.get(
                    "group_verification_note", "Группа не дала датированную публикацию."
                )
            ),
        }
    )

    candidate = enrich_with_external_news(
        candidate, external_results, external_history, now
    )

    candidate = compare_group_with_facts(candidate)

    candidate = update_confidence(candidate)

    external_diagnostics = candidate.get("external_source_diagnostics", [])

    if external_diagnostics:
        candidate["source_diagnostics"][0:0] = external_diagnostics

    candidate["candidate_decision"] = {
        "status": ("accepted" if candidate.get("score", 0) >= 5 else "rejected"),
        "reason": (
            "Есть достойный свежий факт."
            if candidate.get("score", 0) >= 5
            else "Нет свежего факта с редакционным баллом 5 или выше."
        ),
    }

    return candidate


# --------------------------------------------------
# Основной запуск
# --------------------------------------------------

candidates = load_json("news_candidates.json", [])

source_registry = load_json("official_sources.json", {})

external_results = load_json("external_news_raw.json", [])

secondary_results = load_json("secondary_news_raw.json", [])
external_results.extend(secondary_results)

external_history = load_json("external_news_history.json", [])

now = datetime.now(timezone.utc)

group_ids = [
    config["roblox_group_id"]
    for config in source_registry.values()
    if config.get("roblox_group_id")
]

group_lookup = {}
group_fetch_error = None

try:
    group_lookup = fetch_groups(group_ids)
except requests.RequestException as error:
    group_fetch_error = str(error)


verified = []


for candidate in candidates:
    verified_candidate = verify_candidate(
        candidate,
        source_registry,
        group_lookup,
        group_fetch_error,
        external_results,
        external_history,
        now,
    )

    verified.append(verified_candidate)


verified.sort(key=lambda item: item.get("score", 0), reverse=True)


save_json("verified_news.json", verified)


print_source_health_report(verified, title="NEWS SOURCE HEALTH — ROBLOX")


# --------------------------------------------------
# Вывод в Actions
# --------------------------------------------------

print(f"Проверено кандидатов: " f"{len(verified)}")

print(f"Игр в реестре источников: " f"{len(source_registry)}")


for item in verified:
    print()
    print("Игра:", item.get("game", "?"))

    print("Score:", item.get("score", 0))

    print("Confidence:", item.get("confidence", "low"))

    diagnostics = item.get("source_diagnostics", [])

    for diagnostic in diagnostics:
        print(
            "Проверен источник:",
            diagnostic.get("source_type"),
            diagnostic.get("source_url") or "—",
        )
        print("Последняя дата:", diagnostic.get("latest_published_at") or "не найдена")
        print(
            "Результат источника:",
            diagnostic.get("status"),
            "—",
            diagnostic.get("reason"),
        )

    decision = item.get("candidate_decision", {})
    print("Решение по кандидату:", decision.get("status"), "—", decision.get("reason"))

    sources = item.get("sources", [])

    print("Источники:", [source.get("type") for source in sources])

    facts = item.get("facts", [])

    if facts:
        print("Факты:")

        for fact in facts[:3]:
            print("  •", f"[{fact.get('value', 0)}]", fact.get("text", ""))

    group = item.get("official_group")

    if group:
        print("Группа:", group.get("name", ""))

        print("Совпадает с реестром:", group.get("name_matches_registry"))

        if group.get("shout"):
            print("Shout:", group.get("shout"))

    confirmations = item.get("cross_source_confirmations", [])

    if confirmations:
        print("Подтверждено вторым " "источником:", len(confirmations))

    external_article = item.get("external_news_article")

    if external_article:
        print("Официальная статья:", external_article.get("title", ""))

        print("URL статьи:", external_article.get("url", ""))
