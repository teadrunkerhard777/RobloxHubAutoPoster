import json
import re
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup


def load_json(filename, default):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError:
        return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def fetch_page(url):
    response = requests.get(
        url, timeout=20, headers={"User-Agent": ("Mozilla/5.0 " "RobloxHubRU/1.0")}
    )

    response.raise_for_status()

    return response.text


def extract_page_data(html, base_url):
    soup = BeautifulSoup(html, "html.parser")

    # Убираем технический мусор.
    for element in soup(["script", "style", "noscript"]):
        element.decompose()

    title = ""

    title_meta = soup.find("meta", attrs={"property": "og:title"})

    if title_meta:
        title = title_meta.get("content", "").strip()

    if not title:
        heading = soup.find("h1")

        if heading:
            title = heading.get_text(" ", strip=True)

    published_at = None

    published_meta = soup.find("meta", attrs={"property": ("article:published_time")})

    if published_meta:
        published_at = published_meta.get("content")

    if not published_at:
        time_element = soup.find("time", attrs={"datetime": True})

        if time_element:
            published_at = time_element.get("datetime")

    text = soup.get_text("\n", strip=True)

    base_domain = urlparse(base_url).netloc

    links = []
    seen_urls = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "").strip()

        if not href:
            continue

        absolute_url = urljoin(base_url, href)

        parsed = urlparse(absolute_url)

        # Берём только ссылки внутри
        # официального сайта.
        if parsed.netloc != base_domain:
            continue

        label = anchor.get_text(" ", strip=True)

        if not label:
            continue

        if absolute_url in seen_urls:
            continue

        seen_urls.add(absolute_url)

        links.append({"text": label, "url": absolute_url})

    return {
        "title": title,
        "published_at": published_at,
        "text": text[:20000],
        "links": links[:200],
    }


def collect_source(game, url):
    try:
        html = fetch_page(url)

        page_data = extract_page_data(html, url)

        return {
            "game": game,
            "source_type": ("official_news_website"),
            "url": url,
            "success": True,
            "title": page_data["title"],
            "published_at": page_data["published_at"],
            "text": page_data["text"],
            "links": page_data["links"],
            "error": None,
        }

    except requests.RequestException as error:
        return {
            "game": game,
            "source_type": ("official_news_website"),
            "url": url,
            "success": False,
            "title": "",
            "published_at": None,
            "text": "",
            "links": [],
            "error": str(error),
        }


def find_latest_article_url(game, news_url, links):
    news_path = urlparse(news_url).path.rstrip("/")

    for link in links:
        article_url = link.get("url", "")

        parsed = urlparse(article_url)

        article_path = parsed.path.rstrip("/")

        if not article_path:
            continue

        if article_path == news_path:
            continue

        if game == "Blox Fruits":
            if article_path.startswith("/blogs/news/"):
                return article_url

        elif game == "Adopt Me!":
            if article_path.startswith("/news/"):
                return article_url

        elif game == "Brookhaven":
            if article_path.startswith("/posts/brookhaven-update-"):
                return article_url

        elif game == "Pet Simulator 99":
            if article_path.startswith("/post/pet-simulator-99-"):
                return article_url

        elif game == "Blade Ball" and article_path.startswith("/blogs/news/"):
            return article_url

    return None


def fetch_article(url):
    try:
        html = fetch_page(url)

        page_data = extract_page_data(html, url)

        return {
            "url": url,
            "success": True,
            "title": page_data["title"],
            "published_at": page_data["published_at"],
            "text": page_data["text"],
            "error": None,
        }

    except requests.RequestException as error:
        return {
            "url": url,
            "success": False,
            "title": "",
            "published_at": None,
            "text": "",
            "error": str(error),
        }


def infer_published_at_from_links(article_url, links):
    for link in links:
        if link.get("url") != article_url:
            continue

        searchable = " ".join((link.get("text", ""), article_url.replace("-", " ")))

        patterns = (
            (r"\b(\d{1,2}\s+[A-Za-z]+\s+\d{4})\b", "%d %B %Y"),
            (r"\b([A-Za-z]+\s+\d{1,2},?\s+\d{4})\b", "%B %d %Y"),
        )

        for pattern, date_format in patterns:
            match = re.search(pattern, searchable)

            if not match:
                continue

            normalized = match.group(1).replace(",", "")

            try:
                published_at = datetime.strptime(
                    normalized,
                    date_format,
                ).replace(tzinfo=timezone.utc)
            except ValueError:
                continue

            return published_at.date().isoformat()

    return None


def collect_youtube_feed(game, config):
    feed_url = config.get("youtube_feed_url")

    try:
        xml_text = fetch_page(feed_url)
        root = ElementTree.fromstring(xml_text)
    except (requests.RequestException, ElementTree.ParseError) as error:
        return {
            "game": game,
            "source_type": "official_youtube_feed",
            "url": feed_url,
            "success": False,
            "title": "",
            "published_at": None,
            "text": "",
            "links": [],
            "latest_article": None,
            "error": str(error),
        }

    namespaces = {
        "atom": "http://www.w3.org/2005/Atom",
        "media": "http://search.yahoo.com/mrss/",
        "yt": "http://www.youtube.com/xml/schemas/2015",
    }
    game_terms = [term.lower() for term in config.get("youtube_match_terms", [])]
    feed_title = root.findtext("atom:title", "", namespaces).strip()
    feed_author = root.findtext("atom:author/atom:name", "", namespaces).strip()
    expected_channel = config.get("youtube_channel_name", "").strip()

    if expected_channel and expected_channel.casefold() not in {
        feed_title.casefold(),
        feed_author.casefold(),
    }:
        return {
            "game": game,
            "source_type": "official_youtube_feed",
            "url": feed_url,
            "success": False,
            "title": feed_title,
            "published_at": None,
            "text": "",
            "links": [],
            "latest_article": None,
            "error": (
                f"RSS принадлежит каналу «{feed_title or feed_author}», "
                f"ожидался «{expected_channel}»."
            ),
        }

    news_terms = ("update", "event", "trailer", "collab", "release", "launch", "new ")
    entries = []

    for entry in root.findall("atom:entry", namespaces):
        title = entry.findtext("atom:title", "", namespaces).strip()
        published_at = entry.findtext("atom:published", "", namespaces).strip()
        video_id = entry.findtext("yt:videoId", "", namespaces).strip()
        description = entry.findtext(
            "media:group/media:description", "", namespaces
        ).strip()
        combined = f"{title}\n{description}".lower()

        if game_terms and not any(term in combined for term in game_terms):
            continue

        if not any(term in combined for term in news_terms):
            continue

        if not title or not published_at or not description or not video_id:
            continue

        entries.append(
            {
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "success": True,
                "title": title,
                "published_at": published_at,
                "text": f"{title}\n{description}"[:20000],
                "error": None,
            }
        )

    entries.sort(key=lambda item: item["published_at"], reverse=True)
    latest_article = entries[0] if entries else None

    return {
        "game": game,
        "source_type": "official_youtube_feed",
        "url": feed_url,
        "success": True,
        "title": latest_article.get("title", "") if latest_article else "",
        "channel_name": feed_title or feed_author,
        "published_at": (
            latest_article.get("published_at") if latest_article else None
        ),
        "text": latest_article.get("text", "") if latest_article else "",
        "links": [],
        "latest_article": latest_article,
        "error": (
            None
            if latest_article
            else (
                "В официальной ленте нет записи с датой, содержанием "
                "и признаками новости этой игры."
            )
        ),
    }


def collect_external_news(source_registry):
    results = []

    for game, config in source_registry.items():
        youtube_feed_url = config.get("youtube_feed_url")

        if youtube_feed_url:
            results.append(collect_youtube_feed(game, config))

        news_url = config.get("news_url")

        if not news_url:
            continue

        result = collect_source(game, news_url)

        article_url = None

        if result["success"]:
            article_url = find_latest_article_url(game, news_url, result["links"])

        if article_url:
            article = fetch_article(article_url)

            if article["success"] and not article["published_at"]:
                article["published_at"] = infer_published_at_from_links(
                    article_url, result["links"]
                )

            result["latest_article"] = article
        else:
            result["latest_article"] = None

        results.append(result)

    return results


def print_result(result):
    print()
    print(result["game"])

    print("Источник:", result["url"])

    print("Успех:", result["success"])

    if result["success"]:
        print("Символов:", len(result["text"]))

        print("Внутренних ссылок:", len(result["links"]))

        print("Первые ссылки:")

        for link in result["links"][:10]:
            print(" •", link["text"], "→", link["url"])

        article = result.get("latest_article")

        if article:
            print("Последняя статья:", article["url"])

            print("Статья загружена:", article["success"])

            if article["success"]:
                print("Заголовок:", article["title"])

                print("Дата:", article["published_at"])

                print("Символов в статье:", len(article["text"]))

            else:
                print("Ошибка статьи:", article["error"])

        else:
            print("Последняя статья не найдена.")

    else:
        print("Ошибка:", result["error"])


def main():
    source_registry = load_json("official_sources.json", {})

    results = collect_external_news(source_registry)

    for result in results:
        print_result(result)

    save_json("external_news_raw.json", results)

    print()
    print("Сохранено:", "external_news_raw.json")


if __name__ == "__main__":
    main()
