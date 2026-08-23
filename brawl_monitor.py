from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import json
import os
import requests


# ---------------------------------------------------------
# НАСТРОЙКА ЦВЕТНОГО ВЫВОДА
# ---------------------------------------------------------

init(autoreset=True)


# ---------------------------------------------------------
# URL И ФАЙЛЫ
# ---------------------------------------------------------

# Главная страница официального блога Brawl Stars.
BLOG_URL = "https://supercell.com/en/games/brawlstars/blog/"

# Базовый адрес сайта.
BASE_URL = "https://supercell.com"

# Здесь хранится полное состояние монитора.
STATE_FILE = "data/brawl_monitor_state.json"

# Здесь хранятся только свежие изменения
# последнего запуска.
LATEST_CHANGES_FILE = "data/brawl_latest_changes.json"


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ ВЫВОДА
# ---------------------------------------------------------


def print_section(title):
    """Выводит крупный заголовок раздела."""
    print(Fore.CYAN + Style.BRIGHT + f"\n=== {title} ===")


def print_success(text):
    """Выводит успешный статус зелёным."""
    print(Fore.GREEN + text)


def print_warning(text):
    """Выводит предупреждение жёлтым."""
    print(Fore.YELLOW + text)


def print_error(text):
    """Выводит ошибку красным."""
    print(Fore.RED + Style.BRIGHT + text)


# ---------------------------------------------------------
# КАТЕГОРИИ СТАТЕЙ
# ---------------------------------------------------------


def get_article_category(href):
    """
    Определяет тип статьи по URL.

    Пока используем четыре категории:

    release-notes -> обновления и изменения игры
    esports       -> турниры и чемпионаты
    community     -> коллаборации и события
    other         -> всё остальное
    """

    if "/blog/release-notes/" in href:
        return "release-notes"

    if "/blog/esports/" in href:
        return "esports"

    if "/blog/community/" in href:
        return "community"

    return "other"


def get_category_icon(category):
    """
    Возвращает иконку для красивого вывода
    категории статьи в терминале.
    """

    icons = {
        "release-notes": "⚖️",
        "esports": "🏆",
        "community": "🎉",
        "other": "📰",
    }

    return icons.get(category, "📰")


# ---------------------------------------------------------
# ФУНКЦИИ ДЛЯ БАЛАНСА
# ---------------------------------------------------------


def parse_balance_change(text):
    """
    Разделяет строку Supercell
    на имя бойца и описание изменения.

    Например:

    CROW - Main attack damage reduced from 420 ➡️ 380

    превращается в:

    {
        "brawler": "CROW",
        "change": "Main attack damage reduced from 420 ➡️ 380"
    }
    """

    parts = text.split(" - ", 1)

    # Если формат неожиданно изменится,
    # не падаем с ошибкой.
    if len(parts) != 2:
        return {
            "brawler": "UNKNOWN",
            "change": text,
        }

    brawler, change = parts

    return {
        "brawler": brawler.strip(),
        "change": change.strip(),
    }


def split_changes(change_text):
    """
    Разбивает несколько изменений
    одного бойца на отдельные пункты.
    """

    parts = change_text.split(" - ")

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


# ---------------------------------------------------------
# РАБОТА С СОСТОЯНИЕМ МОНИТОРА
# ---------------------------------------------------------


def load_state():
    """
    Загружает прошлое состояние монитора.

    Если файл ещё не существует,
    возвращаем пустое состояние.
    """

    if not os.path.exists(STATE_FILE):
        return {
            "release_url": None,
            "buffs": [],
            "nerfs": [],
            "articles": [],
        }

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        state = json.load(file)

    # Эти значения добавляем через get(),
    # чтобы старый state-файл тоже продолжал работать.
    state.setdefault("release_url", None)
    state.setdefault("buffs", [])
    state.setdefault("nerfs", [])
    state.setdefault("articles", [])

    return state


def save_state(
    release_url,
    buffs,
    nerfs,
    articles,
):
    """
    Сохраняет полное текущее состояние монитора.

    Оно понадобится при следующем запуске,
    чтобы понять, что уже было обработано.
    """

    state = {
        "release_url": release_url,
        "buffs": buffs,
        "nerfs": nerfs,
        "articles": articles,
    }

    os.makedirs(
        os.path.dirname(STATE_FILE),
        exist_ok=True,
    )

    with open(
        STATE_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            state,
            file,
            ensure_ascii=False,
            indent=2,
        )


def save_latest_changes(
    release_title,
    release_url,
    new_buffs,
    new_nerfs,
    new_articles,
):
    """
    Сохраняет только свежие данные,
    найденные во время текущего запуска.

    Позже этот JSON будет использоваться
    генератором утреннего поста.
    """

    data = {
        "release_title": release_title,
        "release_url": release_url,
        "new_buffs": new_buffs,
        "new_nerfs": new_nerfs,
        "new_articles": new_articles,
    }

    os.makedirs(
        os.path.dirname(LATEST_CHANGES_FILE),
        exist_ok=True,
    )

    with open(
        LATEST_CHANGES_FILE,
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2,
        )


def make_change_key(item):
    """
    Создаёт уникальный ключ изменения баланса.

    Он нужен для сравнения старых
    и новых баффов / нерфов.
    """

    return (
        item["brawler"]
        + "|"
        + item["change"]
    )


def make_article_key(article):
    """
    Создаёт уникальный ключ статьи.

    Пока достаточно URL,
    потому что каждая статья Supercell
    имеет собственный адрес.
    """

    return article["url"]

def fetch_article_text(article_url):
    """
    Загружает страницу статьи Supercell
    и вытаскивает из неё основной текст.

    Пока собираем:
    - заголовки h1 / h2 / h3;
    - обычные абзацы p.

    Возвращаем список текстовых блоков.
    """

    response = requests.get(
        article_url,
        timeout=15,
    )

    # Если статья не загрузилась,
    # возвращаем пустой список.
    if response.status_code != 200:
        print_warning(
            f"⚠ Не удалось загрузить статью: {article_url}"
        )

        return []

    # Supercell использует UTF-8.
    html = response.content.decode("utf-8")

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    content = []

    # Собираем основные текстовые элементы статьи.
    for element in soup.find_all(
        ["h1", "h2", "h3", "p"]
    ):
        text = element.get_text(
            " ",
            strip=True,
        )

        # Пустые элементы пропускаем.
        if not text:
            continue

        # Не сохраняем технический подвал Supercell.
        if text in (
            "Follow us on",
            "Download our games from",
        ):
            break

        content.append(text)

    return content


def enrich_new_articles(articles):
    """
    Добавляет к новым статьям их текст.

    Было:

    {
        "title": "...",
        "url": "...",
        "category": "esports"
    }

    Станет:

    {
        "title": "...",
        "url": "...",
        "category": "esports",
        "content": [...]
    }
    """

    enriched_articles = []

    for article in articles:
        print(
            Fore.CYAN
            + f"Читаю статью: {article['title']}"
        )

        content = fetch_article_text(
            article["url"]
        )

        enriched_article = {
            **article,
            "content": content,
        }

        enriched_articles.append(
            enriched_article
        )

    return enriched_articles

# ---------------------------------------------------------
# 1. ЗАГРУЖАЕМ БЛОГ
# ---------------------------------------------------------

print_section("BRAWL STARS BLOG")

response = requests.get(
    BLOG_URL,
    timeout=15,
)

if response.status_code == 200:
    print_success(
        f"✓ Блог загружен, статус {response.status_code}"
    )
else:
    print_error(
        f"✗ Ошибка загрузки блога: {response.status_code}"
    )

    raise SystemExit


# Явно декодируем UTF-8,
# чтобы эмодзи отображались корректно.
blog_html = response.content.decode("utf-8")

soup = BeautifulSoup(
    blog_html,
    "html.parser",
)

links = soup.find_all("a")

print(
    f"Всего ссылок на странице: {len(links)}"
)


# ---------------------------------------------------------
# 2. СОБИРАЕМ СТАТЬИ BRAWL STARS
# ---------------------------------------------------------

print_section("ПОСЛЕДНИЕ СТАТЬИ")

seen_links = set()

articles = []

latest_release_url = None
latest_release_title = None


for link in links:
    href = link.get("href")

    if not href:
        continue

    # Оставляем только ссылки из блога Brawl Stars.
    if "/games/brawlstars/blog/" not in href:
        continue

    # Пагинация статьёй не является.
    if "/blog/page/" in href:
        continue

    # Не сохраняем одну ссылку несколько раз.
    if href in seen_links:
        continue

    seen_links.add(href)

    title = link.get_text(strip=True)

    # Иногда ссылка может быть технической
    # и не иметь нормального заголовка.
    if not title:
        continue

    category = get_article_category(href)

    full_url = BASE_URL + href

    article = {
        "title": title,
        "url": full_url,
        "category": category,
    }

    articles.append(article)

    # Первая найденная статья release-notes
    # считается актуальной.
    if (
        category == "release-notes"
        and latest_release_url is None
    ):
        latest_release_url = full_url
        latest_release_title = title


# ---------------------------------------------------------
# 3. КРАСИВО ПОКАЗЫВАЕМ СТАТЬИ
# ---------------------------------------------------------

for article in articles:
    icon = get_category_icon(
        article["category"]
    )

    print(
        Fore.YELLOW
        + Style.BRIGHT
        + f"{icon} {article['category'].upper()}"
    )

    print(
        Fore.WHITE
        + Style.BRIGHT
        + article["title"]
    )

    print(
        Fore.BLUE
        + article["url"]
    )

    print()


# ---------------------------------------------------------
# 4. ПРОВЕРЯЕМ RELEASE NOTES
# ---------------------------------------------------------

print_section("АКТУАЛЬНЫЕ RELEASE NOTES")

if latest_release_url:
    print_success(
        f"✓ Найдены Release Notes: "
        f"{latest_release_title}"
    )

    print(
        Fore.BLUE
        + latest_release_url
    )

else:
    print_error(
        "✗ Release Notes не найдены"
    )

    raise SystemExit


# ---------------------------------------------------------
# 5. ЗАГРУЖАЕМ RELEASE NOTES
# ---------------------------------------------------------

release_response = requests.get(
    latest_release_url,
    timeout=15,
)

if release_response.status_code == 200:
    print_success(
        f"✓ Release Notes загружены, "
        f"статус {release_response.status_code}"
    )
else:
    print_error(
        f"✗ Ошибка загрузки Release Notes: "
        f"{release_response.status_code}"
    )

    raise SystemExit


release_html = release_response.content.decode(
    "utf-8"
)

release_soup = BeautifulSoup(
    release_html,
    "html.parser",
)


# ---------------------------------------------------------
# 6. ИЩЕМ BALANCE CHANGES
# ---------------------------------------------------------

balance_heading = None

for heading in release_soup.find_all("h3"):
    heading_text = heading.get_text(strip=True)

    # Первый Balance Changes пока считаем
    # самым свежим блоком изменений.
    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# ---------------------------------------------------------
# 7. СОБИРАЕМ BUFFS И NERFS
# ---------------------------------------------------------

buffs = []
nerfs = []

current_section = None


if balance_heading:

    for element in balance_heading.find_all_next():

        # Следующий h3 означает конец
        # текущего блока Balance Changes.
        if element.name == "h3":
            break

        if element.name != "p":
            continue

        text = element.get_text(
            " ",
            strip=True,
        )

        if not text:
            continue

        # После этой строки в текущей статье
        # начинаются bug fixes.
        if text.startswith(
            "AND we're rolling out"
        ):
            break

        if "BUFFS" in text.upper():
            current_section = "buffs"
            continue

        if "NERFS" in text.upper():
            current_section = "nerfs"
            continue

        if current_section == "buffs":
            buffs.append(text)

        elif current_section == "nerfs":
            nerfs.append(text)

else:
    print_warning(
        "⚠ Balance Changes не найден"
    )


# ---------------------------------------------------------
# 8. СТРУКТУРИРУЕМ БАЛАНС
# ---------------------------------------------------------

parsed_buffs = [
    parse_balance_change(buff)
    for buff in buffs
]

parsed_nerfs = [
    parse_balance_change(nerf)
    for nerf in nerfs
]


for buff in parsed_buffs:
    buff["changes"] = split_changes(
        buff["change"]
    )

for nerf in parsed_nerfs:
    nerf["changes"] = split_changes(
        nerf["change"]
    )


# ---------------------------------------------------------
# 9. ЗАГРУЖАЕМ ПРОШЛОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

print_section("СРАВНЕНИЕ С ПРОШЛЫМ ЗАПУСКОМ")

old_state = load_state()


# ---------------------------------------------------------
# 10. ГОТОВИМ КЛЮЧИ СТАРЫХ ДАННЫХ
# ---------------------------------------------------------

old_buff_keys = {
    make_change_key(item)
    for item in old_state["buffs"]
}

old_nerf_keys = {
    make_change_key(item)
    for item in old_state["nerfs"]
}

old_article_keys = {
    make_article_key(article)
    for article in old_state["articles"]
}


# ---------------------------------------------------------
# 11. ИЩЕМ НОВЫЕ ИЗМЕНЕНИЯ
# ---------------------------------------------------------

new_buffs = [
    buff
    for buff in parsed_buffs
    if make_change_key(buff)
    not in old_buff_keys
]

new_nerfs = [
    nerf
    for nerf in parsed_nerfs
    if make_change_key(nerf)
    not in old_nerf_keys
]

new_articles = [
    article
    for article in articles
    if make_article_key(article)
    not in old_article_keys
]

# ---------------------------------------------------------
# ЗАГРУЖАЕМ СОДЕРЖИМОЕ НОВЫХ СТАТЕЙ
# ---------------------------------------------------------

# Полный текст загружаем только для новых статей.
# Старые статьи повторно открывать нет смысла.
enriched_new_articles = enrich_new_articles(
    new_articles
)


# ---------------------------------------------------------
# 12. ОПРЕДЕЛЯЕМ ПЕРВЫЙ ЗАПУСК
# ---------------------------------------------------------

first_run = (
    old_state["release_url"] is None
    and not old_state["articles"]
)


if first_run:
    print_warning(
        "Первый запуск монитора."
    )

    print_warning(
        "Текущие данные будут сохранены "
        "как базовое состояние."
    )

elif (
    not new_buffs
    and not new_nerfs
    and not new_articles
):
    print_success(
        "✓ Ничего нового не найдено"
    )

else:
    print_success(
        "✓ Найдены новые материалы"
    )


# ---------------------------------------------------------
# 13. ПОКАЗЫВАЕМ НОВЫЕ СТАТЬИ
# ---------------------------------------------------------

if enriched_new_articles:
    print_section("НОВЫЕ МАТЕРИАЛЫ")

    for article in enriched_new_articles:
        icon = get_category_icon(
            article["category"]
        )

        print(
            Fore.YELLOW
            + Style.BRIGHT
            + f"{icon} {article['category'].upper()}"
        )

        print(
            Fore.WHITE
            + Style.BRIGHT
            + article["title"]
        )

        print(
            Fore.BLUE
            + article["url"]
        )

        print()

                # Для теста показываем первые несколько
        # текстовых блоков статьи.
        preview = article["content"][:5]

        for text in preview:
            print(
                Fore.WHITE
                + f"  • {text}"
            )


# ---------------------------------------------------------
# 14. ПОКАЗЫВАЕМ НОВЫЕ BUFFS
# ---------------------------------------------------------

if new_buffs:

    print()

    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"📈 НОВЫЕ BUFFS: {len(new_buffs)}"
    )

    for buff in new_buffs:

        print(
            Fore.GREEN
            + Style.BRIGHT
            + f"\n  + {buff['brawler']}"
        )

        for change in buff["changes"]:
            print(
                Fore.WHITE
                + f"      • {change}"
            )


# ---------------------------------------------------------
# 15. ПОКАЗЫВАЕМ НОВЫЕ NERFS
# ---------------------------------------------------------

if new_nerfs:

    print()

    print(
        Fore.RED
        + Style.BRIGHT
        + f"📉 НОВЫЕ NERFS: {len(new_nerfs)}"
    )

    for nerf in new_nerfs:

        print(
            Fore.RED
            + Style.BRIGHT
            + f"\n  - {nerf['brawler']}"
        )

        for change in nerf["changes"]:
            print(
                Fore.WHITE
                + f"      • {change}"
            )


# ---------------------------------------------------------
# 16. СОХРАНЯЕМ СВЕЖИЕ ДАННЫЕ
# ---------------------------------------------------------

save_latest_changes(
    latest_release_title,
    latest_release_url,
    new_buffs,
    new_nerfs,
    enriched_new_articles,
)

print_success(
    f"\n✓ Свежие данные сохранены в "
    f"{LATEST_CHANGES_FILE}"
)


# ---------------------------------------------------------
# 17. ОБНОВЛЯЕМ ПОЛНОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

save_state(
    latest_release_url,
    parsed_buffs,
    parsed_nerfs,
    articles,
)

print_success(
    "✓ Состояние монитора обновлено"
)


# ---------------------------------------------------------
# 18. ИТОГ
# ---------------------------------------------------------

print_section("STATUS")

print(
    f"Release Notes: {latest_release_title}"
)

print(
    f"Всего статей: {len(articles)}"
)

print(
    f"Новых статей: {len(new_articles)}"
)

print(
    f"Всего баффов: {len(parsed_buffs)}"
)

print(
    f"Всего нерфов: {len(parsed_nerfs)}"
)

print(
    f"Новых баффов: {len(new_buffs)}"
)

print(
    f"Новых нерфов: {len(new_nerfs)}"
)

print(
    f"State-файл: {STATE_FILE}"
)
