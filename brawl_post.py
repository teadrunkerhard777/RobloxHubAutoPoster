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

    # MEDIUM выводим отдельно как запасные новости.
    for article in medium_priority_articles:
        print(Fore.YELLOW + Style.BRIGHT + "\n🟡 MEDIUM")
        print(Fore.WHITE + Style.BRIGHT + article["title"])
        print(f"Категория: {article['category']}")
        print(f"Score: {article['score']}")

    # Если основных кандидатов нет, явно подсказываем,
    # что редактор может использовать запасной материал.
    if not high_priority_articles and medium_priority_articles:
        print(
            Fore.YELLOW
            + "\nВысокоприоритетных новостей нет, "
            + "можно использовать MEDIUM."
        )


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

if post is None:
    print(Fore.YELLOW + "\nНовых изменений нет.")

    print(Fore.YELLOW + "Пост сегодня не требуется.")

else:
    print_section("ГОТОВЫЙ ПОСТ")

    # Выводим предпросмотр поста
    # с цветами для удобства чтения в терминале.
    print_colored_post(post)
