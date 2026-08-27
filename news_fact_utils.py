import re

CONTENT_TERMS = {
    "locations": (
        "LANDMARK",
        "LOCATION",
        "PRISON",
        "BANK",
        "SCHOOL",
        "HOSPITAL",
        "ISLAND",
        "MAP",
        "FACILITY",
        "BUILDING",
    ),
    "vehicle": (
        "VEHICLE",
        "CAR",
        "TRUCK",
        "BUS",
        "BIKE",
        "BOAT",
        "HELICOPTER",
        "PLANE",
    ),
    "mechanics_storage": (
        "STORAGE",
        "BACKPACK",
        "INVENTORY",
        "MOVE ITEMS",
        "MULTIPLE ITEMS",
        "TABS",
        "LOCKDOWN",
        "ESCAPE ROUTES",
    ),
    "pets": ("PET", "PETS", "EGG", "EGGS", "LEGENDARY", "ULTRA RARE"),
    "quests": (
        "QUEST",
        "QUESTS",
        "TASK",
        "TASKS",
        "CONTRACT",
        "CONTRACTS",
        "MISSION",
        "MISSIONS",
        "REWARD",
        "REWARDS",
    ),
    "event": ("EVENT", "CASE", "FESTIVAL", "PARTY"),
    "items": (
        "TOOL",
        "TOOLS",
        "ITEM",
        "ITEMS",
        "HANDCUFF",
        "HANDCUFFS",
        "PISTOL",
        "LAUNCHER",
        "SHANK",
        "WAND",
        "WEAPON",
        "WEAPONS",
        "PROP",
        "PROPS",
        "OUTFIT",
        "OUTFITS",
        "SCANNER",
    ),
}


ITEM_NAMES_RU = (
    ("tear gas launcher", "пусковую установку со слезоточивым газом"),
    ("scanner wand", "сканирующую палочку"),
    ("security scanner", "сканер безопасности"),
    ("handcuffs", "наручники"),
    ("pistol", "пистолет"),
    ("shank", "заточку"),
    ("spotlight", "прожектор"),
    ("alarm", "сигнализацию"),
    ("yard props", "реквизит для тюремного двора"),
    ("jail building props", "детали здания тюрьмы"),
    ("prison props", "тюремный реквизит"),
    ("credit cards", "банковские карты"),
    ("cash bags", "мешки с деньгами"),
    ("keycards", "ключ-карты"),
)


VEHICLE_NAMES_RU = (
    ("prisoner bus", "тюремный автобус"),
    ("prison bus", "тюремный автобус"),
    ("armored bank truck", "бронированный банковский грузовик"),
    ("rocket car", "ракетную машину"),
)


def clean_content_line(line):
    line = re.sub(r"^[^A-Za-zА-Яа-я0-9]+", "", line.strip())
    return re.sub(r"\s+", " ", line).strip()


def _contains_term(upper, term):
    return bool(re.search(rf"(?<![A-Z0-9]){re.escape(term)}(?![A-Z0-9])", upper))


def classify_content_line(line):
    upper = clean_content_line(line).upper()

    if not upper:
        return None

    if any(
        _contains_term(upper, term)
        for term in ("LANDMARK", "LOCATION", "NEW MAP", "NEW PRISON")
    ):
        return "locations"

    for kind in (
        "mechanics_storage",
        "pets",
        "quests",
        "event",
        "vehicle",
        "items",
        "locations",
    ):
        if any(_contains_term(upper, term) for term in CONTENT_TERMS[kind]):
            return kind

    return None


def _found_names(text, translations):
    lower = text.lower()
    result = []

    for english, russian in translations:
        if english in lower and russian not in result:
            result.append(russian)

    return result


def _join_ru(values):
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + " и " + values[-1]


def summarize_content_line_ru(line, kind):
    clean = clean_content_line(line)
    lower = clean.lower()

    if kind == "locations":
        if "prison" in lower:
            result = "В игре появилась новая локация — тюрьма."
            item_names = _found_names(clean, ITEM_NAMES_RU)
            vehicle_names = _found_names(clean, VEHICLE_NAMES_RU)
            extras = item_names + vehicle_names

            if extras:
                result += " Для ролевых сцен добавили " + _join_ru(extras) + "."

            return result
        if "bank" in lower:
            return "В игре открылся обновлённый банк."
        if "school" in lower:
            return "В игре появилась новая локация — школа."
        if "hospital" in lower:
            return "В игре появилась новая локация — больница."
        return "В игре появилась новая локация."

    if kind == "vehicle":
        names = _found_names(clean, VEHICLE_NAMES_RU)
        if names:
            return f"В игру добавили {_join_ru(names)}."
        return "В игру добавили новый транспорт."

    if kind == "items":
        names = _found_names(clean, ITEM_NAMES_RU)
        if names:
            prefix = (
                "Для смотрителя добавили " if "warden" in lower else "В игру добавили "
            )
            return prefix + _join_ru(names) + "."
        if "prop" in lower:
            return "Добавили новый реквизит для ролевых сцен."
        if "tool" in lower or "weapon" in lower:
            return "В игре появились новые инструменты и оружие."
        return "В игре появились новые предметы."

    if kind == "mechanics_storage":
        if "storage" in lower or "backpack" in lower:
            return "Появилось отдельное хранилище для предметов " "из рюкзака."
        if "lockdown" in lower:
            return "В тюрьме можно включать режим изоляции."
        return "В игре появилась новая полезная механика."

    if kind == "pets":
        egg_match = re.search(
            r"(.+?)\s+found in\s+(.+?\bEggs?)", clean, flags=re.IGNORECASE
        )
        if egg_match:
            return (
                f"Питомца {egg_match.group(1).strip()} теперь можно "
                f"получить из яиц {egg_match.group(2).strip()}."
            )
        return "В игре появились новые питомцы."

    if kind == "quests":
        if "reward" in lower:
            return "Появились новые задания с наградами."
        return "В игре появились новые задания."

    if kind == "event":
        return "В игре началось новое событие."

    if kind == "map":
        return "В игре появилась новая карта."

    if kind == "boss":
        return "В игре появился новый босс."

    if kind == "season":
        return "В игре стартовал новый сезон."

    if kind == "limited":
        return "Появился ограниченный по времени контент."

    if kind == "code":
        return "Появился новый код на бесплатную награду."

    if kind == "update":
        return "В игре вышло новое обновление."

    return None
