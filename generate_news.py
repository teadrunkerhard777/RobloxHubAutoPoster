import json
import requests

from datetime import datetime, timezone, timedelta


FRESHNESS_HOURS = 48


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


def description_changed(
    universe_id,
    current_description,
    snapshots
):
    previous = snapshots.get(
        str(universe_id)
    )

    if previous is None:
        return False

    previous_description = previous.get(
        "description",
        ""
    )

    return (
        previous_description.strip()
        != current_description.strip()
    )


def build_candidates(
    games,
    snapshots
):
    candidates = []

    for game in games:
        universe_id = game["id"]

        description = game.get(
            "description",
            ""
        )

        changed = description_changed(
            universe_id,
            description,
            snapshots
        )

        fresh = is_fresh(game)

        if not fresh and not changed:
            continue

        sources = [
            {
                "type": "roblox_api",
                "verified": True
            }
        ]

        confidence = "signal_only"

        if changed:
            confidence = "description_changed"

        candidate = {
            "game": game["name"],
            "universe_id": universe_id,
            "updated_at": game["updated"],
            "description": description,
            "description_changed": changed,
            "playing": game.get("playing"),
            "visits": game.get("visits"),
            "sources": sources,
            "confidence": confidence
        }

        candidates.append(candidate)

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
            "updated": game["updated"],
            "checked_at": checked_at
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
        candidate[
            "description_changed"
        ]
    )

    print(
        "Confidence:",
        candidate["confidence"]
    )
