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

# Базовый адрес Supercell.
BASE_URL = "https://supercell.com"

# Файл, в котором монитор будет хранить уже увиденные изменения.
STATE_FILE = "data/brawl_monitor_state.json"

# Файл только с новыми изменениями текущего запуска.
# Его позже будет читать генератор Telegram-поста.
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
# ФУНКЦИИ ДЛЯ БАЛАНСА
# ---------------------------------------------------------


def parse_balance_change(text):
    """
    Разделяет строку на имя бойца и описание изменения.

    Например:

    CROW - Main attack damage reduced from 420 ➡️ 380

    превращается в:

    {
        "brawler": "CROW",
        "change": "Main attack damage reduced from 420 ➡️ 380"
    }
    """

    parts = text.split(" - ", 1)

    # Если формат неожиданно изменился,
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
    Разбивает несколько изменений одного бойца
    на отдельные пункты.
    """

    parts = change_text.split(" - ")

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


# ---------------------------------------------------------
# ФУНКЦИИ ДЛЯ СОСТОЯНИЯ МОНИТОРА
# ---------------------------------------------------------


def load_state():
    """
    Загружает прошлое состояние монитора из JSON.

    Если файл ещё не существует,
    возвращаем пустое состояние.
    """

    if not os.path.exists(STATE_FILE):
        return {
            "release_url": None,
            "buffs": [],
            "nerfs": [],
        }

    with open(
        STATE_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def save_state(release_url, buffs, nerfs):
    """
    Сохраняет полное текущее состояние монитора.

    Этот файл нужен для следующего запуска,
    чтобы понимать, какие изменения мы уже видели.
    """

    # Формируем данные, которые будем хранить между запусками.
    state = {
        "release_url": release_url,
        "buffs": buffs,
        "nerfs": nerfs,
    }

    # Создаём папку data, если её ещё нет.
    os.makedirs(
        os.path.dirname(STATE_FILE),
        exist_ok=True,
    )

    # Сохраняем состояние в JSON.
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
):
    """
    Сохраняет только новые изменения текущего запуска.

    Этот файл позже будет читать генератор
    утреннего Brawl Stars-поста.
    """

    # Здесь уже используется отдельная переменная data,
    # потому что это другой JSON-файл с другой задачей.
    data = {
        "release_title": release_title,
        "release_url": release_url,
        "new_buffs": new_buffs,
        "new_nerfs": new_nerfs,
    }

    # Создаём папку data, если её ещё нет.
    os.makedirs(
        os.path.dirname(LATEST_CHANGES_FILE),
        exist_ok=True,
    )

    # Сохраняем только свежие изменения.
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
    Создаёт уникальную строку для изменения.

    Она нужна, чтобы сравнивать старые и новые данные.

    Например:

    CROW|Main attack damage reduced from 420 ➡️ 380
    """

    return (
        item["brawler"]
        + "|"
        + item["change"]
    )


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
# 2. ИЩЕМ СТАТЬИ И RELEASE NOTES
# ---------------------------------------------------------

print_section("ПОСЛЕДНИЕ СТАТЬИ")

seen_links = set()

article_number = 1

latest_release_url = None
latest_release_title = None


for link in links:
    href = link.get("href")

    if not href:
        continue

    if "/games/brawlstars/blog/" not in href:
        continue

    if "/blog/page/" in href:
        continue

    if href in seen_links:
        continue

    seen_links.add(href)

    title = link.get_text(strip=True)

    # Первая найденная статья release-notes
    # считается самой свежей.
    if (
        "/blog/release-notes/" in href
        and latest_release_url is None
    ):
        latest_release_url = BASE_URL + href
        latest_release_title = title

    print(
        Fore.YELLOW
        + Style.BRIGHT
        + f"{article_number}. "
        + Fore.WHITE
        + Style.BRIGHT
        + title
    )

    print(Fore.BLUE + href)
    print()

    article_number += 1


# ---------------------------------------------------------
# 3. ПРОВЕРЯЕМ RELEASE NOTES
# ---------------------------------------------------------

print_section("АКТУАЛЬНЫЕ RELEASE NOTES")

if latest_release_url:
    print_success(
        f"✓ Найдены Release Notes: {latest_release_title}"
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
# 4. ЗАГРУЖАЕМ RELEASE NOTES
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
# 5. ИЩЕМ BALANCE CHANGES
# ---------------------------------------------------------

balance_heading = None

for heading in release_soup.find_all("h3"):
    heading_text = heading.get_text(strip=True)

    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# ---------------------------------------------------------
# 6. СОБИРАЕМ BUFFS И NERFS
# ---------------------------------------------------------

buffs = []
nerfs = []

current_section = None


if balance_heading:

    for element in balance_heading.find_all_next():

        # Следующий h3 означает конец блока.
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

        # После этой строки начинаются bug fixes,
        # которые к балансу уже не относятся.
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
# 7. СТРУКТУРИРУЕМ ДАННЫЕ
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
# 8. ЗАГРУЖАЕМ ПРОШЛОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

print_section("СРАВНЕНИЕ С ПРОШЛЫМ ЗАПУСКОМ")

old_state = load_state()

# Превращаем прошлые изменения в set,
# чтобы быстро проверять наличие каждого элемента.
old_buff_keys = {
    make_change_key(item)
    for item in old_state["buffs"]
}

old_nerf_keys = {
    make_change_key(item)
    for item in old_state["nerfs"]
}


# ---------------------------------------------------------
# 9. ИЩЕМ ТОЛЬКО НОВЫЕ ИЗМЕНЕНИЯ
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


# ---------------------------------------------------------
# 10. ПОКАЗЫВАЕМ РЕЗУЛЬТАТ СРАВНЕНИЯ
# ---------------------------------------------------------

# Если состояние пустое, это первый запуск монитора.
first_run = (
    old_state["release_url"] is None
)


if first_run:

    print_warning(
        "Первый запуск монитора."
    )

    print_warning(
        "Текущие изменения будут сохранены "
        "как базовое состояние."
    )

else:

    if not new_buffs and not new_nerfs:
        print_success(
            "✓ Новых изменений баланса нет"
        )

    else:

        print_success(
            "✓ Найдены новые изменения!"
        )


# ---------------------------------------------------------
# 11. НОВЫЕ BUFFS
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
# 12. НОВЫЕ NERFS
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
# 13. СОХРАНЯЕМ ТОЛЬКО НОВЫЕ ИЗМЕНЕНИЯ
# ---------------------------------------------------------

save_latest_changes(
    latest_release_title,
    latest_release_url,
    new_buffs,
    new_nerfs,
)

print_success(
    f"\n✓ Свежие изменения сохранены в {LATEST_CHANGES_FILE}"
)

# ---------------------------------------------------------
# 14. СОХРАНЯЕМ НОВОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

save_state(
    latest_release_url,
    parsed_buffs,
    parsed_nerfs,
)

print_success(
    "\n✓ Состояние монитора сохранено"
)


# ---------------------------------------------------------
# 14. ИТОГ
# ---------------------------------------------------------

print_section("STATUS")

print(
    f"Release Notes: {latest_release_title}"
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
