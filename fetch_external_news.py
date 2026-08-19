import json
import requests
from bs4 import BeautifulSoup


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


def fetch_page(url):
    response = requests.get(
        url,
        timeout=20,
        headers={
            "User-Agent": (
                "Mozilla/5.0 "
                "RobloxHubRU/1.0"
            )
        }
    )

    response.raise_for_status()

    return response.text


def extract_page_text(html):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for element in soup(
        [
            "script",
            "style",
            "noscript"
        ]
    ):
        element.decompose()

    text = soup.get_text(
        "\n",
        strip=True
    )

    return text


def collect_source(
    game,
    url
):
    try:
        html = fetch_page(
            url
        )

        text = extract_page_text(
            html
        )

        return {
            "game": game,
            "source_type": (
                "official_news_website"
            ),
            "url": url,
            "success": True,
            "text": text[:20000],
            "error": None
        }

    except requests.RequestException as error:
        return {
            "game": game,
            "source_type": (
                "official_news_website"
            ),
            "url": url,
            "success": False,
            "text": "",
            "error": str(error)
        }


source_registry = load_json(
    "official_sources.json",
    {}
)


results = []


for game, config in source_registry.items():
    news_url = config.get(
        "news_url"
    )

    if not news_url:
        continue

    result = collect_source(
        game,
        news_url
    )

    results.append(
        result
    )

    print()
    print(
        game
    )

    print(
        "Источник:",
        news_url
    )

    print(
        "Успех:",
        result["success"]
    )

    if result["success"]:
        print(
            "Символов:",
            len(
                result["text"]
            )
        )

    else:
        print(
            "Ошибка:",
            result["error"]
        )


save_json(
    "external_news_raw.json",
    results
)


print()
print(
    "Сохранено:",
    "external_news_raw.json"
)
