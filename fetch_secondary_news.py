"""Ищет дополнительные новости Roblox в крупных игровых изданиях."""

import html
import json
import re
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from xml.etree import ElementTree

import requests

from external_news_facts import (
    contains_rumor_signal,
    has_game_news_meaning,
    is_news_event,
)

OUTPUT_FILE = "secondary_news_raw.json"
REQUEST_TIMEOUT = 20

# Tier B используется только для discovery и атрибутированных публикаций.
# Community, Wiki, Reddit и фанатские сайты сюда намеренно не входят.
TIER_B_PUBLISHERS = {
    "beebom",
    "destructoid",
    "dexerto",
    "eurogamer",
    "pcgamesn",
    "pocket tactics",
    "sportskeeda",
    "the gamer",
    "thegamer",
}


def load_games(filename="games.json"):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def clean_html(value):
    text = re.sub(r"<[^>]+>", " ", html.unescape(value or ""))
    return " ".join(text.split())


def normalize_rss_date(value):
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def publisher_is_allowed(publisher):
    normalized = (publisher or "").strip().casefold()
    return normalized in TIER_B_PUBLISHERS


def game_is_explicit(game, title, description):
    haystack = f"{title} {description}".casefold()
    normalized_game = game.casefold().replace("!", "")
    return normalized_game in haystack.replace("!", "")


def is_secondary_news_article(article):
    # fresh article + game relevance != news; Tier B обязан содержать
    # конкретное новое событие или изменение самой игры.
    return is_news_event(article)


def parse_feed(game, feed_text):
    root = ElementTree.fromstring(feed_text)
    candidates = []

    for item in root.findall("./channel/item"):
        raw_title = item.findtext("title") or ""
        publisher = item.findtext("source") or ""
        description = clean_html(item.findtext("description"))
        published_at = normalize_rss_date(item.findtext("pubDate"))
        url = item.findtext("link") or ""
        title = re.sub(
            rf"\s+-\s+{re.escape(publisher)}\s*$",
            "",
            raw_title,
            flags=re.IGNORECASE,
        ).strip()
        article = {
            "success": True,
            "url": url,
            "title": title,
            "published_at": published_at,
            "text": f"{title}. {description}".strip(),
            "source_tier": "B",
            "publisher": publisher,
        }

        if not publisher_is_allowed(publisher):
            continue
        if (
            not url
            or not published_at
            or not game_is_explicit(game, title, description)
        ):
            continue
        if (
            contains_rumor_signal(article)
            or not has_game_news_meaning(article)
            or not is_secondary_news_article(article)
        ):
            continue

        candidates.append(article)

    candidates.sort(key=lambda article: article["published_at"], reverse=True)
    return candidates


def build_feed_url(game):
    query = quote(f'"{game}" Roblox when:30d')
    return "https://news.google.com/rss/search?" f"q={query}&hl=en-US&gl=US&ceid=US:en"


def fetch_secondary_news(games=None, requester=None):
    if games is None:
        games = load_games()
    if requester is None:
        requester = requests.get

    results = []

    for game_config in games:
        game = game_config["name"]
        feed_url = build_feed_url(game)

        try:
            response = requester(
                feed_url,
                timeout=REQUEST_TIMEOUT,
                headers={"User-Agent": "RobloxHubAutoPoster/1.0"},
            )
            response.raise_for_status()
            candidates = parse_feed(game, response.text)
            results.append(
                {
                    "game": game,
                    "source_type": "secondary_gaming_media",
                    "source_tier": "B",
                    "url": feed_url,
                    "success": True,
                    "publisher": (
                        candidates[0].get("publisher") if candidates else None
                    ),
                    "latest_article": candidates[0] if candidates else None,
                    "error": None if candidates else "Нет пригодной Tier B новости.",
                }
            )
        except (requests.RequestException, ElementTree.ParseError) as error:
            results.append(
                {
                    "game": game,
                    "source_type": "secondary_gaming_media",
                    "source_tier": "B",
                    "url": feed_url,
                    "success": False,
                    "publisher": None,
                    "latest_article": None,
                    "error": str(error),
                }
            )

    return results


def main():
    results = fetch_secondary_news()

    with open(OUTPUT_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    found = sum(bool(result.get("latest_article")) for result in results)
    unavailable = sum(result.get("success") is not True for result in results)
    print(
        f"Tier B discovery: проверено {len(results)}, "
        f"найдено {found}, недоступно {unavailable}."
    )


if __name__ == "__main__":
    main()
