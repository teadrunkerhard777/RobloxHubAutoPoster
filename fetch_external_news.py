import json
from urllib.parse import urljoin, urlparse

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


def extract_page_data(
    html,
    base_url
):
    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    # Убираем технический мусор.
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

    base_domain = urlparse(
        base_url
    ).netloc

    links = []
    seen_urls = set()

    for anchor in soup.find_all(
        "a",
        href=True
    ):
        href = anchor.get(
            "href",
            ""
        ).strip()

        if not href:
            continue

        absolute_url = urljoin(
            base_url,
            href
        )

        parsed = urlparse(
            absolute_url
        )

        # Берём только ссылки внутри
        # официального сайта.
        if parsed.netloc != base_domain:
            continue

        label = anchor.get_text(
            " ",
            strip=True
        )

        if not label:
            continue

        if absolute_url in seen_urls:
            continue

        seen_urls.add(
            absolute_url
        )

        links.append(
            {
                "text": label,
                "url": absolute_url
            }
        )

    return {
        "text": text[:20000],
        "links": links[:200]
    }


def collect_source(
    game,
    url
):
    try:
        html = fetch_page(
            url
        )

        page_data = extract_page_data(
            html,
            url
        )

        return {
            "game": game,
            "source_type": (
                "official_news_website"
            ),
            "url": url,
            "success": True,
            "text": page_data[
                "text"
            ],
            "links": page_data[
                "links"
            ],
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
            "links": [],
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

        print(
            "Внутренних ссылок:",
            len(
                result["links"]
            )
        )

        print(
            "Первые ссылки:"
        )

        for link in result[
            "links"
        ][:10]:
            print(
                " •",
                link["text"],
                "→",
                link["url"]
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
