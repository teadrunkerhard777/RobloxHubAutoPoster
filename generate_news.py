import json
import requests
import difflib

from datetime import datetime, timezone, timedelta


FRESHNESS_HOURS = 48

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
    "REWARD"
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


def load_games():
    games = load_json(
        "games.json",
        []
    )

    return [
        game
        for game in games
        if game["universe_id"] is not None
    ]


def fetch_game_data(games):
    universe_ids = ",".join(
        str(game["universe_id"])
        for game in games
    )

    url = (
        "https://games.roblox.com/v1/games"
        f"?universeIds={universe_ids}"
    )

    response = requests.get(
        url,
        timeout=15
    )

    response.raise_for_status()

    return response.json()["data"]


def parse_roblox_datetime(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    )


def is_fresh(game):
    now = datetime.now(timezone.utc)

    freshness_limit = now - timedelta(
        hours=FRESHNESS_HOURS
    )

    updated_at = parse_roblox_datetime(
        game["updated"]
    )

    return updated_at >= freshness_limit


def get_previous_description(
    universe_id,
    snapshots
):
    previous = snapshots.get(
        str(universe_id)
    )

    if previous is None:
        return None

    return previous.get(
        "description",
        ""
    )


def extract_added_lines(
    previous_description,
    current_description
):
    if previous_description is None:
        return []

    previous_lines = (
        previous_description
        .splitlines()
    )

    current_lines = (
        current_description
        .splitlines()
    )

    diff = difflib.ndiff(
        previous_lines,
        current_lines
    )

    added_lines = []

    for line in diff:
        if line.startswith("+ "):
            added_text = line[2:].strip()

            if added_text:
                added_lines.append(
                    added_text
                )

    return added_lines


def find_news_keywords(text):
    text_upper = text.upper()

    found = []

    for keyword in NEWS_KEYWORDS:
        if keyword in text_upper:
            found.append(keyword)

    return found


def calculate_score(
    fresh,
    description_changed,
    added_lines,
    keywords_in_added,
    keywords_in_description
):
    score = 0

    if fresh:
        score += 2

    if description_changed:
        score += 2

    if added_lines:
        score += 3

    if keywords_in_added:
        score += 3

    if keywords_in_description:
        score += 1

    return score


def score_to_confidence(score):
    if score >= 8:
        return "high"

    if score >= 5:
        return "medium"

    return "low"


def build_candidates(
    games,
    snapshots
):
    candidates = []

    for game in games:
        universe_id = game["id"]

        current_description = game.get(
            "description",
            ""
        )

        previous_description = (
            get_previous_description(
                universe_id,
                snapshots
            )
        )

        description_changed = False

        if previous_description is not None:
            description_changed = (
                previous_description.strip()
                != current_description.strip()
            )

        added_lines = extract_added_lines(
            previous_description,
            current_description
        )

        added_text = "\n".join(
            added_lines
        )

        keywords_in_added = (
            find_news_keywords(
                added_text
            )
        )

        keywords_in_description = (
            find_news_keywords(
                current_description
            )
        )

        fresh = is_fresh(game)

        if not fresh and not description_changed:
            continue

        score = calculate_score(
            fresh,
            description_changed,
            added_lines,
            keywords_in_added,
            keywords_in_description
        )

        confidence = score_to_confidence(
            score
        )

        candidate = {
            "game": game["name"],
            "universe_id": universe_id,
            "updated_at": game["updated"],

            "playing": game.get(
                "playing"
            ),

            "visits": game.get(
                "visits"
            ),

            "description_changed":
                description_changed,

            "previous_description":
                previous_description,

            "current_description":
                current_description,

            "added_lines":
                added_lines,

            "keywords_in_added":
                keywords_in_added,

            "keywords_in_description":
                keywords_in_description,

            "score":
                score,

            "confidence":
                confidence,

            "sources": [
                {
                    "type": "roblox_api",
                    "verified": True
                }
            ]
        }

        candidates.append(
            candidate
        )

    candidates.sort(
        key=lambda candidate: candidate["score"],
        reverse=True
    )

    return candidates


def update_snapshots(
    games,
    snapshots
):
    checked_at = (
        datetime.now(timezone.utc)
        .isoformat()
    )

    for game in games:
        universe_id = str(
            game["id"]
        )

        snapshots[universe_id] = {
            "name": game["name"],

            "description": game.get(
                "description",
                ""
            ),

            "updated":
                game["updated"],

            "checked_at":
                checked_at
        }

    return snapshots


tracked_games = load_games()

snapshots = load_json(
    "game_snapshots.json",
    {}
)

print(
    f"Игр в мониторинге: "
    f"{len(tracked_games)}"
)


games = fetch_game_data(
    tracked_games
)


candidates = build_candidates(
    games,
    snapshots
)


save_json(
    "news_candidates.json",
    candidates
)


snapshots = update_snapshots(
    games,
    snapshots
)


save_json(
    "game_snapshots.json",
    snapshots
)


print(
    f"Кандидатов найдено: "
    f"{len(candidates)}"
)


for candidate in candidates:
    print()

    print(
        "Игра:",
        candidate["game"]
    )

    print(
        "Обновлена:",
        candidate["updated_at"]
    )

    print(
        "Описание изменилось:",
        candidate["description_changed"]
    )

    print(
        "Новых строк:",
        len(candidate["added_lines"])
    )

    print(
        "Ключевые слова в новых строках:",
        candidate["keywords_in_added"]
    )

    print(
        "Ключевые слова в описании:",
        candidate["keywords_in_description"]
    )

    print(
        "Score:",
        candidate["score"]
    )

    print(
        "Confidence:",
        candidate["confidence"]
    )
