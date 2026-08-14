import json
import requests


NEWS_KEYWORDS = [
    "UPDATE",
    "NEW",
    "EVENT",
    "CODE",
    "BOSS",
    "ITEM",
    "MAP",
    "PETS",
    "LIMITED",
    "REWARD",
    "CARNIVAL",
    "QUEST",
    "SEASON"
]


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)
    except FileNotFoundError:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
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

        keywords = find_keywords(
            clean_line
        )

        if keywords:
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


def verify_official_description(candidate):
    description = candidate.get(
        "current_description",
        ""
    )

    keywords = find_keywords(
        description
    )

    news_lines = extract_news_lines(
        description
    )

    candidate[
        "official_description_analysis"
    ] = {
        "keywords": keywords,
        "news_lines": news_lines
    }

    if news_lines:
        candidate["score"] += 2

        candidate["sources"].append(
            {
                "type": "official_game_description",
                "verified": True
            }
        )

    return candidate


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

    if creator_type != "Group":
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
        "id": group.get("id"),
        "name": group.get("name"),
        "shout": shout_text,
        "keywords": shout_keywords
    }

    candidate["sources"].append(
        {
            "type": "official_roblox_group",
            "verified": True
        }
    )

    if shout_keywords:
        candidate["score"] += 3

    return candidate


def update_confidence(candidate):
    score = candidate.get(
        "score",
        0
    )

    if score >= 8:
        candidate["confidence"] = "high"

    elif score >= 5:
        candidate["confidence"] = "medium"

    else:
        candidate["confidence"] = "low"

    return candidate


def verify_candidate(candidate):
    candidate = verify_official_description(
        candidate
    )

    candidate = verify_group(
        candidate
    )

    candidate = update_confidence(
        candidate
    )

    return candidate


candidates = load_json(
    "news_candidates.json",
    []
)


verified = []


for candidate in candidates:
    verified_candidate = verify_candidate(
        candidate
    )

    verified.append(
        verified_candidate
    )


verified.sort(
    key=lambda item: item["score"],
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
        item["game"]
    )

    print(
        "Score:",
        item["score"]
    )

    print(
        "Confidence:",
        item["confidence"]
    )

    description_analysis = item.get(
        "official_description_analysis",
        {}
    )

    print(
        "Ключевые слова:",
        description_analysis.get(
            "keywords",
            []
        )
    )

    print(
        "Новостные строки:"
    )

    for line in description_analysis.get(
        "news_lines",
        []
    ):
        print(
            "  •",
            line
        )

    group = item.get(
        "official_group"
    )

    if group:
        print(
            "Группа:",
            group["name"]
        )

        print(
            "Shout:",
            group["shout"]
        )
