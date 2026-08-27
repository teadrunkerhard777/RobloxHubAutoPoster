import json
from pathlib import Path
from urllib.parse import urlparse

from tips_rotation import validate_tip_catalog

GAMES_FILE = Path("games.json")
SOURCES_FILE = Path("official_sources.json")

CONTENT_FILES = (
    Path("tips.json"),
    Path("myths.json"),
    Path("game_snapshots.json"),
    Path("news_candidates.json"),
    Path("verified_news.json"),
)

REQUIRED_SOURCE_FIELDS = (
    "universe_id",
    "root_place_id",
    "roblox_game_url",
    "roblox_group_id",
    "roblox_group_name",
    "roblox_group_url",
    "news_strategy",
    "website",
    "news_url",
    "discord",
    "youtube",
    "x",
    "verified_at",
)

NEWS_STRATEGIES = {
    "official_news_website",
    "official_youtube_feed",
    "roblox_game_description_and_group",
}


def load_json(path):
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def walk_game_names(value):
    if isinstance(value, dict):
        game = value.get("game")

        if isinstance(game, str):
            yield game

        for child in value.values():
            yield from walk_game_names(child)

    elif isinstance(value, list):
        for child in value:
            yield from walk_game_names(child)


def validate_url(value, field, game, errors):
    if value is None:
        return

    parsed = urlparse(value)

    if parsed.scheme != "https" or not parsed.netloc:
        errors.append(f"{game}: поле {field} должно содержать HTTPS URL или null.")


def validate_registry(games, sources):
    errors = []
    game_names = [game["name"] for game in games]

    if len(game_names) != 10:
        errors.append(
            f"games.json должен содержать 10 игр, найдено: {len(game_names)}."
        )

    if len(set(game_names)) != len(game_names):
        errors.append("В games.json есть повторяющиеся названия игр.")

    if set(game_names) != set(sources):
        missing = sorted(set(game_names) - set(sources))
        extra = sorted(set(sources) - set(game_names))

        if missing:
            errors.append("Нет источников для игр: " + ", ".join(missing) + ".")

        if extra:
            errors.append(
                "Лишние игры в official_sources.json: " + ", ".join(extra) + "."
            )

    for game in games:
        name = game["name"]
        source = sources.get(name)

        if source is None:
            continue

        missing_fields = [
            field for field in REQUIRED_SOURCE_FIELDS if field not in source
        ]

        if missing_fields:
            errors.append(f"{name}: отсутствуют поля: {', '.join(missing_fields)}.")
            continue

        if source["universe_id"] != game["universe_id"]:
            errors.append(f"{name}: universe_id не совпадает с games.json.")

        if source["news_strategy"] not in NEWS_STRATEGIES:
            errors.append(f"{name}: неизвестная стратегия новостей.")

        if (
            source["news_strategy"] == "official_news_website"
            and not source["news_url"]
        ):
            errors.append(f"{name}: для официального сайта не указан news_url.")

        if source["news_strategy"] == "official_youtube_feed":
            if not source.get("youtube"):
                errors.append(f"{name}: не указан официальный YouTube-канал.")

            if not source.get("youtube_feed_url"):
                errors.append(f"{name}: не указан публичный YouTube RSS.")

            if not source.get("youtube_match_terms"):
                errors.append(f"{name}: не заданы фильтры игры для YouTube RSS.")

            if not source.get("youtube_channel_name"):
                errors.append(f"{name}: не задано имя официального YouTube-канала.")

        if (
            source["news_strategy"] == "roblox_game_description_and_group"
            and source["news_url"] is not None
        ):
            errors.append(f"{name}: news_url не соответствует стратегии Roblox.")

        if str(source["root_place_id"]) not in source["roblox_game_url"]:
            errors.append(f"{name}: root_place_id не совпадает с URL игры.")

        if str(source["roblox_group_id"]) not in source["roblox_group_url"]:
            errors.append(f"{name}: group_id не совпадает с URL группы.")

        for field in (
            "roblox_game_url",
            "roblox_group_url",
            "website",
            "news_url",
            "discord",
            "youtube",
            "x",
            "youtube_feed_url",
        ):
            validate_url(source.get(field), field, name, errors)

    return errors


def validate_content_files(canonical_names):
    errors = []

    for path in CONTENT_FILES:
        if not path.exists():
            continue

        for name in sorted(set(walk_game_names(load_json(path)))):
            if name not in canonical_names:
                errors.append(
                    f"{path}: неизвестное или иначе написанное название «{name}»."
                )

    tips = load_json(Path("tips.json"))
    games_with_tips = set(walk_game_names(tips))
    missing_tips = sorted(canonical_names - games_with_tips)

    if missing_tips:
        errors.append(
            "В tips.json нет советов для игр: " + ", ".join(missing_tips) + "."
        )

    errors.extend(validate_tip_catalog(tips, canonical_names, minimum_per_game=15))

    return errors


def main():
    games = load_json(GAMES_FILE)
    sources = load_json(SOURCES_FILE)
    canonical_names = {game["name"] for game in games}

    errors = validate_registry(games, sources)
    errors.extend(validate_content_files(canonical_names))

    if errors:
        print("Реестр источников содержит ошибки:")

        for error in errors:
            print(f"- {error}")

        raise SystemExit(1)

    external_count = sum(
        source["news_strategy"] == "official_news_website"
        or source["news_strategy"] == "official_youtube_feed"
        for source in sources.values()
    )

    print(
        "Источники проверены: "
        f"{len(games)} игр, {external_count} официальных внешних лент, "
        f"{len(games) - external_count} Roblox-источников."
    )


if __name__ == "__main__":
    main()
