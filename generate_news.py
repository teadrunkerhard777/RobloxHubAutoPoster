import json
import requests

from datetime import datetime, timezone, timedelta


FRESHNESS_HOURS = 48


def load_games():
    with open("games.json", "r", encoding="utf-8") as file:
        games = json.load(file)

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


def get_fresh_games(games):
    now = datetime.now(timezone.utc)

    freshness_limit = now - timedelta(
        hours=FRESHNESS_HOURS
    )

    fresh_games = []

    for game in games:
        updated_at = parse_roblox_datetime(
            game["updated"]
        )

        if updated_at >= freshness_limit:
            fresh_games.append(game)

    return fresh_games


def save_news_data(data):
    with open(
        "news_data.json",
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


try:
    tracked_games = load_games()

    print(
        f"Игр с известным universe_id: "
        f"{len(tracked_games)}"
    )

    games = fetch_game_data(
        tracked_games
    )

    fresh_games = get_fresh_games(
        games
    )

    save_news_data(
        fresh_games
    )

    print("Данные Roblox получены.")

    print(
        f"Свежих обновлений за последние "
        f"{FRESHNESS_HOURS} часов: "
        f"{len(fresh_games)}"
    )

    if not fresh_games:
        print("Свежих обновлений нет.")

    for game in fresh_games:
        print()
        print("Игра:", game["name"])
        print("Обновлена:", game["updated"])
        print(
            "Игроков сейчас:",
            game["playing"]
        )
        print(
            "Посещений:",
            game["visits"]
        )

except requests.RequestException as error:
    print("Ошибка получения данных Roblox:")
    print(error)
    raise
