from bs4 import BeautifulSoup
import requests


BLOG_URL = "https://supercell.com/en/games/brawlstars/blog/"


response = requests.get(BLOG_URL, timeout=15)

soup = BeautifulSoup(response.text, "html.parser")

links = soup.find_all("a")

print("Всего ссылок:", len(links))

seen_links = set()

for link in links:
    href = link.get("href")

    if not href:
        continue

    # Берём только статьи Brawl Stars
    if "/games/brawlstars/blog/" not in href:
        continue

    # Пропускаем страницы пагинации
    if "/blog/page/" in href:
        continue

    # Пропускаем дубли
    if href in seen_links:
        continue

    seen_links.add(href)

    title = link.get_text(strip=True)

    print("Заголовок:", title)
    print("Ссылка:", href)
    print()


    RELEASE_URL = (
    "https://supercell.com"
    "/en/games/brawlstars/blog/release-notes/release-notes-june-2026/"
)

release_response = requests.get(RELEASE_URL, timeout=15)
release_soup = BeautifulSoup(release_response.text, "html.parser")

print("Release Notes статус:", release_response.status_code)

headings = release_soup.find_all(["h1", "h2", "h3"])

for heading in headings:
    print(heading.name, "->", heading.get_text(strip=True))

# Ищем первый заголовок h3 с текстом "Balance Changes:"
balance_heading = None

for heading in release_soup.find_all("h3"):
    # strip=True убирает лишние пробелы и переносы строк
    heading_text = heading.get_text(strip=True)

    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# Если нужный заголовок нашли, начинаем собирать текст после него
if balance_heading:
    print("\n=== BALANCE CHANGES ===")

    # Берём следующие элементы после найденного заголовка
    # и идём по ним по порядку
    for element in balance_heading.find_all_next():

        # Если встретили следующий h3,
        # значит текущий раздел закончился
        if element.name == "h3":
            break

        # Пока для проверки выводим только обычные абзацы
        if element.name == "p":
            text = element.get_text(" ", strip=True)

            if text:
                print(text)

else:
    print("Раздел Balance Changes не найден")


# Ищем первый заголовок h3 с текстом "Balance Changes:"
balance_heading = None

for heading in release_soup.find_all("h3"):
    # strip=True убирает лишние пробелы и переносы строк
    heading_text = heading.get_text(strip=True)

    if heading_text == "Balance Changes:":
        balance_heading = heading
        break


# Если нужный заголовок нашли, начинаем собирать текст после него
if balance_heading:
    print("\n=== BALANCE CHANGES ===")

    # Берём следующие элементы после найденного заголовка
    # и идём по ним по порядку
    for element in balance_heading.find_all_next():

        # Если встретили следующий h3,
        # значит текущий раздел закончился
        if element.name == "h3":
            break

        # Пока для проверки выводим только обычные абзацы
        if element.name == "p":
            text = element.get_text(" ", strip=True)

            if text:
                print(text)

else:
    print("Раздел Balance Changes не найден")


# ПРИНТЫ СТАТУСА

print("Статус:", response.status_code)
print("Размер страницы:", len(response.text))
