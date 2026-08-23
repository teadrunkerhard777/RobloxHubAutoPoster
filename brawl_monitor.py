from bs4 import BeautifulSoup
from colorama import Fore, Style, init
import requests


# ---------------------------------------------------------
# НАСТРОЙКА ЦВЕТНОГО ВЫВОДА
# ---------------------------------------------------------

# autoreset=True автоматически возвращает обычный цвет
# после каждого print, поэтому цвета не "протекают"
# на следующие строки.
init(autoreset=True)


# ---------------------------------------------------------
# URL ИСТОЧНИКОВ
# ---------------------------------------------------------

# Главная страница официального блога Brawl Stars.
BLOG_URL = "https://supercell.com/en/games/brawlstars/blog/"

# Пока вручную указываем актуальную страницу Release Notes.
# Позже научим скрипт находить её автоматически.
RELEASE_URL = (
    "https://supercell.com"
    "/en/games/brawlstars/blog/release-notes/release-notes-june-2026/"
)


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ КРАСИВОГО ВЫВОДА
# ---------------------------------------------------------

def print_section(title):
    """Печатает крупный заголовок раздела."""
    print(Fore.CYAN + Style.BRIGHT + f"\n=== {title} ===")


def print_success(text):
    """Печатает успешный статус зелёным цветом."""
    print(Fore.GREEN + text)


def print_warning(text):
    """Печатает предупреждение жёлтым цветом."""
    print(Fore.YELLOW + text)


def print_error(text):
    """Печатает ошибку красным цветом."""
    print(Fore.RED + Style.BRIGHT + text)


# ---------------------------------------------------------
# 1. ПОЛУЧАЕМ ГЛАВНУЮ СТРАНИЦУ БЛОГА
# ---------------------------------------------------------

print_section("BRAWL STARS BLOG")

response = requests.get(BLOG_URL, timeout=15)

# Проверяем, успешно ли загрузилась страница.
if response.status_code == 200:
    print_success(f"✓ Блог загружен, статус {response.status_code}")
else:
    print_error(f"✗ Ошибка загрузки блога: {response.status_code}")


# Явно декодируем страницу как UTF-8.
# Это нужно для корректного отображения эмодзи и спецсимволов.
blog_html = response.content.decode("utf-8")

# BeautifulSoup превращает HTML в удобную структуру.
soup = BeautifulSoup(blog_html, "html.parser")

# Находим все ссылки на странице.
links = soup.find_all("a")

print(Fore.WHITE + f"Всего ссылок на странице: {len(links)}")


# ---------------------------------------------------------
# 2. ИЩЕМ СТАТЬИ BRAWL STARS
# ---------------------------------------------------------

print_section("ПОСЛЕДНИЕ СТАТЬИ")

# Здесь будем хранить уже найденные ссылки,
# чтобы одна статья не выводилась несколько раз.
seen_links = set()

article_number = 1

for link in links:
    href = link.get("href")

    # Если ссылки нет, пропускаем элемент.
    if not href:
        continue

    # Берём только страницы блога Brawl Stars.
    if "/games/brawlstars/blog/" not in href:
        continue

    # Пагинация нам не нужна.
    if "/blog/page/" in href:
        continue

    # Не выводим одну ссылку дважды.
    if href in seen_links:
        continue

    seen_links.add(href)

    # Получаем название статьи.
    title = link.get_text(strip=True)

    # Номер статьи выделяем жёлтым,
    # название делаем более заметным белым.
    print(
        Fore.YELLOW
        + Style.BRIGHT
        + f"{article_number}. "
        + Fore.WHITE
        + Style.BRIGHT
        + title
    )

    # Ссылку показываем менее ярким цветом.
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


# Декодируем HTML как UTF-8.
release_html = release_response.content.decode("utf-8")

# Разбираем страницу Release Notes.
release_soup = BeautifulSoup(release_html, "html.parser")


# ---------------------------------------------------------
# 4. ПОКАЗЫВАЕМ СТРУКТУРУ RELEASE NOTES
# ---------------------------------------------------------

print_section("РАЗДЕЛЫ RELEASE NOTES")

# Находим заголовки статьи.
headings = release_soup.find_all(["h1", "h2", "h3"])

for heading in headings:
    heading_text = heading.get_text(strip=True)

    # h1 / h2 делаем заметнее,
    # h3 оставляем обычным голубым.
    if heading.name in ["h1", "h2"]:
        print(Fore.MAGENTA + Style.BRIGHT + heading_text)
    else:
        print(Fore.CYAN + f"• {heading_text}")


# ---------------------------------------------------------
# 5. ИЩЕМ ПЕРВЫЙ РАЗДЕЛ BALANCE CHANGES
# ---------------------------------------------------------

balance_heading = None

for heading in release_soup.find_all("h3"):
    heading_text = heading.get_text(strip=True)

    # Берём первый Balance Changes,
    # потому что сейчас это самый свежий блок изменений.
    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# ---------------------------------------------------------
# 6. РАЗБИРАЕМ BALANCE CHANGES НА BUFFS И NERFS
# ---------------------------------------------------------

print_section("BALANCE CHANGES")

# В эти списки будем складывать найденные изменения.
buffs = []
nerfs = []

# Здесь будем помнить, какой раздел сейчас читаем:
# "buffs", "nerfs" или None.
current_section = None


if balance_heading:

    # Идём по элементам после заголовка Balance Changes.
    for element in balance_heading.find_all_next():

        # Если встретили следующий h3,
        # значит раздел Balance Changes закончился.
        if element.name == "h3":
            break

        # Пока работаем только с обычными абзацами <p>.
        if element.name != "p":
            continue

        # Получаем чистый текст текущего абзаца.
        text = element.get_text(" ", strip=True)

        # Пустые абзацы пропускаем.
        if not text:
            continue

        # -------------------------------------------------
        # ПРОВЕРЯЕМ, НЕ ЗАКОНЧИЛСЯ ЛИ БЛОК БАЛАНСА
        # -------------------------------------------------

        # После последних нерфов Supercell иногда сразу
        # начинает перечислять исправления приложения.
        # Эта фраза означает, что Balance Changes закончился.
        if text.startswith("AND we're rolling out"):
            break

        # -------------------------------------------------
        # ОПРЕДЕЛЯЕМ НАЧАЛО BUFFS
        # -------------------------------------------------

        if "BUFFS" in text.upper():
            current_section = "buffs"
            continue

        # -------------------------------------------------
        # ОПРЕДЕЛЯЕМ НАЧАЛО NERFS
        # -------------------------------------------------

        if "NERFS" in text.upper():
            current_section = "nerfs"
            continue

        # -------------------------------------------------
        # СОХРАНЯЕМ ИЗМЕНЕНИЕ В НУЖНЫЙ СПИСОК
        # -------------------------------------------------

        if current_section == "buffs":
            buffs.append(text)

        elif current_section == "nerfs":
            nerfs.append(text)

else:
    print_warning("⚠ Раздел Balance Changes не найден")

    # ---------------------------------------------------------
# 7. РАЗДЕЛЯЕМ ИМЯ БОЙЦА И ОПИСАНИЕ ИЗМЕНЕНИЯ
# ---------------------------------------------------------


def parse_balance_change(text):
    """
    Разделяет строку вида:

    CROW - Main attack damage reduced from 420 ➡️ 380

    на словарь:

    {
        "brawler": "CROW",
        "change": "Main attack damage reduced from 420 ➡️ 380"
    }
    """

    # Разделяем только по первому " - ".
    # Это важно, потому что внутри описания тоже могут встречаться дефисы.
    parts = text.split(" - ", 1)

    # Если строка неожиданно не содержит разделителя,
    # сохраняем её целиком как описание.
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


# Превращаем обычные строки в структурированные словари.
parsed_buffs = [parse_balance_change(buff) for buff in buffs]
parsed_nerfs = [parse_balance_change(nerf) for nerf in nerfs]


# ---------------------------------------------------------
# 7. КРАСИВО ВЫВОДИМ BUFFS
# ---------------------------------------------------------

print()
print(Fore.GREEN + Style.BRIGHT + f"📈 BUFFS: {len(parsed_buffs)}")

for buff in parsed_buffs:
    print(
        Fore.GREEN
        + Style.BRIGHT
        + f"  + {buff['brawler']}"
        + Fore.WHITE
        + f" | {buff['change']}"
    )


# ---------------------------------------------------------
# 8. КРАСИВО ВЫВОДИМ NERFS
# ---------------------------------------------------------

print()
print(Fore.RED + Style.BRIGHT + f"📉 NERFS: {len(parsed_nerfs)}")

for nerf in parsed_nerfs:
    print(
        Fore.RED
        + Style.BRIGHT
        + f"  - {nerf['brawler']}"
        + Fore.WHITE
        + f" | {nerf['change']}"
    )
