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

# Пока указываем Release Notes вручную.
# Позже монитор будет находить актуальную страницу автоматически.
RELEASE_URL = (
    "https://supercell.com"
    "/en/games/brawlstars/blog/release-notes/release-notes-june-2026/"
)


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
    # Внутри самого описания тоже могут встречаться " - ".
    parts = text.split(" - ", 1)

    # На случай неожиданного формата страницы
    # не падаем с ошибкой, а сохраняем исходный текст.
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

    превращается в список из двух изменений.
    """

    # На странице Supercell отдельные изменения
    # обычно разделяются строкой " - ".
    parts = change_text.split(" - ")

    # Убираем пробелы и возможные пустые элементы.
    return [part.strip() for part in parts if part.strip()]


# ---------------------------------------------------------
# 1. ПОЛУЧАЕМ ГЛАВНУЮ СТРАНИЦУ БЛОГА
# ---------------------------------------------------------

print_section("BRAWL STARS BLOG")

response = requests.get(BLOG_URL, timeout=15)

if response.status_code == 200:
    print_success(f"✓ Блог загружен, статус {response.status_code}")
else:
    print_error(f"✗ Ошибка загрузки блога: {response.status_code}")


# Supercell использует UTF-8.
# Декодируем байты вручную, чтобы эмодзи и стрелки
# отображались корректно.
blog_html = response.content.decode("utf-8")

# Превращаем HTML в структуру BeautifulSoup.
soup = BeautifulSoup(blog_html, "html.parser")

# Получаем все ссылки страницы.
links = soup.find_all("a")

print(f"Всего ссылок на странице: {len(links)}")


# ---------------------------------------------------------
# 2. ИЩЕМ СТАТЬИ BRAWL STARS
# ---------------------------------------------------------

print_section("ПОСЛЕДНИЕ СТАТЬИ")

# set удобен тем, что не позволяет хранить дубли.
seen_links = set()

article_number = 1

for link in links:
    href = link.get("href")

    # Элемент без ссылки нам не нужен.
    if not href:
        continue

    # Оставляем только статьи блога Brawl Stars.
    if "/games/brawlstars/blog/" not in href:
        continue

    # Убираем страницы пагинации:
    # page/1, page/2 и т.д.
    if "/blog/page/" in href:
        continue

    # Повторно найденную статью не выводим.
    if href in seen_links:
        continue

    seen_links.add(href)

    # Получаем заголовок статьи.
    title = link.get_text(strip=True)

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
# 3. ОТКРЫВАЕМ RELEASE NOTES
# ---------------------------------------------------------

print_section("RELEASE NOTES")

release_response = requests.get(RELEASE_URL, timeout=15)

if release_response.status_code == 200:
    print_success(
        f"✓ Release Notes загружены, статус {release_response.status_code}"
    )
else:
    print_error(
        f"✗ Ошибка загрузки Release Notes: {release_response.status_code}"
    )


# Явно декодируем HTML как UTF-8.
release_html = release_response.content.decode("utf-8")

release_soup = BeautifulSoup(release_html, "html.parser")


# ---------------------------------------------------------
# 4. ПОКАЗЫВАЕМ СТРУКТУРУ RELEASE NOTES
# ---------------------------------------------------------

print_section("РАЗДЕЛЫ RELEASE NOTES")

# Пока оставляем этот вывод для обучения и отладки.
# Позже его можно будет убрать или включать только
# в специальном debug-режиме.
headings = release_soup.find_all(["h1", "h2", "h3"])

for heading in headings:
    heading_text = heading.get_text(strip=True)

    if heading.name in ["h1", "h2"]:
        print(Fore.MAGENTA + Style.BRIGHT + heading_text)
    else:
        print(Fore.CYAN + f"• {heading_text}")


# ---------------------------------------------------------
# 5. ИЩЕМ ПЕРВЫЙ BALANCE CHANGES
# ---------------------------------------------------------

balance_heading = None

for heading in release_soup.find_all("h3"):
    heading_text = heading.get_text(strip=True)

    # Пока берём первый найденный Balance Changes,
    # потому что он относится к наиболее свежему
    # дополнению Release Notes.
    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# ---------------------------------------------------------
# 6. СОБИРАЕМ BUFFS И NERFS
# ---------------------------------------------------------

print_section("BALANCE CHANGES")

# Сырые строки с сайта сначала собираем
# в два отдельных списка.
buffs = []
nerfs = []

# Здесь запоминаем, какой блок сейчас читаем.
# Возможные значения:
# None, "buffs", "nerfs".
current_section = None


if balance_heading:

    # Идём по элементам после заголовка Balance Changes.
    for element in balance_heading.find_all_next():

        # Следующий h3 означает конец текущего раздела.
        if element.name == "h3":
            break

        # Нас интересуют только обычные абзацы.
        if element.name != "p":
            continue

        text = element.get_text(" ", strip=True)

        if not text:
            continue

        # Supercell после списка баланса иногда начинает
        # перечислять исправления приложения без отдельного h3.
        # Эта фраза означает, что баланс уже закончился.
        if text.startswith("AND we're rolling out"):
            break

        # Начался раздел баффов.
        if "BUFFS" in text.upper():
            current_section = "buffs"
            continue

        # Начался раздел нерфов.
        if "NERFS" in text.upper():
            current_section = "nerfs"
            continue

        # Сохраняем строку в соответствующий список.
        if current_section == "buffs":
            buffs.append(text)

        elif current_section == "nerfs":
            nerfs.append(text)

else:
    print_warning("⚠ Раздел Balance Changes не найден")


# ---------------------------------------------------------
# 7. ПРЕВРАЩАЕМ СЫРЫЕ СТРОКИ В СТРУКТУРИРОВАННЫЕ ДАННЫЕ
# ---------------------------------------------------------

# Сначала отделяем имя бойца от описания.
parsed_buffs = [parse_balance_change(buff) for buff in buffs]
parsed_nerfs = [parse_balance_change(nerf) for nerf in nerfs]


# Теперь внутри каждого бойца разбиваем длинное описание
# на отдельные изменения.
#
# В результате структура выглядит примерно так:
#
# {
#     "brawler": "SURGE",
#     "changes": [
#         "Power Shield cooldown increased...",
#         "Hypercharge range reduced...",
#         ...
#     ]
# }
for buff in parsed_buffs:
    buff["changes"] = split_changes(buff["change"])

for nerf in parsed_nerfs:
    nerf["changes"] = split_changes(nerf["change"])


# ---------------------------------------------------------
# 8. КРАСИВО ВЫВОДИМ BUFFS
# ---------------------------------------------------------

print()
print(
    Fore.GREEN
    + Style.BRIGHT
    + f"📈 BUFFS: {len(parsed_buffs)}"
)

for buff in parsed_buffs:
    # Сначала имя бойца.
    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"\n  + {buff['brawler']}"
    )

    # Затем каждое изменение отдельной строкой.
    for change in buff["changes"]:
        print(Fore.WHITE + f"      • {change}")


# ---------------------------------------------------------
# 9. КРАСИВО ВЫВОДИМ NERFS
# ---------------------------------------------------------

print()
print(
    Fore.RED
    + Style.BRIGHT
    + f"📉 NERFS: {len(parsed_nerfs)}"
)

for nerf in parsed_nerfs:
    # Имя бойца выводим красным.
    print(
        Fore.RED
        + Style.BRIGHT
        + f"\n  - {nerf['brawler']}"
    )

    # Несколько изменений одного бойца
    # показываем отдельными строками.
    for change in nerf["changes"]:
        print(Fore.WHITE + f"      • {change}")


# ---------------------------------------------------------
# 10. ИТОГОВЫЙ СТАТУС
# ---------------------------------------------------------

print_section("STATUS")

print_success(f"✓ Статус блога: {response.status_code}")
print_success(
    f"✓ Статус Release Notes: {release_response.status_code}"
)

print(f"Размер страницы блога: {len(blog_html)} символов")
print(f"Найдено статей: {len(seen_links)}")
print(f"Найдено баффов: {len(parsed_buffs)}")
print(f"Найдено нерфов: {len(parsed_nerfs)}")
