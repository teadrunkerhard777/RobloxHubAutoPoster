import json
import requests


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
    "CONTRACTS"
]


def load_json(filename, default):
    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except FileNotFoundError:
        return default


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


def find_keywords(text):
    if not text:
        return []

    text_upper = text.upper()

    return [
        keyword
        for keyword in NEWS_KEYWORDS
        if keyword in text_upper
    ]


def extract_news_lines(text):
    if not text:
        return []

    interesting_lines = []

    for line in text.splitlines():
        clean_line = line.strip()

        if not clean_line:
            continue

        if find_keywords(clean_line):
            interesting_lines.append(
                clean_line
            )

    return interesting_lines


def fetch_group(group_id):
    url = (
        "https://groups.roblox.com/"
        f"v1/groups/{group_id}"
    )

    response = requests.get(
        url,
        timeout=15
    )

    response.raise_for_status()

    return response.json()


# --------------------------------------------------
# Проверка официального описания игры
# --------------------------------------------------

def verify_official_description(candidate):
    # Новый generate_news.py использует
    # поле description.
    #
    # current_description оставляем
    # как fallback для совместимости.
    description = candidate.get(
        "description"
    )

    if description is None:
        description = candidate.get(
            "current_description",
            ""
        )

    keywords = find_keywords(
        description
    )

    # Если новый генератор уже выделил факты,
    # используем именно их.
    facts = candidate.get(
        "facts",
        []
    )

    fact_lines = [
        fact.get("text", "")
        for fact in facts
        if fact.get("text")
    ]

    # Если facts почему-то нет —
    # используем старый способ.
    if fact_lines:
        news_lines = fact_lines
    else:
        news_lines = extract_news_lines(
            description
        )

    candidate[
        "official_description_analysis"
    ] = {
        "keywords": keywords,
        "news_lines": news_lines
    }

    # Источник обязательно существует.
    sources = candidate.setdefault(
        "sources",
        []
    )

    if description:
        sources.append(
            {
                "type": (
                    "official_game_description"
                ),
                "verified": True
            }
        )

    # ВАЖНО:
    # score здесь больше не повышаем.
    #
    # Новый generate_news.py уже оценил
    # содержательность фактов.
    # Иначе один факт будет считаться дважды.

    return candidate


# --------------------------------------------------
# Проверка официальной Roblox-группы
# --------------------------------------------------

def verify_group(candidate):
    creator = candidate.get(
        "creator"
    )

    if not creator:
        return candidate

    creator_type = creator.get(
        "type"
    )

    creator_id = creator.get(
        "id"
    )

    if (
        creator_type != "Group"
        or not creator_id
    ):
        return candidate

    try:
        group = fetch_group(
            creator_id
        )

    except requests.RequestException as error:
        candidate[
            "group_verification_note"
        ] = str(error)

        return candidate

    shout = group.get(
        "shout"
    )

    shout_text = ""

    if isinstance(shout, dict):
        shout_text = shout.get(
            "body",
            ""
        )

    elif isinstance(shout, str):
        shout_text = shout

    shout_keywords = find_keywords(
        shout_text
    )

    candidate[
        "official_group"
    ] = {
        "id": group.get(
            "id"
        ),
        "name": group.get(
            "name"
        ),
        "shout": shout_text,
        "keywords": shout_keywords
    }

    sources = candidate.setdefault(
        "sources",
        []
    )

    sources.append(
        {
            "type": (
                "official_roblox_group"
            ),
            "verified": True
        }
    )

    # Shout повышает score только если
    # действительно содержит новостный сигнал.
    if shout_keywords:
        candidate["score"] = min(
            candidate.get(
                "score",
                0
            ) + 1,
            10
        )

    return candidate


# --------------------------------------------------
# Confidence
# --------------------------------------------------

def update_confidence(candidate):
    score = candidate.get(
        "score",
        0
    )

    if score >= 8:
        candidate[
            "confidence"
        ] = "high"

    elif score >= 5:
        candidate[
            "confidence"
        ] = "medium"

    else:
        candidate[
            "confidence"
        ] = "low"

    return candidate


# --------------------------------------------------
# Полная проверка одного кандидата
# --------------------------------------------------

def verify_candidate(candidate):
    # Страховка для старых и новых данных.
    candidate.setdefault(
        "sources",
        []
    )

    candidate = (
        verify_official_description(
            candidate
        )
    )

    candidate = verify_group(
        candidate
    )

    candidate = update_confidence(
        candidate
    )

    return candidate


# --------------------------------------------------
# Основной запуск
# --------------------------------------------------

candidates = load_json(
    "news_candidates.json",
    []
)


verified = []


for candidate in candidates:
    verified_candidate = (
        verify_candidate(
            candidate
        )
    )

    verified.append(
        verified_candidate
    )


verified.sort(
    key=lambda item: item.get(
        "score",
        0
    ),
    reverse=True
)


save_json(
    "verified_news.json",
    verified
)


print(
    f"Проверено кандидатов: "
    f"{len(verified)}"
)


for item in verified:
    print()

    print(
        "Игра:",
        item.get(
            "game",
            "?"
        )
    )

    print(
        "Score:",
        item.get(
            "score",
            0
        )
    )

    print(
        "Confidence:",
        item.get(
            "confidence",
            "low"
        )
    )

    facts = item.get(
        "facts",
        []
    )

    if facts:
        print(
            "Факты:"
        )

        for fact in facts[:3]:
            print(
                "  •",
                f"[{fact.get('value', 0)}]",
                fact.get(
                    "text",
                    ""
                )
            )

    group = item.get(
        "official_group"
    )

    if group:
        print(
            "Группа:",
            group.get(
                "name",
                ""
            )
        )

        if group.get(
            "shout"
        ):
            print(
                "Shout:",
                group["shout"]
            )
