import json
import os
import re
from datetime import date
from difflib import SequenceMatcher

import requests
from bs4 import BeautifulSoup
from colorama import Fore, Style, init

# ---------------------------------------------------------
# НАСТРОЙКА ЦВЕТНОГО ВЫВОДА
# ---------------------------------------------------------

init(autoreset=True)


# ---------------------------------------------------------
# URL И ФАЙЛЫ
# ---------------------------------------------------------

# Главная страница официального блога Brawl Stars.
BLOG_URL = "https://supercell.com/en/games/brawlstars/blog/"

# Официальный русский архив Brawl Stars.
# Slug русской статьи может отличаться от английского,
# поэтому ссылки из него собираем отдельно.
RU_BLOG_URL = "https://supercell.com/en/games/brawlstars/ru/blog/"

# Базовый адрес сайта.
BASE_URL = "https://supercell.com"

# Минимальное сходство нормализованных заголовков,
# при котором соответствие считаем достаточно надёжным.
RU_TITLE_MATCH_THRESHOLD = 0.55

# Если два кандидата получили почти одинаковый score,
# безопаснее не выбирать ни один из них автоматически.
RU_TITLE_MATCH_MARGIN = 0.05

# Подробную диагностику сопоставления можно включить
# отдельно, не делая обычный запуск монитора шумным.
DEBUG_RU_MATCHING = False

# Английские и русские названия месяцев приводим
# к одному номеру без сторонних библиотек и API.
ARTICLE_MONTHS = {
    "jan": 1,
    "january": 1,
    "янв": 1,
    "января": 1,
    "feb": 2,
    "february": 2,
    "фев": 2,
    "февраля": 2,
    "mar": 3,
    "march": 3,
    "мар": 3,
    "марта": 3,
    "apr": 4,
    "april": 4,
    "апр": 4,
    "апреля": 4,
    "may": 5,
    "мая": 5,
    "jun": 6,
    "june": 6,
    "июн": 6,
    "июня": 6,
    "jul": 7,
    "july": 7,
    "июл": 7,
    "июля": 7,
    "aug": 8,
    "august": 8,
    "авг": 8,
    "августа": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "сен": 9,
    "сент": 9,
    "сентября": 9,
    "oct": 10,
    "october": 10,
    "окт": 10,
    "октября": 10,
    "nov": 11,
    "november": 11,
    "ноя": 11,
    "ноября": 11,
    "dec": 12,
    "december": 12,
    "дек": 12,
    "декабря": 12,
}

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

    return [part.strip() for part in parts if part.strip()]


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
    high_priority_articles,
    medium_priority_articles,
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
        # Полный список сохраняем для совместимости
        # и возможной ручной редакторской проверки.
        "new_articles": new_articles,
        # Отдельные списки нужны генератору поста.
        # LOW остаются только в общем new_articles.
        "high_priority_articles": high_priority_articles,
        "medium_priority_articles": medium_priority_articles,
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

    return item["brawler"] + "|" + item["change"]


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
        print_warning(f"⚠ Не удалось загрузить статью: {article_url}")

        return []

    # Supercell использует UTF-8.
    html = response.content.decode("utf-8")

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    content = []

    # Собираем основные текстовые элементы статьи.
    for element in soup.find_all(["h1", "h2", "h3", "p"]):
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


def clean_article_content(content, article_title):
    """
    Очищает сырой текст статьи от повторов и служебных строк.

    На входе:
    [
        "Название статьи",
        "Название статьи",
        "Some useful paragraph...",
        "Another paragraph...",
        ...
    ]

    На выходе:
    [
        "Some useful paragraph...",
        "Another paragraph...",
        ...
    ]
    """

    cleaned = []

    for text in content:

        # Убираем пустые строки.
        if not text:
            continue

        # Убираем повтор самого заголовка статьи.
        if text.strip() == article_title.strip():
            continue

        # Убираем служебные элементы Supercell.
        if text in (
            "Follow us on",
            "Download our games from",
        ):
            continue

        # Не сохраняем одинаковый текст дважды подряд.
        if cleaned and cleaned[-1] == text:
            continue

        cleaned.append(text)

    return cleaned


def normalize_article_date(date_text):
    """
    Приводит английскую или русскую дату статьи
    к безопасному формату YYYY-MM-DD.

    Поддерживаем цифровой ISO-формат, английский порядок
    month-day-year и порядок day-month-year, используемый
    как английскими, так и русскими страницами архива.

    Если набор токенов, месяц или календарная дата
    не распознаны надёжно, ничего не угадываем.
    """

    if not isinstance(date_text, str):
        return None

    normalized_text = date_text.strip().casefold()

    if not normalized_text:
        return None

    # Уже нормализованную дату проверяем через date,
    # чтобы исключить невозможные значения календаря.
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized_text):
        try:
            return date.fromisoformat(normalized_text).isoformat()
        except ValueError:
            return None

    # Запятые, точки и русское сокращение года
    # являются оформлением и не влияют на саму дату.
    normalized_text = re.sub(
        r"[.,]",
        " ",
        normalized_text,
    )
    tokens = normalized_text.split()
    tokens = [token for token in tokens if token not in ("г", "год", "года")]

    if len(tokens) != 3:
        return None

    # Aug 3 2026 и August 3 2026.
    if tokens[0] in ARTICLE_MONTHS:
        month_token, day_token, year_token = tokens

    # 3 Aug 2026 и 3 августа 2026.
    elif tokens[1] in ARTICLE_MONTHS:
        day_token, month_token, year_token = tokens

    else:
        return None

    if not day_token.isdigit() or not year_token.isdigit():
        return None

    day_value = int(day_token)
    month_value = ARTICLE_MONTHS[month_token]
    year_value = int(year_token)

    try:
        return date(
            year_value,
            month_value,
            day_value,
        ).isoformat()
    except ValueError:
        return None


def extract_archive_article_date(link):
    """
    Извлекает дату из карточки статьи архива Supercell.

    Заголовок и дата находятся внутри одного контейнера
    archived-article. Если структура страницы изменилась
    или дата отсутствует, возвращаем None без догадок.
    """

    article_container = link.find_parent(attrs={"data-test-class": "archived-article"})

    if article_container is None:
        return None

    date_element = article_container.find(attrs={"data-test-id": "publish-date-text"})

    if date_element is None:
        return None

    date_text = date_element.get_text(
        " ",
        strip=True,
    )

    return normalize_article_date(date_text)


def fetch_russian_articles():
    """
    Загружает официальный русский архив Brawl Stars
    и возвращает краткие данные опубликованных статей.

    Русский slug может быть переведён и не совпадать
    с английским URL. Поэтому собираем реальные ссылки
    из архива, а не пытаемся построить их заменой строки.
    """

    response = requests.get(
        RU_BLOG_URL,
        timeout=15,
    )

    # Ошибка русского архива не должна останавливать
    # основной английский монитор и сохранение изменений.
    if response.status_code != 200:
        print_warning(f"⚠ Не удалось загрузить русский архив: {response.status_code}")

        return []

    html = response.content.decode("utf-8")

    soup = BeautifulSoup(
        html,
        "html.parser",
    )

    russian_articles = []
    seen_links = set()

    for link in soup.find_all("a"):
        href = link.get("href")

        if not href:
            continue

        # Оставляем только статьи русского архива Brawl Stars.
        if "/games/brawlstars/ru/blog/" not in href:
            continue

        # Ссылки пагинации не являются статьями.
        if "/ru/blog/page/" in href:
            continue

        # Не добавляем одну русскую статью несколько раз,
        # даже если на странице есть повторяющиеся ссылки.
        if href in seen_links:
            continue

        seen_links.add(href)

        title = link.get_text(strip=True)

        # Технические ссылки без заголовка пропускаем.
        if not title:
            continue

        if href.startswith("http"):
            full_url = href
        else:
            full_url = BASE_URL + href

        russian_articles.append(
            {
                "title": title,
                "url": full_url,
                "category": get_article_category(href),
                "date": extract_archive_article_date(link),
                # Индекс отражает порядок только среди
                # уникальных статей текущей страницы архива.
                "archive_index": len(russian_articles),
            }
        )

    return russian_articles


def normalize_article_title(title):
    """
    Нормализует заголовок для безопасного сравнения.

    Регистр, пунктуация и лишние пробелы не должны
    мешать сопоставлению одинаковых или близких названий.
    При этом слова не переводим и не угадываем смысл,
    чтобы не создавать слишком агрессивные совпадения.
    """

    if not isinstance(title, str):
        return ""

    normalized_title = title.lower()

    # Заменяем пунктуацию пробелами, но сохраняем буквы
    # разных алфавитов и цифры, важные для названий и дат.
    normalized_title = re.sub(
        r"[^\w\s]",
        " ",
        normalized_title,
    )

    # Несколько пробелов и неразрывные пробелы
    # приводим к одному обычному разделителю.
    return " ".join(normalized_title.split())


def find_article_by_title_similarity(article, candidates):
    """
    Выбирает кандидата по сходству заголовков.

    Этот способ используется только как дополнительный
    сигнал или fallback, когда надёжной даты нет.
    Порог и margin защищают от слабых и неоднозначных
    совпадений между разными языками.
    """

    normalized_title = normalize_article_title(article.get("title", ""))
    scored_candidates = []

    for russian_article in candidates:
        normalized_russian_title = normalize_article_title(russian_article["title"])

        if not normalized_title or not normalized_russian_title:
            continue

        similarity = SequenceMatcher(
            None,
            normalized_title,
            normalized_russian_title,
        ).ratio()

        scored_candidates.append(
            (
                similarity,
                russian_article,
            )
        )

    if not scored_candidates:
        return None

    # Сначала рассматриваем наиболее похожий заголовок.
    scored_candidates.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    best_similarity, best_article = scored_candidates[0]

    if best_similarity < RU_TITLE_MATCH_THRESHOLD:
        return None

    # Два почти одинаковых результата создают риск
    # выбора неправильной русской статьи.
    if len(scored_candidates) > 1:
        second_similarity = scored_candidates[1][0]

        if best_similarity - second_similarity < RU_TITLE_MATCH_MARGIN:
            return None

    return best_article


def print_russian_match_debug(article, russian_article, method=None):
    """
    Показывает краткую диагностику RU-сопоставления.

    Вывод включается только отдельным флагом, поэтому
    обычный запуск монитора не перегружается деталями.
    Старые статьи без date обрабатываются через get().
    """

    if not DEBUG_RU_MATCHING:
        return

    print(Fore.CYAN + f"\nEN: {article.get('title')}")
    print(Fore.CYAN + f"EN date: {article.get('date')}")

    if russian_article is None:
        print(Fore.YELLOW + "⚠ Русская версия не найдена")
        return

    print(Fore.CYAN + "\nRU candidate:")
    print(Fore.CYAN + russian_article["title"])
    print(Fore.CYAN + f"RU date: {russian_article.get('date')}")
    print(Fore.GREEN + f"🇷🇺 Совпадение найдено по {method}")


def find_russian_article(article, russian_articles):
    """
    Ищет безопасное соответствие английской статьи
    среди материалов официального русского архива.

    Категория является обязательным первым фильтром.
    Одинаковая нормализованная дата считается главным
    межъязыковым сигналом. Заголовок и позиция в архиве
    используются только для fallback или разрешения tie.
    """

    article_category = article.get("category")
    category_candidates = [
        russian_article
        for russian_article in russian_articles
        if russian_article.get("category") == article_category
    ]

    if not category_candidates:
        print_russian_match_debug(article, None)
        return None

    article_date = normalize_article_date(article.get("date"))

    if article_date:
        same_date_candidates = [
            russian_article
            for russian_article in category_candidates
            if normalize_article_date(russian_article.get("date")) == article_date
        ]

        # Единственная статья той же категории и даты
        # считается надёжным межъязыковым соответствием.
        if len(same_date_candidates) == 1:
            match = same_date_candidates[0]
            print_russian_match_debug(article, match, "category + date")
            return match

        if len(same_date_candidates) > 1:
            # Сначала пробуем консервативный title similarity.
            title_match = find_article_by_title_similarity(
                article,
                same_date_candidates,
            )

            if title_match is not None:
                print_russian_match_debug(
                    article,
                    title_match,
                    "category + date + title similarity",
                )
                return title_match

            # Одинаковая позиция помогает только после того,
            # как category и date уже надёжно совпали.
            article_index = article.get("archive_index")

            if article_index is not None:
                index_candidates = [
                    russian_article
                    for russian_article in same_date_candidates
                    if russian_article.get("archive_index") == article_index
                ]

                if len(index_candidates) == 1:
                    match = index_candidates[0]
                    print_russian_match_debug(
                        article,
                        match,
                        "category + date + archive index",
                    )
                    return match

            print_russian_match_debug(article, None)
            return None

        # Известные несовпадающие даты являются сильным
        # отрицательным сигналом. В fallback оставляем только
        # кандидатов, у которых дату определить не удалось.
        fallback_candidates = [
            russian_article
            for russian_article in category_candidates
            if normalize_article_date(russian_article.get("date")) is None
        ]

    else:
        # Старые структуры без date продолжают работать
        # через прежний консервативный title similarity.
        fallback_candidates = category_candidates

    title_match = find_article_by_title_similarity(
        article,
        fallback_candidates,
    )

    if title_match is not None:
        print_russian_match_debug(article, title_match, "title similarity")
        return title_match

    print_russian_match_debug(article, None)
    return None


def enrich_articles_with_russian_versions(articles, russian_articles):
    """
    Добавляет к HIGH и MEDIUM статьям русские данные.

    Английские content и clean_content не изменяются.
    Если соответствие найдено, русский текст загружается
    теми же функциями чтения и очистки, что английский.
    """

    for article in articles:
        russian_article = find_russian_article(
            article,
            russian_articles,
        )

        if russian_article is None:
            article.update(
                {
                    "ru_found": False,
                    "ru_title": None,
                    "ru_url": None,
                    "ru_content": [],
                    "ru_clean_content": [],
                }
            )

            continue

        ru_content = fetch_article_text(russian_article["url"])
        ru_clean_content = clean_article_content(
            ru_content,
            russian_article["title"],
        )

        article.update(
            {
                "ru_found": True,
                "ru_title": russian_article["title"],
                "ru_url": russian_article["url"],
                "ru_content": ru_content,
                "ru_clean_content": ru_clean_content,
            }
        )

    return articles


def evaluate_article(article):
    """
    Оценивает, стоит ли использовать статью
    в будущем утреннем выпуске Roblox Hub.

    Возвращаем словарь:

    {
        "is_relevant": True,
        "priority": "high",
        "score": 7,
        "reasons": [
            "Есть изменения баланса",
            "Есть новый боец",
        ],
    }

    Чем выше score, тем интереснее статья
    для новостного выпуска.
    """

    category = article["category"]

    # clean_content уже содержит очищенный текст статьи.
    content = article.get(
        "clean_content",
        [],
    )

    # Склеиваем весь текст в одну строку,
    # чтобы было удобнее искать ключевые слова.
    full_text = " ".join(content).lower()

    score = 0
    reasons = []

    # -----------------------------------------------------
    # RELEASE NOTES
    # -----------------------------------------------------

    # Release Notes почти всегда потенциально полезны,
    # потому что содержат реальные изменения игры.
    if category == "release-notes":
        score += 3

        reasons.append("Официальные Release Notes")

    # -----------------------------------------------------
    # БАЛАНС
    # -----------------------------------------------------

    balance_keywords = [
        "balance changes",
        "buffs",
        "nerfs",
        "buff",
        "nerf",
    ]

    if any(keyword in full_text for keyword in balance_keywords):
        score += 4

        reasons.append("Есть изменения баланса")

    # -----------------------------------------------------
    # НОВЫЕ БОЙЦЫ
    # -----------------------------------------------------

    brawler_keywords = [
        "new brawler",
        "new brawlers",
    ]

    if any(keyword in full_text for keyword in brawler_keywords):
        score += 5

        reasons.append("Есть новый боец")

    # -----------------------------------------------------
    # HYPERCHARGE / NANOpower
    # -----------------------------------------------------

    power_keywords = [
        "new hypercharge",
        "new hypercharges",
        "nanopower",
    ]

    if any(keyword in full_text for keyword in power_keywords):
        score += 4

        reasons.append("Есть новая способность или Hypercharge")

    # -----------------------------------------------------
    # НОВЫЕ РЕЖИМЫ
    # -----------------------------------------------------

    mode_keywords = [
        "new game mode",
        "new game modes",
        "game mode",
        "game modes",
    ]

    if any(keyword in full_text for keyword in mode_keywords):
        score += 3

        reasons.append("Есть информация об игровых режимах")

    # -----------------------------------------------------
    # СОБЫТИЯ / КОЛЛАБОРАЦИИ
    # -----------------------------------------------------

    event_keywords = [
        "event",
        "collaboration",
        "collab",
    ]

    if any(keyword in full_text for keyword in event_keywords):
        score += 2

        reasons.append("Есть игровое событие или коллаборация")

    # -----------------------------------------------------
    # ESPORTS
    # -----------------------------------------------------

    # Киберспорт считаем менее приоритетным,
    # потому что он нужен не в каждый утренний выпуск.
    if category == "esports":
        score += 1

        reasons.append("Новость Brawl Stars Esports")

    # -----------------------------------------------------
    # ИТОГОВОЕ РЕШЕНИЕ
    # -----------------------------------------------------

    # Высокий приоритет получают главные материалы,
    # которые можно автоматически рассматривать
    # как кандидатов для утреннего выпуска.
    if score >= 6:
        priority = "high"

    # Средний приоритет оставляем для запасных новостей.
    # Они достаточно содержательные, но пока не должны
    # автоматически попадать в утренний выпуск.
    elif score >= 3:
        priority = "medium"

    # Остальные статьи сохраняем с низким приоритетом.
    # Они остаются доступны редактору и не удаляются.
    else:
        priority = "low"

    # Поле is_relevant сохраняем для совместимости
    # с текущей структурой данных. Теперь только статьи
    # с высоким приоритетом считаются кандидатами в выпуск.
    is_relevant = priority == "high"

    return {
        "is_relevant": is_relevant,
        "priority": priority,
        "score": score,
        "reasons": reasons,
    }


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
        "content": [...],
        "clean_content": [...],
        "is_relevant": False,
        "priority": "low",
        "score": 1,
        "reasons": [...]
    }
    """

    enriched_articles = []

    for article in articles:
        print(Fore.CYAN + f"Читаю статью: {article['title']}")

        content = fetch_article_text(article["url"])

        # Убираем повторы заголовка и служебные строки.
        clean_content = clean_article_content(
            content,
            article["title"],
        )

        enriched_article = {
            **article,
            # Полный сырой текст оставляем для отладки.
            "content": content,
            # Очищенный текст будет использовать
            # будущий генератор новостей.
            "clean_content": clean_content,
        }

        # Добавляем редакторскую оценку статьи:
        # is_relevant, priority, score и reasons.
        # Эти поля пока не влияют на сохранение материалов.
        evaluation = evaluate_article(enriched_article)

        enriched_article.update(evaluation)

        enriched_articles.append(enriched_article)

    return enriched_articles


def split_articles_by_priority(articles):
    """
    Разделяет новые статьи на основные
    и запасные кандидаты для выпуска.

    Статьи с высоким приоритетом считаются
    основными кандидатами. Средний приоритет
    оставляем как запасной источник новости.

    Низкоприоритетные статьи намеренно не входят
    ни в один список кандидатов, но продолжают
    храниться в общем поле new_articles.
    """

    high_priority_articles = []
    medium_priority_articles = []

    for article in articles:
        priority = article.get("priority", "low")

        if priority == "high":
            high_priority_articles.append(article)

        elif priority == "medium":
            medium_priority_articles.append(article)

    return high_priority_articles, medium_priority_articles


# ---------------------------------------------------------
# 1. ЗАГРУЖАЕМ БЛОГ
# ---------------------------------------------------------

print_section("BRAWL STARS BLOG")

response = requests.get(
    BLOG_URL,
    timeout=15,
)

if response.status_code == 200:
    print_success(f"✓ Блог загружен, статус {response.status_code}")
else:
    print_error(f"✗ Ошибка загрузки блога: {response.status_code}")

    raise SystemExit


# Явно декодируем UTF-8,
# чтобы эмодзи отображались корректно.
blog_html = response.content.decode("utf-8")

soup = BeautifulSoup(
    blog_html,
    "html.parser",
)

links = soup.find_all("a")

print(f"Всего ссылок на странице: {len(links)}")


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
        "date": extract_archive_article_date(link),
        # Позиция считается только среди уникальных
        # статей текущей страницы английского архива.
        "archive_index": len(articles),
    }

    articles.append(article)

    # Первая найденная статья release-notes
    # считается актуальной.
    if category == "release-notes" and latest_release_url is None:
        latest_release_url = full_url
        latest_release_title = title


# ---------------------------------------------------------
# 3. КРАСИВО ПОКАЗЫВАЕМ СТАТЬИ
# ---------------------------------------------------------

for article in articles:
    icon = get_category_icon(article["category"])

    print(Fore.YELLOW + Style.BRIGHT + f"{icon} {article['category'].upper()}")

    print(Fore.WHITE + Style.BRIGHT + article["title"])

    print(Fore.BLUE + article["url"])

    print()


# ---------------------------------------------------------
# 4. ПРОВЕРЯЕМ RELEASE NOTES
# ---------------------------------------------------------

print_section("АКТУАЛЬНЫЕ RELEASE NOTES")

if latest_release_url:
    print_success(f"✓ Найдены Release Notes: " f"{latest_release_title}")

    print(Fore.BLUE + latest_release_url)

else:
    print_error("✗ Release Notes не найдены")

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
        f"✓ Release Notes загружены, " f"статус {release_response.status_code}"
    )
else:
    print_error(f"✗ Ошибка загрузки Release Notes: " f"{release_response.status_code}")

    raise SystemExit


release_html = release_response.content.decode("utf-8")

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
        if text.startswith("AND we're rolling out"):
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
    print_warning("⚠ Balance Changes не найден")


# ---------------------------------------------------------
# 8. СТРУКТУРИРУЕМ БАЛАНС
# ---------------------------------------------------------

parsed_buffs = [parse_balance_change(buff) for buff in buffs]

parsed_nerfs = [parse_balance_change(nerf) for nerf in nerfs]


for buff in parsed_buffs:
    buff["changes"] = split_changes(buff["change"])

for nerf in parsed_nerfs:
    nerf["changes"] = split_changes(nerf["change"])


# ---------------------------------------------------------
# 9. ЗАГРУЖАЕМ ПРОШЛОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

print_section("СРАВНЕНИЕ С ПРОШЛЫМ ЗАПУСКОМ")

old_state = load_state()


# ---------------------------------------------------------
# 10. ГОТОВИМ КЛЮЧИ СТАРЫХ ДАННЫХ
# ---------------------------------------------------------

old_buff_keys = {make_change_key(item) for item in old_state["buffs"]}

old_nerf_keys = {make_change_key(item) for item in old_state["nerfs"]}

old_article_keys = {make_article_key(article) for article in old_state["articles"]}


# ---------------------------------------------------------
# 11. ИЩЕМ НОВЫЕ ИЗМЕНЕНИЯ
# ---------------------------------------------------------

new_buffs = [
    buff for buff in parsed_buffs if make_change_key(buff) not in old_buff_keys
]

new_nerfs = [
    nerf for nerf in parsed_nerfs if make_change_key(nerf) not in old_nerf_keys
]

new_articles = [
    article for article in articles if make_article_key(article) not in old_article_keys
]

# ---------------------------------------------------------
# ЗАГРУЖАЕМ СОДЕРЖИМОЕ НОВЫХ СТАТЕЙ
# ---------------------------------------------------------

# Полный текст загружаем только для новых статей.
# Старые статьи повторно открывать нет смысла.
enriched_new_articles = enrich_new_articles(new_articles)

# Готовим отдельные списки кандидатов для генератора поста.
# Полный список enriched_new_articles при этом сохраняется:
# статьи с низким приоритетом из JSON не удаляются.
high_priority_articles, medium_priority_articles = split_articles_by_priority(
    enriched_new_articles
)

# Русский архив загружаем только при наличии кандидатов.
# LOW статьи не входят в эти списки и не требуют поиска
# или дополнительного сетевого запроса.
if high_priority_articles or medium_priority_articles:
    russian_articles = fetch_russian_articles()

    enrich_articles_with_russian_versions(
        high_priority_articles,
        russian_articles,
    )

    enrich_articles_with_russian_versions(
        medium_priority_articles,
        russian_articles,
    )


# ---------------------------------------------------------
# 12. ОПРЕДЕЛЯЕМ ПЕРВЫЙ ЗАПУСК
# ---------------------------------------------------------

first_run = old_state["release_url"] is None and not old_state["articles"]


if first_run:
    print_warning("Первый запуск монитора.")

    print_warning("Текущие данные будут сохранены " "как базовое состояние.")

elif not new_buffs and not new_nerfs and not new_articles:
    print_success("✓ Ничего нового не найдено")

else:
    print_success("✓ Найдены новые материалы")


# ---------------------------------------------------------
# 13. ПОКАЗЫВАЕМ НОВЫЕ СТАТЬИ
# ---------------------------------------------------------

if enriched_new_articles:
    print_section("НОВЫЕ МАТЕРИАЛЫ")

    for article in enriched_new_articles:
        icon = get_category_icon(article["category"])

        print(Fore.YELLOW + Style.BRIGHT + f"{icon} {article['category'].upper()}")

        print(Fore.WHITE + Style.BRIGHT + article["title"])

        print(Fore.BLUE + article["url"])

        # Цвет и формулировка помогают сразу увидеть,
        # насколько статья подходит для выпуска.
        if article["priority"] == "high":
            print(
                Fore.GREEN + f"🔥 HIGH | кандидат в выпуск | score: {article['score']}"
            )

        elif article["priority"] == "medium":
            print(
                Fore.YELLOW
                + f"🟡 MEDIUM | запасная новость | score: {article['score']}"
            )

        else:
            print(
                Fore.WHITE
                + Style.DIM
                + f"⚪ LOW | можно пропустить | score: {article['score']}"
            )

        for reason in article["reasons"]:
            print(Fore.WHITE + f"  • {reason}")

        print()

        # Для теста показываем первые несколько
        # текстовых блоков статьи.
        preview = article["clean_content"][:5]

        for text in preview:
            print(Fore.WHITE + f"  • {text}")


# ---------------------------------------------------------
# 14. ПОКАЗЫВАЕМ НОВЫЕ BUFFS
# ---------------------------------------------------------

if new_buffs:

    print()

    print(Fore.GREEN + Style.BRIGHT + f"📈 НОВЫЕ BUFFS: {len(new_buffs)}")

    for buff in new_buffs:

        print(Fore.GREEN + Style.BRIGHT + f"\n  + {buff['brawler']}")

        for change in buff["changes"]:
            print(Fore.WHITE + f"      • {change}")


# ---------------------------------------------------------
# 15. ПОКАЗЫВАЕМ НОВЫЕ NERFS
# ---------------------------------------------------------

if new_nerfs:

    print()

    print(Fore.RED + Style.BRIGHT + f"📉 НОВЫЕ NERFS: {len(new_nerfs)}")

    for nerf in new_nerfs:

        print(Fore.RED + Style.BRIGHT + f"\n  - {nerf['brawler']}")

        for change in nerf["changes"]:
            print(Fore.WHITE + f"      • {change}")


# ---------------------------------------------------------
# 16. СОХРАНЯЕМ СВЕЖИЕ ДАННЫЕ
# ---------------------------------------------------------

save_latest_changes(
    latest_release_title,
    latest_release_url,
    new_buffs,
    new_nerfs,
    enriched_new_articles,
    high_priority_articles,
    medium_priority_articles,
)

print_success(f"\n✓ Свежие данные сохранены в " f"{LATEST_CHANGES_FILE}")


# ---------------------------------------------------------
# 17. ОБНОВЛЯЕМ ПОЛНОЕ СОСТОЯНИЕ
# ---------------------------------------------------------

save_state(
    latest_release_url,
    parsed_buffs,
    parsed_nerfs,
    articles,
)

print_success("✓ Состояние монитора обновлено")


# ---------------------------------------------------------
# 18. ИТОГ
# ---------------------------------------------------------

print_section("STATUS")

print(f"Release Notes: {latest_release_title}")

print(f"Всего статей: {len(articles)}")

print(f"Новых статей: {len(new_articles)}")

print(f"High priority статей: {len(high_priority_articles)}")

print(f"Medium priority статей: {len(medium_priority_articles)}")

print(f"Всего баффов: {len(parsed_buffs)}")

print(f"Всего нерфов: {len(parsed_nerfs)}")

print(f"Новых баффов: {len(new_buffs)}")

print(f"Новых нерфов: {len(new_nerfs)}")

print(f"State-файл: {STATE_FILE}")
