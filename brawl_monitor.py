from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import requests


# ---------------------------------------------------------
# НАСТРОЙКА ЦВЕТНОГО ВЫВОДА
# ---------------------------------------------------------

# autoreset=True автоматически возвращает обычный цвет
# после каждого print.
init(autoreset=True)


# ---------------------------------------------------------
# URL ИСТОЧНИКОВ
# ---------------------------------------------------------

# Главная страница официального блога Brawl Stars.
BLOG_URL = "https://supercell.com/en/games/brawlstars/blog/"

# Базовый адрес Supercell.
# Ссылки внутри HTML часто приходят в сокращённом виде:
# /en/games/brawlstars/blog/...
#
# Поэтому позже будем добавлять этот адрес к найденной ссылке.
BASE_URL = "https://supercell.com"


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
# ФУНКЦИИ ДЛЯ ОБРАБОТКИ БАЛАНСА
# ---------------------------------------------------------


def parse_balance_change(text):
    """
    Разделяет строку Supercell на имя бойца и описание.

    Например:

    CROW - Main attack damage reduced from 420 ➡️ 380

    превращается в:

    {
        "brawler": "CROW",
        "change": "Main attack damage reduced from 420 ➡️ 380"
    }
    """

    # Делим только по первому разделителю.
    # Внутри описания тоже могут встречаться " - ".
    parts = text.split(" - ", 1)

    # Если Supercell неожиданно изменит формат,
    # скрипт не упадёт, а сохранит исходный текст.
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

    Например:

    Hypercharge range reduced from 20 ➡️ 16
    - Projectile damage reduced from 1000 ➡️ 800

    превращается в список из двух элементов.
    """

    parts = change_text.split(" - ")

    # Убираем лишние пробелы и пустые строки.
    return [part.strip() for part in parts if part.strip()]


# ---------------------------------------------------------
# 1. ЗАГРУЖАЕМ ГЛАВНУЮ СТРАНИЦУ БЛОГА
# ---------------------------------------------------------

print_section("BRAWL STARS BLOG")

response = requests.get(BLOG_URL, timeout=15)

if response.status_code == 200:
    print_success(f"✓ Блог загружен, статус {response.status_code}")
else:
    print_error(f"✗ Ошибка загрузки блога: {response.status_code}")

    # Если сам блог недоступен, продолжать работу нет смысла.
    raise SystemExit


# Supercell использует UTF-8.
# Декодируем байты вручную для корректных эмодзи
# и специальных символов.
blog_html = response.content.decode("utf-8")

# BeautifulSoup превращает HTML
# в удобную для поиска структуру.
soup = BeautifulSoup(blog_html, "html.parser")

# Находим все ссылки на странице.
links = soup.find_all("a")

print(f"Всего ссылок на странице: {len(links)}")


# ---------------------------------------------------------
# 2. ИЩЕМ СТАТЬИ И АКТУАЛЬНЫЕ RELEASE NOTES
# ---------------------------------------------------------

print_section("ПОСЛЕДНИЕ СТАТЬИ")

# set используем для защиты от повторяющихся ссылок.
seen_links = set()

article_number = 1

# Здесь сохраним первую найденную статью Release Notes.
# Блог Supercell выводит свежие статьи выше старых,
# поэтому первая такая ссылка считается актуальной.
latest_release_url = None
latest_release_title = None


for link in links:
    href = link.get("href")

    # Если у тега <a> нет адреса, пропускаем.
    if not href:
        continue

    # Берём только ссылки из блога Brawl Stars.
    if "/games/brawlstars/blog/" not in href:
        continue

    # Убираем страницы пагинации:
    # page/1, page/2 и т.д.
    if "/blog/page/" in href:
        continue

    # Не обрабатываем одну статью несколько раз.
    if href in seen_links:
        continue

    seen_links.add(href)

    # Получаем заголовок статьи.
    title = link.get_text(strip=True)

    # -----------------------------------------------------
    # ИЩЕМ АКТУАЛЬНЫЕ RELEASE NOTES
    # -----------------------------------------------------

    # Если встретили статью категории release-notes
    # и раньше такую ещё не находили,
    # сохраняем её как самую свежую.
    if (
        "/blog/release-notes/" in href
        and latest_release_url is None
    ):
        latest_release_url = BASE_URL + href
        latest_release_title = title

    # -----------------------------------------------------
    # КРАСИВО ВЫВОДИМ СТАТЬЮ
    # -----------------------------------------------------

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
# 3. ПРОВЕРЯЕМ НАЙДЕННЫЕ RELEASE NOTES
# ---------------------------------------------------------

print_section("АКТУАЛЬНЫЕ RELEASE NOTES")

if latest_release_url:
    print_success(
        f"✓ Найдены Release Notes: {latest_release_title}"
    )

    print(Fore.BLUE + latest_release_url)

else:
    print_error("✗ В блоге не удалось найти Release Notes")

    # Без Release Notes баланс парсить неоткуда.
    raise SystemExit


# ---------------------------------------------------------
# 4. ЗАГРУЖАЕМ НАЙДЕННЫЕ RELEASE NOTES
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


# Декодируем страницу вручную как UTF-8.
release_html = release_response.content.decode("utf-8")

# Разбираем HTML Release Notes.
release_soup = BeautifulSoup(
    release_html,
    "html.parser",
)


# ---------------------------------------------------------
# 5. ПОКАЗЫВАЕМ СТРУКТУРУ RELEASE NOTES
# ---------------------------------------------------------

print_section("РАЗДЕЛЫ RELEASE NOTES")

# Пока оставляем этот вывод для обучения и отладки.
# Когда монитор будет готов, можно будет
# убрать его или включать через debug-режим.
headings = release_soup.find_all(
    ["h1", "h2", "h3"]
)

for heading in headings:
    heading_text = heading.get_text(strip=True)

    # h1 и h2 делаем заметнее.
    if heading.name in ["h1", "h2"]:
        print(
            Fore.MAGENTA
            + Style.BRIGHT
            + heading_text
        )

    # h3 выводим как подзаголовки.
    else:
        print(
            Fore.CYAN
            + f"• {heading_text}"
        )


# ---------------------------------------------------------
# 6. ИЩЕМ ПЕРВЫЙ РАЗДЕЛ BALANCE CHANGES
# ---------------------------------------------------------

balance_heading = None

for heading in release_soup.find_all("h3"):
    heading_text = heading.get_text(strip=True)

    # Пока берём первый найденный Balance Changes.
    #
    # На текущей странице именно первый блок содержит
    # наиболее свежие изменения, добавленные позже
    # первоначальной публикации Release Notes.
    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# ---------------------------------------------------------
# 7. СОБИРАЕМ BUFFS И NERFS
# ---------------------------------------------------------

print_section("BALANCE CHANGES")

# Здесь сначала храним сырые строки с сайта.
buffs = []
nerfs = []

# Запоминаем, какой подраздел сейчас читаем:
#
# None
# "buffs"
# "nerfs"
current_section = None


if balance_heading:

    # Идём по HTML-элементам после Balance Changes.
    for element in balance_heading.find_all_next():

        # Следующий h3 означает,
        # что текущий Balance Changes закончился.
        if element.name == "h3":
            break

        # Пока работаем только с текстовыми абзацами.
        if element.name != "p":
            continue

        text = element.get_text(
            " ",
            strip=True,
        )

        # Пустые строки не нужны.
        if not text:
            continue

        # После баланса Supercell иногда сразу начинает
        # перечислять исправления приложения,
        # не создавая для них отдельный h3.
        #
        # Эта фраза означает конец интересующего
        # нас блока Balance Changes.
        if text.startswith(
            "AND we're rolling out"
        ):
            break

        # Начался раздел BUFFS.
        if "BUFFS" in text.upper():
            current_section = "buffs"
            continue

        # Начался раздел NERFS.
        if "NERFS" in text.upper():
            current_section = "nerfs"
            continue

        # Добавляем строку в нужную категорию.
        if current_section == "buffs":
            buffs.append(text)

        elif current_section == "nerfs":
            nerfs.append(text)

else:
    print_warning(
        "⚠ Раздел Balance Changes не найден"
    )


# ---------------------------------------------------------
# 8. ПРЕВРАЩАЕМ СТРОКИ В СТРУКТУРИРОВАННЫЕ ДАННЫЕ
# ---------------------------------------------------------

# Отделяем имя бойца от описания изменения.
parsed_buffs = [
    parse_balance_change(buff)
    for buff in buffs
]

parsed_nerfs = [
    parse_balance_change(nerf)
    for nerf in nerfs
]


# Теперь разбиваем длинное описание
# на отдельные изменения.
#
# Получаем структуру примерно такого вида:
#
# {
#     "brawler": "SURGE",
#     "change": "...",
#     "changes": [
#         "...",
#         "...",
#         "..."
#     ]
# }
for buff in parsed_buffs:
    buff["changes"] = split_changes(
        buff["change"]
    )

for nerf in parsed_nerfs:
    nerf["changes"] = split_changes(
        nerf["change"]
    )


# ---------------------------------------------------------
# 9. ВЫВОДИМ BUFFS
# ---------------------------------------------------------

print()

print(
    Fore.GREEN
    + Style.BRIGHT
    + f"📈 BUFFS: {len(parsed_buffs)}"
)

for buff in parsed_buffs:

    # Имя бойца выделяем отдельно.
    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"\n  + {buff['brawler']}"
    )

    # Каждое изменение показываем отдельной строкой.
    for change in buff["changes"]:
        print(
            Fore.WHITE
            + f"      • {change}"
        )


# ---------------------------------------------------------
# 10. ВЫВОДИМ NERFS
# ---------------------------------------------------------

print()

print(
    Fore.RED
    + Style.BRIGHT
    + f"📉 NERFS: {len(parsed_nerfs)}"
)

for nerf in parsed_nerfs:

    # Имя бойца выделяем красным.
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n  - {nerf['brawler']}"
    )

    # Каждое изменение показываем
    # отдельным пунктом.
    for change in nerf["changes"]:
        print(
            Fore.WHITE
            + f"      • {change}"
        )


# ---------------------------------------------------------
# 11. ИТОГОВЫЙ СТАТУС
# ---------------------------------------------------------

print_section("STATUS")

print_success(
    f"✓ Статус блога: {response.status_code}"
)

print_success(
    f"✓ Статус Release Notes: "
    f"{release_response.status_code}"
)

print(
    f"Release Notes: {latest_release_title}"
)

print(
    f"Найдено статей: {len(seen_links)}"
)

print(
    f"Найдено баффов: {len(parsed_buffs)}"
)

print(
    f"Найдено нерфов: {len(parsed_nerfs)}"
)
