import json
import re
from datetime import datetime, timezone

import requests

from news_fact_utils import classify_content_line, summarize_content_line_ru

GAMES_FILE = "games.json"
SNAPSHOTS_FILE = "game_snapshots.json"
OUTPUT_FILE = "news_candidates.json"

ROBLOX_GAMES_API = "https://games.roblox.com/v1/games"

REQUEST_TIMEOUT = 20


# --------------------------------------------------
# Какие слова вообще могут указывать на контент
# --------------------------------------------------

NEWS_KEYWORDS = {
    "UPDATE",
    "EVENT",
    "NEW",
    "CODE",
    "CODES",
    "REWARD",
    "REWARDS",
    "QUEST",
    "QUESTS",
    "BOSS",
    "MAP",
    "VEHICLE",
    "VEHICLES",
    "PET",
    "PETS",
    "ITEM",
    "ITEMS",
    "SEASON",
    "LIMITED",
    "CONTRACT",
    "CONTRACTS",
}


# --------------------------------------------------
# JSON
# --------------------------------------------------


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


# --------------------------------------------------
# Текст
# --------------------------------------------------


def clean_line(line):
    line = line.strip()

    line = re.sub(r"\s+", " ", line)

    return line


def split_description(description):
    if not description:
        return []

    lines = []

    for raw_line in description.splitlines():
        line = clean_line(raw_line)

        if line:
            lines.append(line)

    return lines


def get_added_lines(old_description, new_description):
    old_lines = set(split_description(old_description))

    new_lines = split_description(new_description)

    return [line for line in new_lines if line not in old_lines]


def find_keywords(text):
    if not text:
        return []

    upper_text = text.upper()

    found = []

    for keyword in NEWS_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", upper_text):
            found.append(keyword)

    return sorted(found)


# --------------------------------------------------
# Определение фактов
# --------------------------------------------------


def has_any(upper, phrases):
    return any(phrase in upper for phrase in phrases)


def make_fact(line, kind, value, reason, specific=True):
    fact = {
        "text": line,
        "kind": kind,
        "value": value,
        "specific": specific,
        "reason": reason,
    }

    summary_ru = summarize_content_line_ru(line, kind)

    if summary_ru:
        fact["summary_ru"] = summary_ru

    return fact


def analyze_line(line):
    """
    Возвращает факт и его редакционную ценность.

    0 = не новость
    2 = почти пустой сигнал
    3-4 = слабая новость
    5-6 = нормальная новость
    7-10 = сильная новость
    """

    upper = line.upper()

    # Новые строки Roblox description могут быть содержательными и без
    # служебных слов NEW/UPDATE. Категория определяется по самой игровой
    # сущности: локации, транспорту, инструментам, питомцам и механикам.
    semantic_kind = classify_content_line(line)

    # Конкретные строки из описаний часто не содержат слово EVENT.
    # Важна не метка UPDATE сама по себе, а названное изменение после неё.
    if re.search(r"\bFOUND IN\b.+\bEGGS?\b", upper):
        return make_fact(
            line=line,
            kind="pets",
            value=8,
            reason="Назван питомец и способ его получения",
        )

    if re.match(r"^[^A-Z0-9]*FIND\b.+\bFOR\b", upper):
        return make_fact(
            line=line, kind="quests", value=7, reason="Описано конкретное задание"
        )

    if " CASE" in upper or upper.endswith("CASE"):
        return make_fact(
            line=line,
            kind="event",
            value=7,
            reason="Названо конкретное игровое событие",
        )

    if semantic_kind:
        semantic_values = {
            "pets": 8,
            "quests": 7,
            "event": 7,
            "vehicle": 8,
            "locations": 8,
            "mechanics_storage": 8,
            "items": 7,
        }

        return make_fact(
            line=line,
            kind=semantic_kind,
            value=semantic_values[semantic_kind],
            reason=("Строка называет конкретное игровое содержимое"),
        )

    concrete_update = re.search(
        r"\b(?:LATEST\s+)?(?:NEW|UPDATED)?\s*"
        r"([A-Z][A-Z0-9 '&]+?)\s+UPDATE\s*[-–—:]\s*(.+)",
        upper,
    )

    if concrete_update and len(concrete_update.group(2).strip()) >= 12:
        return make_fact(
            line=line,
            kind="update",
            value=7,
            reason="Обновление с названной темой и подробностью",
        )

    concrete_change = re.match(
        r"^[^A-Z0-9]*(?:NEW|UPDATED)\s+" r"([A-Z0-9 '&]+?)\s*[-–—:]\s*(.+)", upper
    )

    if concrete_change and len(concrete_change.group(2).strip()) >= 12:
        kind = (
            "vehicle"
            if has_any(
                concrete_change.group(1), ("CAR", "TRUCK", "VEHICLE", "BIKE", "BOAT")
            )
            else "items"
        )

        return make_fact(
            line=line,
            kind=kind,
            value=7,
            reason="Названо конкретное новое или обновлённое содержимое",
        )

    # ------------------------------------------------
    # Бесплатные награды / коды
    # ------------------------------------------------

    if re.search(r"\bCODES?\b", upper) and has_any(
        upper, ("FREE", "REWARD", "REWARDS", "REDEEM")
    ):
        return make_fact(
            line=line, kind="code", value=10, reason=("Код или бесплатная награда")
        )

    # ------------------------------------------------
    # Событие + награды / контракты / задания
    # ------------------------------------------------

    if "EVENT" in upper:
        if has_any(
            upper, ("REWARD", "REWARDS", "CONTRACT", "CONTRACTS", "QUEST", "QUESTS")
        ):
            return make_fact(
                line=line,
                kind="event",
                value=9,
                reason=("Событие с конкретной " "активностью или наградами"),
            )

        return make_fact(line=line, kind="event", value=7, reason="Игровое событие")

    # ------------------------------------------------
    # Контракты / задания с наградами
    # ------------------------------------------------

    if has_any(upper, ("CONTRACT", "CONTRACTS", "QUEST", "QUESTS")):
        if has_any(upper, ("REWARD", "REWARDS", "EXCLUSIVE")):
            return make_fact(
                line=line, kind="quests", value=8, reason=("Задания с наградами")
            )

        return make_fact(line=line, kind="quests", value=6, reason="Новые задания")

    # ------------------------------------------------
    # Новый босс
    # ------------------------------------------------

    if "NEW BOSS" in upper or ("BOSS" in upper and "NEW" in upper):
        return make_fact(line=line, kind="boss", value=8, reason="Новый босс")

    # ------------------------------------------------
    # Новая карта
    # ------------------------------------------------

    if "NEW MAP" in upper or ("MAP" in upper and "NEW" in upper):
        return make_fact(line=line, kind="map", value=7, reason="Новая карта")

    # ------------------------------------------------
    # Новый транспорт
    # ------------------------------------------------

    if has_any(upper, ("NEW VEHICLE", "NEW CAR", "NEW BIKE", "NEW BOAT")):
        return make_fact(line=line, kind="vehicle", value=7, reason="Новый транспорт")

    # ------------------------------------------------
    # Новый сезон
    # ------------------------------------------------

    if "SEASON" in upper:
        return make_fact(line=line, kind="season", value=7, reason="Новый сезон")

    # ------------------------------------------------
    # Limited
    # ------------------------------------------------

    if "LIMITED" in upper:
        return make_fact(
            line=line,
            kind="limited",
            value=7,
            reason=("Ограниченный по времени контент"),
        )

    # ------------------------------------------------
    # Новые питомцы
    # ------------------------------------------------

    if "NEW PET" in upper or "NEW PETS" in upper:
        return make_fact(line=line, kind="pets", value=6, reason="Новые питомцы")

    # ------------------------------------------------
    # Новые предметы
    #
    # Это намеренно СЛАБЫЙ факт.
    # "NEW ITEMS!" само по себе больше
    # не должно становиться главной новостью дня.
    # ------------------------------------------------

    if "NEW ITEM" in upper or "NEW ITEMS" in upper:
        return make_fact(
            line=line, kind="items", value=4, reason=("Новые предметы без подробностей")
        )

    # ------------------------------------------------
    # Update с номером
    #
    # UPDATE 21 — уже полезнее,
    # чем просто UPDATE.
    # ------------------------------------------------

    update_number = re.search(r"\bUPDATE\s*#?\s*(\d+)\b", upper)

    if update_number:
        return make_fact(
            line=line,
            kind="update",
            value=6,
            reason=("Обновление с конкретным номером"),
        )

    # ------------------------------------------------
    # Просто "UPDATE"
    #
    # Практически ничего не сообщает.
    # ------------------------------------------------

    if "UPDATE" in upper:
        return make_fact(
            line=line,
            kind="update",
            value=2,
            reason=("Упоминание обновления " "без конкретики"),
            specific=False,
        )

    return None


def extract_facts(description, added_lines):
    lines = split_description(description)

    facts = []

    added_set = set(added_lines)

    for line in lines:
        fact = analyze_line(line)

        if fact is None:
            continue

        fact["is_new_line"] = line in added_set

        # Новая строка в описании —
        # сильный сигнал, но не сама новость.
        if fact["is_new_line"]:
            fact["value"] += 2

        facts.append(fact)

    # Самые содержательные факты наверх.
    facts.sort(key=lambda item: (item["value"], item["specific"]), reverse=True)

    return facts


# --------------------------------------------------
# Confidence
# --------------------------------------------------


def score_to_confidence(score):
    if score >= 8:
        return "high"

    if score >= 5:
        return "medium"

    return "low"


# --------------------------------------------------
# Roblox API
# --------------------------------------------------


def fetch_games(universe_ids):
    response = requests.get(
        ROBLOX_GAMES_API,
        params={"universeIds": ",".join(str(value) for value in universe_ids)},
        timeout=REQUEST_TIMEOUT,
    )

    response.raise_for_status()

    data = response.json()

    return data.get("data", [])


# --------------------------------------------------
# Основной код
# --------------------------------------------------

games_config = load_json(GAMES_FILE)

old_snapshots = load_json(SNAPSHOTS_FILE, {})


universe_ids = [game["universe_id"] for game in games_config]


print()
print(f"Проверяем игр: " f"{len(universe_ids)}")


try:
    api_games = fetch_games(universe_ids)

except requests.RequestException as error:
    print()
    print("Ошибка Roblox Games API:")
    print(str(error))

    raise SystemExit(1)


api_by_id = {int(game["id"]): game for game in api_games}


candidates = []
new_snapshots = {}


for config in games_config:
    universe_id = int(config["universe_id"])

    configured_name = config["name"]

    api_game = api_by_id.get(universe_id)

    if api_game is None:
        print(f"⚠️ {configured_name}: " "Roblox API не вернул игру.")

        continue

    description = api_game.get("description") or ""

    updated = api_game.get("updated")

    created = api_game.get("created")

    creator = api_game.get("creator")

    previous = old_snapshots.get(str(universe_id), {})

    previous_description = previous.get("description") or ""

    description_changed = previous_description != description and bool(
        previous_description
    )

    # Первый увиденный description — снимок состояния, а не доказательство
    # того, что весь перечисленный в нём контент появился сегодня.
    if previous_description:
        added_lines = get_added_lines(previous_description, description)
    else:
        added_lines = []

    analyzed_facts = extract_facts(description, added_lines)

    # Для публикации годятся только новые строки текущего снимка.
    # Иначе один и тот же UPDATE из неизменного description повторялся бы
    # каждое утро без собственной даты публикации.
    facts = [fact for fact in analyzed_facts if fact.get("is_new_line")]

    keywords = find_keywords(description)

    # ------------------------------------------------
    # Итоговый score игры
    #
    # Берём ценность лучшего ФАКТА,
    # а не количество слов UPDATE/NEW.
    # ------------------------------------------------

    if facts:
        score = facts[0]["value"]
    else:
        score = 0

    # Реальное изменение описания —
    # дополнительное подтверждение свежести.
    if description_changed:
        score += 1

    score = min(score, 10)

    confidence = score_to_confidence(score)

    candidate = {
        "game": configured_name,
        "universe_id": universe_id,
        # Сохраняем API-имя отдельно.
        "roblox_name": api_game.get("name", configured_name),
        "description": description,
        "updated": updated,
        "created": created,
        "creator": creator,
        # Старые поля оставляем,
        # чтобы verify_news.py не сломался.
        "description_changed": (description_changed),
        "added_lines": added_lines,
        "keywords": keywords,
        "score": score,
        "confidence": confidence,
        # Новый главный слой.
        "facts": facts,
        "description_facts": analyzed_facts,
        "priority": config.get("priority", False),
        "checked_at": (datetime.now(timezone.utc).isoformat()),
    }

    candidates.append(candidate)

    new_snapshots[str(universe_id)] = {
        "game": configured_name,
        "roblox_name": api_game.get("name", configured_name),
        "description": description,
        "updated": updated,
        "checked_at": (datetime.now(timezone.utc).isoformat()),
    }


# --------------------------------------------------
# Самые ценные кандидаты наверх
# --------------------------------------------------

candidates.sort(
    key=lambda item: (item["score"], item.get("priority", False)), reverse=True
)


save_json(OUTPUT_FILE, candidates)

save_json(SNAPSHOTS_FILE, new_snapshots)


# --------------------------------------------------
# Отчёт в Actions
# --------------------------------------------------

print()
print("Результаты:")

print()


for candidate in candidates:
    facts = candidate.get("facts", [])

    print(f"{candidate['game']}")

    print(f"  score: " f"{candidate['score']}")

    print(f"  confidence: " f"{candidate['confidence']}")

    print(f"  description_changed: " f"{candidate['description_changed']}")

    if not facts:
        print("  фактов: нет")

    else:
        print(f"  фактов: " f"{len(facts)}")

        for fact in facts[:3]:
            marker = "🆕" if fact["is_new_line"] else "•"

            print(
                f"  {marker} "
                f"[{fact['value']}] "
                f"{fact['kind']}: "
                f"{fact['text']}"
            )

    print()


print(f"Сохранено: " f"{OUTPUT_FILE}")

print(f"Снимки обновлены: " f"{SNAPSHOTS_FILE}")
