import json
import os
import re

from colorama import Fore, Style, init

# ---------------------------------------------------------
# НАСТРОЙКА ЦВЕТНОГО ВЫВОДА
# ---------------------------------------------------------

# После каждого print цвет автоматически сбрасывается.
init(autoreset=True)


# ---------------------------------------------------------
# ФАЙЛ С ДАННЫМИ МОНИТОРА
# ---------------------------------------------------------

# Этот JSON создаёт brawl_monitor.py.
# В нём находятся только новые изменения,
# найденные во время последнего запуска монитора.
LATEST_CHANGES_FILE = "data/brawl_latest_changes.json"

# ---------------------------------------------------------
# DEBUG-РЕЖИМ
# ---------------------------------------------------------

# True  -> показываем служебную информацию и score бойцов.
# False -> выводим только обычный результат.
DEBUG = False


# ---------------------------------------------------------
# ОГРАНИЧЕНИЯ РУССКОГО NEWS PREVIEW
# ---------------------------------------------------------

# Берём не больше двух официальных текстовых блоков.
# Этого достаточно для короткого редакторского preview,
# который удобно просматривать перед Telegram-выпуском.
NEWS_MAX_BLOCKS = 2

# Общий объём выбранного текста ограничиваем,
# чтобы терминальный preview оставался коротким.
NEWS_MAX_CHARS = 450

# Короткие подписи и элементы навигации обычно
# не содержат самостоятельной новости.
NEWS_MIN_BLOCK_LENGTH = 25

# Короткий блок без завершающей пунктуации чаще всего
# оказывается подзаголовком или названием этапа, а не
# самостоятельным содержательным предложением.
NEWS_SHORT_HEADING_MAX_CHARS = 60

# Удаляем только строки, которые начинаются с явной
# структуры расписания «День N |» или «Day N |».
# Обычный абзац со словом «день» это правило не затронет.
NEWS_DAY_STAGE_PATTERN = r"^(?:день|day)\s+\d+\s*\|"

# Эти префиксы относятся к навигации, социальным сетям
# и техническим элементам сайта, а не к тексту статьи.
NEWS_SERVICE_PREFIXES = (
    "download our games from",
    "follow us on",
    "share",
    "загрузите наши игры",
    "поделиться",
    "подписывайтесь на нас",
    "скачайте наши игры",
)


# ---------------------------------------------------------
# ОГРАНИЧЕНИЯ ФИНАЛЬНОГО TELEGRAM-ПОСТА
# ---------------------------------------------------------

# Финальный выпуск должен быстро читаться с телефона.
# Лимит заметно ниже технического ограничения Telegram,
# потому что это редакционное правило короткого формата.
FINAL_POST_MAX_CHARS = 1400

# Сохраняем уже принятую для Balance Changes квоту:
# максимум три бойца с баффами и четыре с нерфами.
FINAL_BALANCE_MAX_BUFFS = 3
FINAL_BALANCE_MAX_NERFS = 4

# Автоматически меняем регистр только у полностью прописных
# заголовков. Эти известные игровые и брендовые названия
# восстанавливаем после безопасного перевода остальных слов
# в обычный регистр.
NEWS_TITLE_CASE_EXCEPTIONS = (
    ("brawl stars", "Brawl Stars"),
    ("hypercharge", "Hypercharge"),
    ("supercell", "Supercell"),
    ("adidas", "adidas"),
    ("npc", "NPC"),
    ("старр", "Старр"),
)

# Если полностью прописной заголовок содержит неизвестную
# латинскую аббревиатуру, оставляем официальный вариант как
# есть. Так генератор не испортит новое имя или бренд.
NEWS_TITLE_SAFE_LATIN_WORDS = {
    "ADIDAS",
    "BRAWL",
    "HYPERCHARGE",
    "NPC",
    "STARS",
    "SUPERCELL",
}


# ---------------------------------------------------------
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ---------------------------------------------------------


def print_section(title):
    """Выводит красивый заголовок раздела в терминале."""
    print(Fore.CYAN + Style.BRIGHT + f"\n=== {title} ===")


def load_latest_changes():
    """
    Загружает свежие изменения из JSON.

    Если файл ещё не существует,
    возвращаем None.
    """

    if not os.path.exists(LATEST_CHANGES_FILE):
        return None

    with open(
        LATEST_CHANGES_FILE,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def get_news_candidates(data):
    """
    Получает подготовленные монитором статьи-кандидаты.

    Используем get() с пустыми списками, чтобы генератор
    продолжал работать со старыми latest changes JSON,
    в которых новых полей ещё не было.

    HIGH считаются основными кандидатами выпуска.
    MEDIUM остаются запасными. LOW монитор не добавляет
    ни в один из этих списков, поэтому генератор их
    полностью игнорирует.
    """

    high_priority_articles = data.get(
        "high_priority_articles",
        [],
    )

    medium_priority_articles = data.get(
        "medium_priority_articles",
        [],
    )

    return high_priority_articles, medium_priority_articles


def print_news_candidates(high_priority_articles, medium_priority_articles):
    """
    Показывает статьи-кандидаты только в терминале.

    Этот блок нужен для проверки нового pipeline данных.
    В готовый Telegram-пост статьи пока не добавляются.
    """

    print_section("NEWS CANDIDATES")

    # Все HIGH показываем как основных кандидатов.
    for article in high_priority_articles:
        print(Fore.GREEN + Style.BRIGHT + "\n🔥 HIGH")
        print(Fore.WHITE + Style.BRIGHT + article["title"])
        print(f"Категория: {article['category']}")
        print(f"Score: {article['score']}")
        print_russian_article_status(article)

    # MEDIUM выводим отдельно как запасные новости.
    for article in medium_priority_articles:
        print(Fore.YELLOW + Style.BRIGHT + "\n🟡 MEDIUM")
        print(Fore.WHITE + Style.BRIGHT + article["title"])
        print(f"Категория: {article['category']}")
        print(f"Score: {article['score']}")
        print_russian_article_status(article)

    # Если основных кандидатов нет, явно подсказываем,
    # что редактор может использовать запасной материал.
    if not high_priority_articles and medium_priority_articles:
        print(
            Fore.YELLOW
            + "\nВысокоприоритетных новостей нет, "
            + "можно использовать MEDIUM."
        )


def print_russian_article_status(article):
    """
    Показывает наличие официальной русской версии.

    Старые JSON могут не содержать ru_found и другие
    новые поля. В этом случае безопасно показываем,
    что русская версия пока не найдена.
    """

    if article.get("ru_found"):
        print(Fore.GREEN + "🇷🇺 Русская версия найдена")
        print(Fore.GREEN + f"Название: {article['ru_title']}")
        print(Fore.GREEN + f"URL: {article['ru_url']}")

    else:
        print(Fore.YELLOW + "⚠ Русская версия пока не найдена")


def select_news_content(article):
    """
    Выбирает короткий набор содержательных русских блоков.

    Используем только официальный ru_clean_content.
    Текст не переводим, не пересказываем и не исправляем:
    функция лишь исключает служебные строки и применяет
    безопасные ограничения количества и общей длины.
    """

    # Английский текст не используем как fallback.
    # Без найденной русской версии preview не создаётся.
    if not article.get("ru_found"):
        return []

    ru_content = article.get(
        "ru_clean_content",
        [],
    )

    if not ru_content:
        return []

    ru_title_value = article.get("ru_title") or ""
    ru_title = " ".join(ru_title_value.split()).casefold()
    selected_blocks = []
    selected_chars = 0

    for raw_block in ru_content:
        if len(selected_blocks) >= NEWS_MAX_BLOCKS:
            break

        # Неожиданные значения в старом JSON пропускаем,
        # чтобы одна повреждённая строка не ломала preview.
        if not isinstance(raw_block, str):
            continue

        # Нормализуем только пробелы. Слова, числа, даты
        # и пунктуацию официального текста не переписываем.
        block = " ".join(raw_block.split())

        if not block:
            continue

        normalized_block = block.casefold()

        # Повтор русского заголовка не является
        # самостоятельным содержательным абзацем.
        if ru_title and normalized_block == ru_title:
            continue

        if len(block) < NEWS_MIN_BLOCK_LENGTH:
            continue

        # Короткие названия этапов из календаря события
        # не несут достаточно контекста для отдельного
        # preview-блока. Проверяем только строгое начало
        # «День N |» / «Day N |», поэтому содержательные
        # предложения со словом «день» сохраняются.
        if re.match(NEWS_DAY_STAGE_PATTERN, normalized_block):
            continue

        # Одиночный короткий блок без точки, вопросительного
        # или восклицательного знака обычно является ещё одним
        # подзаголовком. Более длинные абзацы не отбрасываем:
        # у официального сайта завершающая пунктуация иногда
        # может отсутствовать после извлечения HTML-текста.
        if len(block) <= NEWS_SHORT_HEADING_MAX_CHARS and not re.search(
            r"[.!?…][\"'»”)]*$", block
        ):
            continue

        # Очевидные элементы подвала и навигации
        # отбрасываем независимо от их длины.
        if normalized_block.startswith(NEWS_SERVICE_PREFIXES):
            continue

        # Повторный блок не добавляет новой информации.
        if block in selected_blocks:
            continue

        # Между блоками в preview будет пустая строка.
        # Учитываем эти два символа в общем лимите.
        separator_length = 2 if selected_blocks else 0
        candidate_length = separator_length + len(block)

        if selected_chars + candidate_length > NEWS_MAX_CHARS:
            continue

        selected_blocks.append(block)
        selected_chars += candidate_length

    return selected_blocks


def build_article_news_preview(article):
    """
    Формирует отдельный русский preview одной статьи.

    HIGH отмечаем как основной материал, MEDIUM — как
    запасной. LOW и статьи без полезного официального
    русского текста автоматический блок не получают.
    """

    priority = article.get("priority")

    if priority not in ("high", "medium"):
        return None

    if not article.get("ru_found"):
        return None

    ru_title = article.get("ru_title")

    if not ru_title:
        return None

    selected_blocks = select_news_content(article)

    if not selected_blocks:
        return None

    if priority == "high":
        marker = "🔥 HIGH"
    else:
        marker = "🟡 MEDIUM"

    # Склеиваем только выбранные фрагменты оригинального
    # русского текста, не добавляя выводов от генератора.
    news_text = "\n\n".join(selected_blocks)

    return f"{marker}\n\n{ru_title}\n\n{news_text}\n\nИсточник: Supercell"


def print_russian_news_previews(high_priority_articles, medium_priority_articles):
    """
    Показывает русские новостные блоки в терминале.

    Это отдельный предпросмотр pipeline. Он не передаётся
    в build_post() и не становится частью Telegram-поста.
    """

    print_section("RUSSIAN NEWS PREVIEW")

    candidates = high_priority_articles + medium_priority_articles
    available_previews = []

    for article in candidates:
        # Даже если старый или повреждённый JSON случайно
        # содержит LOW в списке, генератор его игнорирует.
        if article.get("priority") not in ("high", "medium"):
            continue

        if not article.get("ru_found"):
            print(Fore.YELLOW + "\n⚠ Пропущено: официальная русская версия не найдена")

            continue

        preview = build_article_news_preview(article)

        if preview is None:
            print(
                Fore.YELLOW + "\n⚠ Пропущено: не удалось получить содержательный текст"
            )

            continue

        if article["priority"] == "high":
            color = Fore.GREEN
        else:
            color = Fore.YELLOW

        print(color + "\n" + preview)

        # Возвращаем только действительно построенные блоки.
        # Итоговый статус генератора не должен считать статью
        # материалом, если русская версия пуста или непригодна.
        available_previews.append(preview)

    return available_previews


def print_generation_result(post, russian_news_previews):
    """
    Выводит итог генерации с учётом двух типов материала.

    Balance Changes по-прежнему формируют готовый пост через
    build_post(). Русские HIGH/MEDIUM статьи пока остаются
    отдельным preview, но их наличие уже означает, что у
    редактора есть материал для будущего выпуска.
    """

    if post is not None:
        print_section("ГОТОВЫЙ ПОСТ")

        # Выводим предпросмотр balance-поста с цветами
        # для удобства чтения в терминале.
        print_colored_post(post)

        return

    if russian_news_previews:
        print(Fore.GREEN + "\n✓ Есть новостной материал для выпуска")

        return

    # Сообщаем об отсутствии выпуска только тогда, когда
    # нет ни Balance Changes, ни пригодного русского preview.
    print(Fore.YELLOW + "\nНовых материалов нет.")
    print(Fore.YELLOW + "Пост сегодня не требуется.")


# ---------------------------------------------------------
# НОРМАЛИЗАЦИЯ ЗНАЧЕНИЙ
# ---------------------------------------------------------


def normalize_values(text):
    """
    Приводит технические значения Supercell
    к более привычному русскому виду.

    Примеры:

    4s   -> 4 сек.
    0.5s -> 0,5 сек.
    1.5s -> 1,5 сек.

    Используем регулярное выражение,
    поэтому не нужно вручную перечислять
    1s, 2s, 3s, 4s и т.д.
    """

    def replace_seconds(match):
        # Получаем само число без буквы s.
        value = match.group(1)

        # Для русского оформления заменяем точку на запятую.
        value = value.replace(".", ",")

        return f"{value} сек."

    # Ищем число, после которого сразу стоит s.
    # Например: 5s, 0.5s, 12s.
    return re.sub(
        r"(\d+(?:\.\d+)?)s\b",
        replace_seconds,
        text,
    )


# ---------------------------------------------------------
# ПЕРЕВОД ИЗМЕНЕНИЙ
# ---------------------------------------------------------


def translate_change(change_text):
    """
    Переводит типовые формулировки Supercell
    в короткий русский текст.

    Сначала идут более конкретные правила,
    затем более общие.

    Это важно, чтобы одно широкое правило
    случайно не перехватило другой тип изменения.
    """

    # -----------------------------------------------------
    # ОСНОВНАЯ АТАКА
    # -----------------------------------------------------

    if "Main attack damage reduced from" in change_text:
        values = change_text.replace(
            "Main attack damage reduced from",
            "",
        ).strip()

        return f"Урон основной атаки: {values}"

    if "Main attack damage increased from" in change_text:
        values = change_text.replace(
            "Main attack damage increased from",
            "",
        ).strip()

        return f"Урон основной атаки: {values}"

    if "Main attack projectile speed increased from" in change_text:
        values = change_text.replace(
            "Main attack projectile speed increased from",
            "",
        ).strip()

        return f"Скорость снаряда основной атаки: {values}"

    # -----------------------------------------------------
    # ЗДОРОВЬЕ
    # -----------------------------------------------------

    if "Health increased from" in change_text:
        values = change_text.replace(
            "Health increased from",
            "",
        ).strip()

        return f"Здоровье: {values}"

    if "Health reduced from" in change_text:
        values = change_text.replace(
            "Health reduced from",
            "",
        ).strip()

        return f"Здоровье: {values}"

    # -----------------------------------------------------
    # GADGET / STAR POWER
    # -----------------------------------------------------

    if "bouncing projectile damage reduced from" in change_text:
        values = change_text.split(
            "bouncing projectile damage reduced from",
            1,
        )[1].strip()

        return f"Урон от отскакивающего снаряда гаджета: {values}"

    if "ammo spawn time increased from" in change_text:
        values = change_text.split(
            "ammo spawn time increased from",
            1,
        )[1].strip()

        return f"Время появления боеприпаса: {values}"

    if "Gadget knockback removed" in change_text:
        return "Гаджет больше не отбрасывает противников"

    if "Gadget Super charge duration increased from" in change_text:
        values = change_text.split(
            "Gadget Super charge duration increased from",
            1,
        )[1].strip()

        return f"Время зарядки Super гаджетом: {values}"

    if "Gadget extra duration reduced from" in change_text:
        values = change_text.split(
            "Gadget extra duration reduced from",
            1,
        )[1].strip()

        return f"Дополнительная длительность гаджета: {values}"

    if "duration of charm reduced from" in change_text:
        values = change_text.split(
            "duration of charm reduced from",
            1,
        )[1].strip()

        return f"Длительность очарования: {values}"

    # -----------------------------------------------------
    # BROCK / ДОПОЛНИТЕЛЬНАЯ ДАЛЬНОСТЬ
    # -----------------------------------------------------

    if "time for extra range increased from" in change_text:
        values = change_text.split(
            "time for extra range increased from",
            1,
        )[1].strip()

        return "Время до получения дополнительной дальности: " f"{values}"

    # -----------------------------------------------------
    # HYPERCHARGE
    # -----------------------------------------------------

    if "Hypercharge rate reduced by" in change_text:
        value = change_text.split(
            "Hypercharge rate reduced by",
            1,
        )[1].strip()

        return f"Скорость зарядки Hypercharge снижена на {value}"

    if "Hypercharge rate increased by" in change_text:
        value = change_text.split(
            "Hypercharge rate increased by",
            1,
        )[1].strip()

        return f"Скорость зарядки Hypercharge увеличена на {value}"

    if "Hypercharge main attack Super charge rate reduced from" in change_text:
        values = change_text.split(
            "Hypercharge main attack Super charge rate reduced from",
            1,
        )[1].strip()

        return "Зарядка Super основной атакой " f"во время Hypercharge: {values}"

    if "Hypercharge main attack Super charge rate reduced by" in change_text:
        value = change_text.split(
            "Hypercharge main attack Super charge rate reduced by",
            1,
        )[1].strip()

        return (
            "Зарядка Super основной атакой " f"во время Hypercharge снижена на {value}"
        )

    if "Hypercharge main attack's second shot damage was reduced from" in change_text:
        values = change_text.split(
            "Hypercharge main attack's second shot damage was reduced from",
            1,
        )[1].strip()

        return "Урон второго выстрела основной атаки " f"в Hypercharge: {values}"

    if "Hypercharge projectile damage reduced from" in change_text:
        values = change_text.split(
            "Hypercharge projectile damage reduced from",
            1,
        )[1].strip()

        return f"Урон снаряда Hypercharge: {values}"

    # -----------------------------------------------------
    # SUPER
    # -----------------------------------------------------

    if "Mecha's main attack Super charge rate reduced by" in change_text:
        value = change_text.split(
            "Mecha's main attack Super charge rate reduced by",
            1,
        )[1].strip()

        return "Зарядка Super основной атакой мехи " f"снижена на {value}"

    if "Super charge rate increased by" in change_text:
        value = change_text.split(
            "Super charge rate increased by",
            1,
        )[1].strip()

        # У Supercell после изменения иногда идёт длинная Note.
        # Для короткого поста она не нужна.
        value = value.split(
            "Note:",
            1,
        )[0].strip()

        return f"Скорость зарядки Super увеличена на {value}"

    # -----------------------------------------------------
    # COOLDOWN
    # -----------------------------------------------------

    if "cooldown increased from" in change_text:
        values = change_text.split(
            "cooldown increased from",
            1,
        )[1].strip()

        return f"Перезарядка способности: {values}"

    if "cooldown reduced from" in change_text:
        values = change_text.split(
            "cooldown reduced from",
            1,
        )[1].strip()

        return f"Перезарядка способности: {values}"

    # -----------------------------------------------------
    # ДАЛЬНОСТЬ
    # -----------------------------------------------------

    # Общие правила держим почти в конце,
    # чтобы они не перехватывали специфичные случаи.
    if "range reduced from" in change_text:
        values = change_text.split(
            "range reduced from",
            1,
        )[1].strip()

        return f"Дальность: {values}"

    if "range increased from" in change_text:
        values = change_text.split(
            "range increased from",
            1,
        )[1].strip()

        return f"Дальность: {values}"

    # -----------------------------------------------------
    # НЕИЗВЕСТНАЯ ФОРМУЛИРОВКА
    # -----------------------------------------------------

    # Если новое правило ещё не написано,
    # оставляем оригинальный текст.
    #
    # Это лучше, чем потерять информацию
    # или неправильно её перевести.
    return change_text


# ---------------------------------------------------------
# ФОРМИРОВАНИЕ ОДНОГО БОЙЦА
# ---------------------------------------------------------


def format_brawler_change(item, symbol):
    """
    Формирует текст одного бойца для Telegram-поста.

    Например:

    🔻 CROW
    • Урон основной атаки: 420 ➡️ 380
    """

    lines = []

    # Имя бойца выводим отдельной строкой.
    lines.append(f"{symbol} {item['brawler']}")

    # У одного бойца может быть несколько изменений.
    for change in item["changes"]:

        # Сначала переводим техническую формулировку.
        translated_change = translate_change(change)

        # Потом приводим секунды и дробные числа
        # к более привычному русскому виду.
        translated_change = normalize_values(translated_change)

        # Добавляем готовую строку в пост.
        lines.append(f"• {translated_change}")

    return "\n".join(lines)


def print_colored_post(post):
    """
    Красиво выводит готовый пост в терминале.

    Важно:
    Colorama раскрашивает только терминал.
    В сам Telegram эти цвета не попадут.
    """

    for line in post.splitlines():

        # Заголовок Brawl Stars.
        if line.startswith("💥 BRAWL STARS"):
            print(Fore.MAGENTA + Style.BRIGHT + line)

        # Основной заголовок выпуска.
        elif line.startswith("⚖️"):
            print(Fore.CYAN + Style.BRIGHT + line)

        # Заголовок раздела баффов.
        elif line.startswith("📈"):
            print(Fore.GREEN + Style.BRIGHT + line)

        # Заголовок раздела нерфов.
        elif line.startswith("📉"):
            print(Fore.RED + Style.BRIGHT + line)

        # Имя бойца с баффом.
        elif line.startswith("🔺"):
            print(Fore.GREEN + Style.BRIGHT + line)

        # Имя бойца с нерфом.
        elif line.startswith("🔻"):
            print(Fore.RED + Style.BRIGHT + line)

        # Информация о скрытых изменениях.
        elif line.startswith("👀"):
            print(Fore.YELLOW + Style.BRIGHT + line)

        # Подвал Roblox Hub.
        elif line.startswith("⭐"):
            print(Fore.BLUE + line)

        # Обычный текст изменений.
        elif line.startswith("•"):
            print(Fore.WHITE + line)

        # Пустые и прочие строки.
        else:
            print(line)


# ---------------------------------------------------------
# ФОРМИРОВАНИЕ ПОЛНОГО ПОСТА
# ---------------------------------------------------------
def score_change(item):
    """
    Оценивает важность изменений одного бойца.

    Чем больше итоговый score,
    тем выше боец попадёт в выпуск.

    Пока используем простую понятную систему:
    - больше изменений = выше приоритет;
    - Hypercharge и Super считаем важнее;
    - урон и здоровье тоже повышают приоритет.
    """

    score = 0

    # Каждый отдельный пункт уже даёт вес.
    score += len(item["changes"]) * 2

    # Собираем весь текст изменений в одну строку,
    # чтобы искать ключевые слова.
    full_text = " ".join(item["changes"]).lower()

    # Изменения Hypercharge обычно заметны игрокам.
    if "hypercharge" in full_text:
        score += 4

    # Изменения Super тоже считаем важными.
    if "super" in full_text:
        score += 3

    # Урон напрямую влияет на силу бойца.
    if "damage" in full_text:
        score += 3

    # Здоровье тоже является важной базовой характеристикой.
    if "health" in full_text:
        score += 3

    # Изменение дальности заметно влияет на геймплей.
    if "range" in full_text:
        score += 2

    # Gadget и Star Power чуть менее важны,
    # но всё равно добавляем им вес.
    if "gadget" in full_text:
        score += 1

    if "star power" in full_text:
        score += 1

    return score


def print_debug_scores(buffs, nerfs):
    """
    Показывает рейтинг важности изменений.

    Этот вывод нужен только для настройки алгоритма.
    В Telegram он никогда не попадёт.
    """

    if not DEBUG:
        return

    print_section("DEBUG: CHANGE SCORES")

    # Сортируем баффы по score, от большего к меньшему.
    sorted_buffs = sorted(
        buffs,
        key=score_change,
        reverse=True,
    )

    # Сортируем нерфы по тому же принципу.
    sorted_nerfs = sorted(
        nerfs,
        key=score_change,
        reverse=True,
    )

    if sorted_buffs:
        print(Fore.GREEN + Style.BRIGHT + "\n📈 BUFF SCORES")

        for item in sorted_buffs:
            score = score_change(item)

            print(
                Fore.GREEN
                + f"{item['brawler']}: "
                + Fore.YELLOW
                + Style.BRIGHT
                + str(score)
            )

    if sorted_nerfs:
        print(Fore.RED + Style.BRIGHT + "\n📉 NERF SCORES")

        for item in sorted_nerfs:
            score = score_change(item)

            print(
                Fore.RED
                + f"{item['brawler']}: "
                + Fore.YELLOW
                + Style.BRIGHT
                + str(score)
            )


def build_post(data):
    """
    Собирает полный текст будущего Telegram-поста
    из свежих баффов и нерфов.
    """

    # Получаем все свежие изменения от монитора.
    all_buffs = data.get(
        "new_buffs",
        [],
    )

    all_nerfs = data.get(
        "new_nerfs",
        [],
    )

    # Для короткого выпуска ограничиваем количество бойцов.
    # Полные данные при этом остаются в JSON.
    # Сортируем бойцов по важности.
    # reverse=True означает: сначала самый высокий score.
    sorted_buffs = sorted(
        all_buffs,
        key=score_change,
        reverse=True,
    )
    sorted_nerfs = sorted(
        all_nerfs,
        key=score_change,
        reverse=True,
    )

    # В короткий выпуск берём только самых заметных.
    new_buffs = sorted_buffs[:3]
    new_nerfs = sorted_nerfs[:4]
    # Считаем, сколько изменений не вошло
    # в короткую версию поста.
    hidden_buffs = max(
        0,
        len(all_buffs) - len(new_buffs),
    )

    hidden_nerfs = max(
        0,
        len(all_nerfs) - len(new_nerfs),
    )

    # Если монитор ничего нового не нашёл,
    # публикация не нужна.
    if not new_buffs and not new_nerfs:
        return None

    post_parts = []

    # -----------------------------------------------------
    # ЗАГОЛОВОК
    # -----------------------------------------------------

    post_parts.append("💥 BRAWL STARS | ROBLOX HUB")

    post_parts.append("")

    post_parts.append("⚖️ ИЗМЕНЕНИЯ БАЛАНСА")

    # -----------------------------------------------------
    # БАФФЫ
    # -----------------------------------------------------

    if new_buffs:
        post_parts.append("")
        post_parts.append("📈 БАФФЫ")

        for buff in new_buffs:
            post_parts.append("")

            post_parts.append(
                format_brawler_change(
                    buff,
                    "🔺",
                )
            )

    # -----------------------------------------------------
    # НЕРФЫ
    # -----------------------------------------------------

    if new_nerfs:
        post_parts.append("")
        post_parts.append("📉 НЕРФЫ")

        for nerf in new_nerfs:
            post_parts.append("")

            post_parts.append(
                format_brawler_change(
                    nerf,
                    "🔻",
                )
            )

    # -----------------------------------------------------
    # НЕ ПОМЕСТИВШИЕСЯ ИЗМЕНЕНИЯ
    # -----------------------------------------------------

    hidden_total = hidden_buffs + hidden_nerfs

    if hidden_total > 0:
        post_parts.append("")

        post_parts.append(f"👀 Ещё изменений в обновлении: {hidden_total}")

    # -----------------------------------------------------
    # ПОДВАЛ ПОСТА
    # -----------------------------------------------------

    post_parts.append("")

    post_parts.append("⭐ Roblox Hub следит за изменениями Brawl Stars")

    # Склеиваем все части через перенос строки.
    return "\n".join(post_parts)


# ---------------------------------------------------------
# ФОРМИРОВАНИЕ ФИНАЛЬНОГО TELEGRAM-ПОСТА
# ---------------------------------------------------------


def normalize_news_title(title: str) -> str:
    """
    Безопасно приводит полностью прописной заголовок
    к более спокойному Telegram-регистру.

    Заголовки со смешанным регистром уже содержат решение
    редактора Supercell, поэтому возвращаем их без изменений.
    Для полностью прописного текста дополнительно проверяем
    латинские слова: неизвестную аббревиатуру лучше сохранить,
    чем случайно испортить её автоматическим преобразованием.
    """

    if not title:
        return title

    letters = [character for character in title if character.isalpha()]

    # Если в заголовке уже есть строчная буква, официальный
    # смешанный регистр считаем более надёжным вариантом.
    if not letters or any(character.islower() for character in letters):
        return title

    latin_words = set(re.findall(r"[A-Z][A-Z0-9-]*", title))

    if latin_words - NEWS_TITLE_SAFE_LATIN_WORDS:
        return title

    normalized_title = title.lower()

    # Поднимаем только первую буквенную позицию, не предполагая,
    # что заголовок обязательно начинается с буквы или цифры.
    for index, character in enumerate(normalized_title):
        if character.isalpha():
            normalized_title = (
                normalized_title[:index]
                + character.upper()
                + normalized_title[index + 1 :]
            )
            break

    # Возвращаем точное написание известных имён после общей
    # нормализации. Замена ограничена границами слова и потому
    # не меняет похожие части внутри других названий.
    for source, replacement in NEWS_TITLE_CASE_EXCEPTIONS:
        normalized_title = re.sub(
            rf"(?<!\w){re.escape(source)}(?!\w)",
            replacement,
            normalized_title,
            flags=re.IGNORECASE,
        )

    return normalized_title


def build_news_section(article: dict, max_blocks: int = NEWS_MAX_BLOCKS) -> str | None:
    """
    Собирает новостную секцию только из официального RU-текста.

    Функция повторно использует select_news_content(), поэтому
    в финальный пост действуют те же фильтры служебных строк,
    подзаголовков и лимита официального текста. Содержимое
    блоков не пересказывается и не обрезается.
    """

    if not article.get("ru_found") or max_blocks <= 0:
        return None

    ru_title = article.get("ru_title")

    if not isinstance(ru_title, str) or not ru_title.strip():
        return None

    selected_blocks = select_news_content(article)[:max_blocks]

    if not selected_blocks:
        return None

    section_parts = [
        "🔥 ГЛАВНОЕ",
        normalize_news_title(ru_title.strip()),
        *selected_blocks,
        "Источник: Supercell",
    ]

    return "\n\n".join(section_parts)


def select_final_news(
    high_priority_articles: list[dict],
    medium_priority_articles: list[dict],
) -> dict | None:
    """
    Выбирает одну статью для финального выпуска.

    Сначала просматриваем HIGH в архивном порядке, затем
    MEDIUM. Статья считается пригодной только если для неё
    действительно строится русская секция. LOW игнорируется,
    даже если повреждённый JSON поместил её не в тот список.
    """

    priority_groups = (
        ("high", high_priority_articles),
        ("medium", medium_priority_articles),
    )

    for expected_priority, articles in priority_groups:
        for article in articles:
            if article.get("priority") != expected_priority:
                continue

            if build_news_section(article) is not None:
                return article

    return None


def select_balance_changes(
    data: dict,
    max_changes: int | None = None,
) -> tuple[list[dict], list[dict], int]:
    """
    Отбирает наиболее важные изменения для общей секции.

    Первичный отбор полностью сохраняет текущие правила:
    максимум три buff, четыре nerf и сортировка score_change().
    Если общий пост не помещается, max_changes постепенно
    уменьшается. Тогда удаляются целые бойцы с минимальным
    score, а более важные изменения остаются в выпуске.
    """

    all_buffs = data.get("new_buffs", [])
    all_nerfs = data.get("new_nerfs", [])

    selected_buffs = sorted(
        all_buffs,
        key=score_change,
        reverse=True,
    )[:FINAL_BALANCE_MAX_BUFFS]
    selected_nerfs = sorted(
        all_nerfs,
        key=score_change,
        reverse=True,
    )[:FINAL_BALANCE_MAX_NERFS]

    selected_total = len(selected_buffs) + len(selected_nerfs)

    if max_changes is not None and selected_total > max_changes:
        # В ключе храним тип и позицию, а не сам словарь:
        # словари нельзя безопасно помещать в set.
        ranked_changes = []

        for index, item in enumerate(selected_buffs):
            ranked_changes.append((score_change(item), "buff", index))

        for index, item in enumerate(selected_nerfs):
            ranked_changes.append((score_change(item), "nerf", index))

        ranked_changes.sort(
            key=lambda ranked_item: ranked_item[0],
            reverse=True,
        )
        retained_keys = {
            (change_type, index)
            for _, change_type, index in ranked_changes[:max_changes]
        }

        selected_buffs = [
            item
            for index, item in enumerate(selected_buffs)
            if ("buff", index) in retained_keys
        ]
        selected_nerfs = [
            item
            for index, item in enumerate(selected_nerfs)
            if ("nerf", index) in retained_keys
        ]

    hidden_total = (
        len(all_buffs) + len(all_nerfs) - len(selected_buffs) - len(selected_nerfs)
    )

    return selected_buffs, selected_nerfs, hidden_total


def build_balance_section(
    data: dict,
    max_changes: int | None = None,
    heading: str = "⚖️ БАЛАНС",
) -> str | None:
    """
    Формирует компактную balance-секцию общего выпуска.

    Перевод и форматирование каждого бойца выполняют прежние
    normalize_values(), translate_change() и
    format_brawler_change(). Пустые BUFF/NERF-разделы никогда
    не добавляются.
    """

    selected_buffs, selected_nerfs, hidden_total = select_balance_changes(
        data,
        max_changes=max_changes,
    )

    if not selected_buffs and not selected_nerfs:
        return None

    section_parts = [heading]

    if selected_buffs:
        section_parts.append("📈 БАФФЫ")

        for buff in selected_buffs:
            section_parts.append(format_brawler_change(buff, "🔺"))

    if selected_nerfs:
        section_parts.append("📉 НЕРФЫ")

        for nerf in selected_nerfs:
            section_parts.append(format_brawler_change(nerf, "🔻"))

    if hidden_total > 0:
        section_parts.append(f"👀 Ещё изменений в обновлении: {hidden_total}")

    return "\n\n".join(section_parts)


def build_final_post(data: dict) -> str | None:
    """
    Собирает короткий готовый Brawl Stars пост для Telegram.

    Поддерживаются news + balance, только news и только
    balance. При превышении лимита сначала убирается второй
    официальный новостной блок, затем по одному исключаются
    наименее важные изменения баланса. Срез строки никогда
    не используется: каждый факт остаётся целым.
    """

    high_priority_articles, medium_priority_articles = get_news_candidates(data)
    news_article = select_final_news(
        high_priority_articles,
        medium_priority_articles,
    )

    if news_article is None:
        news_block_count = 0
    else:
        news_block_count = min(
            NEWS_MAX_BLOCKS,
            len(select_news_content(news_article)),
        )

    selected_buffs, selected_nerfs, _ = select_balance_changes(data)
    balance_change_count = len(selected_buffs) + len(selected_nerfs)

    while True:
        if news_article is None:
            news_section = None
        else:
            news_section = build_news_section(
                news_article,
                max_blocks=news_block_count,
            )

        if news_section is None:
            balance_heading = "⚖️ ИЗМЕНЕНИЯ БАЛАНСА"
        else:
            balance_heading = "⚖️ БАЛАНС"

        balance_section = build_balance_section(
            data,
            max_changes=balance_change_count,
            heading=balance_heading,
        )

        if news_section is None and balance_section is None:
            return None

        post_parts = ["💥 BRAWL STARS | ROBLOX HUB"]

        if news_section is not None:
            post_parts.append(news_section)

        if balance_section is not None:
            post_parts.append(balance_section)

        post_parts.append("🎮 Roblox Hub")
        final_post = "\n\n".join(post_parts)

        if len(final_post) <= FINAL_POST_MAX_CHARS:
            return final_post

        # Первый шаг сокращения — оставить у новости только
        # один официальный содержательный блок целиком.
        if news_block_count > 1:
            news_block_count = 1
            continue

        # Затем убираем по одному наименее важному бойцу.
        # Повторная сортировка сохраняет кандидатов с высоким
        # score независимо от того, buff это или nerf.
        if balance_change_count > 0:
            balance_change_count -= 1
            continue

        # Теоретически один официальный блок или заголовок
        # тоже может быть длиннее редакционного лимита. Его
        # нельзя резать или переписывать, поэтому безопаснее
        # не создавать пост, чем публиковать обрывок.
        return None


# ---------------------------------------------------------
# 1. ЗАГРУЖАЕМ ДАННЫЕ
# ---------------------------------------------------------

print_section("BRAWL POST GENERATOR")

data = load_latest_changes()

if data is None:
    print(Fore.RED + Style.BRIGHT + "✗ Файл свежих изменений не найден")

    print("Сначала запусти brawl_monitor.py")

    raise SystemExit


print(Fore.GREEN + f"✓ Загружен файл {LATEST_CHANGES_FILE}")


# ---------------------------------------------------------
# 2. ПОКАЗЫВАЕМ ПОЛУЧЕННЫЕ ДАННЫЕ
# ---------------------------------------------------------

new_buffs = data.get(
    "new_buffs",
    [],
)

new_nerfs = data.get(
    "new_nerfs",
    [],
)

high_priority_articles, medium_priority_articles = get_news_candidates(data)

print(f"Новых баффов: {len(new_buffs)}")

print(f"Новых нерфов: {len(new_nerfs)}")

# Отдельно показываем подготовленные статьи-кандидаты.
# Этот debug-блок не является частью Telegram-поста.
print_news_candidates(
    high_priority_articles,
    medium_priority_articles,
)

# Русские тексты показываем отдельным preview-разделом.
# В готовый Telegram-пост эти блоки пока не добавляются.
russian_news_previews = print_russian_news_previews(
    high_priority_articles,
    medium_priority_articles,
)

# В debug-режиме показываем,
# какие бойцы получили самый высокий приоритет.
print_debug_scores(
    new_buffs,
    new_nerfs,
)

# ---------------------------------------------------------
# 3. СОБИРАЕМ ПОСТ
# ---------------------------------------------------------

post = build_post(data)


# ---------------------------------------------------------
# 4. ВЫВОДИМ РЕЗУЛЬТАТ
# ---------------------------------------------------------

print_generation_result(
    post,
    russian_news_previews,
)


# ---------------------------------------------------------
# 5. ПОКАЗЫВАЕМ ФИНАЛЬНЫЙ TELEGRAM-ПОСТ
# ---------------------------------------------------------

# Этот блок пока служит только редакторским предпросмотром.
# Генератор не записывает результат в posts.json, не меняет
# state монитора и ничего автоматически не публикует.
final_post = build_final_post(data)

print_section("FINAL TELEGRAM POST")

if final_post is None:
    print(Fore.YELLOW + "\nПост не создан: подходящих новых материалов нет.")
else:
    print("\n" + final_post)
