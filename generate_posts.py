import json
import os
import random
from datetime import datetime, timedelta, timezone

from image_library import select_daily_image
from tips_rotation import build_tips_post, choose_tips

LOCAL_TIMEZONE = timezone(timedelta(hours=5))

# Картинки публикуются четыре раза в день.
# Один генератор обслуживает все слоты без отдельных скриптов.
IMAGE_POST_HOURS = (11, 14, 17, 21)
IMAGE_DIRECTORY = "images/16-00"
IMAGE_HISTORY_FILE = "image_history.json"

# Текстовые слоты храним рядом с image-расписанием,
# чтобы генератор и тесты использовали единый источник времени.
ROBLOX_NEWS_HOUR = 10
BRAWL_POST_HOUR = 12
TIPS_POST_HOUR = 15
MYTH_POST_HOUR = 19

# Утренний fallback старается показать три разные игры,
# но два проверенных совета уже считаются достаточным
# содержательным выпуском для обязательного слота 10:00.
MORNING_FALLBACK_MAX_TIPS = 3
MORNING_FALLBACK_MIN_TIPS = 2

# Brawl monitor сохраняет сюда подготовленные данные.
# generate_posts.py только читает файл и не меняет state.
BRAWL_LATEST_CHANGES_FILE = "data/brawl_latest_changes.json"
BRAWL_SKIP_ENVIRONMENT_VARIABLE = "ROBLOX_HUB_SKIP_BRAWL"

# Локальная база содержит только заранее проверенные evergreen-советы.
# Историю храним отдельно: статический справочник не меняется во время
# генерации, а служебное состояние легко сохранить между запусками.
BRAWL_TIPS_FILE = "brawl_tips.json"
BRAWL_TIP_HISTORY_FILE = "brawl_tip_history.json"
BRAWL_TIP_HISTORY_LIMIT = 7

# Telegram принимает у photo post более короткую подпись, чем
# у обычного text post. Оба новостных слота заранее приводим
# к безопасному лимиту, не разрезая слово посередине.
TELEGRAM_CAPTION_MAX_CHARS = 1024
ROBLOX_NEWS_HEADER_PATH = "assets/news_headers/roblox_news_header.png"
BRAWL_NEWS_HEADER_PATH = "assets/news_headers/brawl_news_header.png"

MYTH_HISTORY_LIMIT = 3
GAME_HISTORY_LIMIT = 5
TIPS_RELEASE_HISTORY_LIMIT = 3
TIPS_GAME_HISTORY_FILE = "tips_game_history.json"
TIPS_CATEGORY_HISTORY_FILE = "tips_category_history.json"


GAME_EMOJIS = {
    "Blox Fruits": "🍈",
    "RIVALS": "🔫",
    "99 Nights in the Forest": "🌲",
    "Steal a Brainrot": "🧠",
    "Brookhaven": "🏡",
    "Adopt Me!": "🐾",
    "Grow a Garden": "🌱",
    "Dress To Impress": "👗",
    "Pet Simulator 99": "🐶",
    "Blade Ball": "⚔️",
}


# --------------------------------------------------
# Базовые функции
# --------------------------------------------------


def build_post(post_id, publish_at, game, rubric, text, source, image_path=None):
    post = {
        "id": post_id,
        "publish_at": publish_at.isoformat(),
        "game": game,
        "rubric": rubric,
        "source": source,
        "text": text,
        "status": "pending",
        "published_at": None,
        "attempts": 0,
        "last_error": None,
    }

    if image_path is not None:
        post["image_path"] = image_path

    return post


def load_json(filename, default=None):
    try:
        with open(filename, "r", encoding="utf-8") as file:
            return json.load(file)

    except FileNotFoundError:
        if default is not None:
            return default

        raise


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def fit_telegram_caption(text, max_chars=TELEGRAM_CAPTION_MAX_CHARS):
    """
    Укладывает готовый редакционный текст в лимит photo caption.

    Сначала убираем последние дополнительные блоки, сохраняя
    первый смысловой блок и footer. Если один блок всё равно
    слишком длинный, сокращаем его по последнему целому слову.
    Исходные формулировки не переписываются и новые факты не
    добавляются.
    """

    normalized_text = text.strip()

    if len(normalized_text) <= max_chars:
        return normalized_text

    blocks = [block.strip() for block in normalized_text.split("\n\n") if block.strip()]

    if len(blocks) == 1:
        shortened = blocks[0][: max_chars - 1].rsplit(maxsplit=1)[0].rstrip()
        return f"{shortened}…"

    footer = blocks[-1]
    content_blocks = blocks[:-1]

    while len(content_blocks) > 1:
        candidate = "\n\n".join([*content_blocks, footer])

        if len(candidate) <= max_chars:
            return candidate

        content_blocks.pop()

    footer_suffix = f"\n\n{footer}"
    available_chars = max_chars - len(footer_suffix) - 1
    shortened = content_blocks[0][:available_chars].rsplit(maxsplit=1)[0].rstrip()

    return f"{shortened}…{footer_suffix}"


def resolve_news_header(header_path, path_checker=None):
    """
    Возвращает путь только к реально существующей шапке.

    Отсутствующий ассет не должен останавливать всю дневную
    очередь. В этом редком случае генератор создаёт прежний
    text-only пост и оставляет понятную запись в терминале.
    """

    if path_checker is None:
        path_checker = os.path.isfile

    if path_checker(header_path):
        return header_path

    print("Шапка не найдена, создан пост без изображения.")
    return None


def load_brawl_latest_changes():
    """Загружает последний подготовленный monitor JSON для Brawl."""

    return load_json(BRAWL_LATEST_CHANGES_FILE)


def load_brawl_tips():
    """Загружает локальную базу проверенных Brawl Stars советов."""

    return load_json(BRAWL_TIPS_FILE)


def load_brawl_tip_history():
    """Загружает историю fallback без ошибки при первом запуске."""

    return load_json(BRAWL_TIP_HISTORY_FILE, [])


def save_brawl_tip_history(history):
    """Сохраняет только короткое окно последних использованных ID."""

    save_json(BRAWL_TIP_HISTORY_FILE, history)


def remember_game(game):
    history = load_json("game_history.json", [])

    history.append(game)

    save_json("game_history.json", history[-GAME_HISTORY_LIMIT:])


def find_post(posts, post_id):
    for post in posts:
        if str(post["id"]) == post_id:
            return post

    return None


def schedule_image_posts(
    existing_posts,
    target_date,
    image_selector=None,
):
    """
    Добавляет недостающие image-посты на 11:00, 14:00,
    17:00 и 21:00.

    У каждого слота собственный стабильный ID. Поэтому повторный
    запуск генератора на ту же дату не создаёт вторую запись и
    не выбирает новую картинку для уже подготовленного времени.

    image_selector можно заменить в тестах. В обычном запуске
    используется существующая библиотека select_daily_image().
    """

    if image_selector is None:
        image_selector = select_daily_image

    posts_added = 0

    # Уже запланированные на эту дату изображения исключаем
    # из последующих выборок. Если уникальных файлов не хватает,
    # безопаснее оставить слот пустым, чем повторить картинку.
    scheduled_image_paths = {
        post.get("image_path")
        for post in existing_posts
        if post.get("source") == "image_library"
        and post.get("publish_at", "").startswith(target_date.isoformat())
        and post.get("image_path")
    }

    for publish_hour in IMAGE_POST_HOURS:
        post_id = f"{target_date}-image-{publish_hour}"
        existing_post = find_post(
            existing_posts,
            post_id,
        )

        if existing_post is not None:
            print(f"{publish_hour:02d}:00 — пост с картинкой уже существует.")
            continue

        image_path = image_selector(
            directory=IMAGE_DIRECTORY,
            history_filename=IMAGE_HISTORY_FILE,
            exclude_paths=scheduled_image_paths,
        )

        if image_path is None:
            print(
                f"{publish_hour:02d}:00 — уникальной картинки нет, " "пост не добавлен."
            )
            continue

        # Дополнительная защита на уровне очереди:
        # даже нестандартный selector не может вернуть
        # уже запланированную сегодня картинку повторно.
        if image_path in scheduled_image_paths:
            print(
                f"{publish_hour:02d}:00 — selector вернул повторную "
                "картинку, пост не добавлен."
            )
            continue

        existing_posts.append(
            build_post(
                post_id=post_id,
                publish_at=datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    publish_hour,
                    0,
                    tzinfo=LOCAL_TIMEZONE,
                ),
                game="Roblox",
                rubric="Картинка дня",
                source="image_library",
                text="",
                image_path=image_path,
            )
        )

        scheduled_image_paths.add(image_path)
        posts_added += 1

        print(f"{publish_hour:02d}:00 — картинка добавлена: {image_path}")

    return posts_added


def is_verified_brawl_tip(tip):
    """
    Проверяет минимальную структуру локального Brawl-совета.

    Fallback не должен случайно публиковать произвольные данные
    из повреждённого или подменённого JSON. Поэтому принимаем
    только явно помеченные статические записи для Brawl Stars.
    """

    return (
        isinstance(tip, dict)
        and isinstance(tip.get("id"), str)
        and bool(tip["id"].strip())
        and tip.get("game") == "Brawl Stars"
        and isinstance(tip.get("topic"), str)
        and bool(tip["topic"].strip())
        and isinstance(tip.get("text"), str)
        and bool(tip["text"].strip())
        and tip.get("source") == "verified_static"
    )


def select_brawl_fallback_tip(tips, recent_tip_ids, rng=None):
    """
    Выбирает совет без повтора среди семи последних публикаций.

    Пока в базе есть неиспользованные недавно записи, выбираем
    только среди них. После полного цикла начинаем новое окно,
    но по возможности исключаем последний показанный совет —
    одинаковые публикации не идут две даты подряд.

    Возвращаем также готовую новую историю. Записывает её уже
    вызывающая функция и только после успешного выбора совета.
    """

    if rng is None:
        rng = random

    verified_tips = [tip for tip in tips if is_verified_brawl_tip(tip)]

    if not verified_tips:
        return None, []

    if not isinstance(recent_tip_ids, list):
        recent_tip_ids = []

    recent_tip_ids = [tip_id for tip_id in recent_tip_ids if isinstance(tip_id, str)][
        -BRAWL_TIP_HISTORY_LIMIT:
    ]
    recent_ids = set(recent_tip_ids)
    candidates = [tip for tip in verified_tips if tip["id"] not in recent_ids]
    starts_new_cycle = not candidates

    if starts_new_cycle:
        last_tip_id = recent_tip_ids[-1] if recent_tip_ids else None
        candidates = [tip for tip in verified_tips if tip["id"] != last_tip_id]

        # Для базы из одной записи немедленный повтор неизбежен,
        # но обязательный слот всё равно должен быть заполнен.
        if not candidates:
            candidates = verified_tips

    selected_tip = rng.choice(candidates)

    if starts_new_cycle:
        updated_history = [selected_tip["id"]]
    else:
        updated_history = (recent_tip_ids + [selected_tip["id"]])[
            -BRAWL_TIP_HISTORY_LIMIT:
        ]

    return selected_tip, updated_history


def build_brawl_fallback(tip=None):
    """
    Собирает короткий обязательный пост без выдуманных новостей.

    Обычный fallback дословно использует проверенный текст из
    локальной базы. Если база недоступна или повреждена, выдаём
    нейтральное сообщение без утверждений о событиях в игре.
    """

    if tip is not None and is_verified_brawl_tip(tip):
        return (
            "💥 BRAWL STARS | ROBLOX HUB\n\n"
            "🎯 СОВЕТ ДНЯ\n\n"
            f"{tip['text'].strip()}\n\n"
            "⭐ Roblox Hub"
        )

    return (
        "💥 BRAWL STARS | ROBLOX HUB\n\n"
        "🎮 Сегодня без свежих подтверждённых новостей.\n\n"
        "Следим за официальными обновлениями Brawl Stars и вернёмся "
        "с новым выпуском, когда появится проверенный материал. 👀\n\n"
        "⭐ Roblox Hub"
    )


def generate_brawl_fallback(
    tips_loader=None,
    history_loader=None,
    history_saver=None,
    rng=None,
):
    """
    Выбирает локальный совет и безопасно обновляет его историю.

    Ошибка базы или истории не должна оставлять ежедневный слот
    пустым. В таком случае используем аварийный нейтральный текст.
    Если состояние нельзя надёжно сохранить, совет не публикуем:
    иначе следующий запуск мог бы повторить его как новый.
    """

    if tips_loader is None:
        tips_loader = load_brawl_tips

    if history_loader is None:
        history_loader = load_brawl_tip_history

    if history_saver is None:
        history_saver = save_brawl_tip_history

    try:
        tips = tips_loader()

        if not isinstance(tips, list):
            raise TypeError("Brawl tips JSON должен содержать список")

        history = history_loader()
        selected_tip, updated_history = select_brawl_fallback_tip(
            tips,
            history,
            rng=rng,
        )

        if selected_tip is None:
            return build_brawl_fallback()

        history_saver(updated_history)
        return build_brawl_fallback(selected_tip)
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return build_brawl_fallback()


def schedule_brawl_post(
    existing_posts,
    target_date,
    data_loader=None,
    final_post_builder=None,
    fallback_builder=None,
    skip_fresh_material=False,
    header_checker=None,
):
    """
    Добавляет готовый Brawl Stars пост в слот 12:00.

    Сначала функция читает подготовленный monitor JSON и вызывает
    существующий build_final_post(). Если свежего материала нет,
    обязательный слот заполняется локальным проверенным fallback.
    Зависимости можно заменить в тестах без рабочих файлов.

    Проверка стабильного ID выполняется до выбора fallback-совета.
    Поэтому повторный запуск не создаёт дубль и не сдвигает ротацию.
    """

    post_id = f"{target_date}-brawl-{BRAWL_POST_HOUR}"
    existing_post = find_post(existing_posts, post_id)

    if existing_post is not None and existing_post.get("status") == "published":
        print("12:00 — Brawl Stars пост уже существует.")
        return 0

    if existing_post is not None:
        # Pending/failed Brawl-пост не пересобираем и не расходуем
        # следующий fallback-совет. Только безопасно переводим
        # существующую запись на photo-формат с тем же ID.
        existing_post["text"] = fit_telegram_caption(existing_post.get("text", ""))
        header_path = resolve_news_header(
            BRAWL_NEWS_HEADER_PATH,
            path_checker=header_checker,
        )

        if header_path is None:
            existing_post.pop("image_path", None)
        else:
            existing_post["image_path"] = header_path

        print("12:00 — Brawl Stars пост уже существует.")

        if header_path is not None:
            print("12:00 — создан Brawl news post с шапкой.")

        return 0

    # Старые версии генератора могли уже поставить другой
    # текстовый пост на 12:00 с прежним ID. Не удаляем и не
    # перезаписываем такую запись, чтобы сохранить очередь.
    for post in existing_posts:
        publish_at_value = post.get("publish_at")

        if not publish_at_value or post.get("image_path"):
            continue

        try:
            publish_at = datetime.fromisoformat(publish_at_value)
        except (TypeError, ValueError):
            continue

        local_publish_at = publish_at.astimezone(LOCAL_TIMEZONE)

        if (
            local_publish_at.date() == target_date
            and local_publish_at.hour == BRAWL_POST_HOUR
        ):
            print("12:00 — слот уже занят существующим текстовым постом.")
            return 0

    if fallback_builder is None:
        fallback_builder = generate_brawl_fallback

    if data_loader is None:
        data_loader = load_brawl_latest_changes

    if final_post_builder is None and not skip_fresh_material:
        # Импорт выполняем только при реальной сборке. Так тесты
        # расписания могут передать локальную функцию, а обычный
        # запуск использует единственный рабочий Brawl-генератор.
        from brawl_post import build_final_post

        final_post_builder = build_final_post

    final_text = None

    if not skip_fresh_material:
        try:
            brawl_data = data_loader()
            final_text = final_post_builder(brawl_data)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
            print(f"12:00 — Brawl pipeline недоступен: {error}")

    if final_text is not None:
        rubric = "Brawl Stars"
        source = "brawl_pipeline"
        status_message = "12:00 — создан Brawl Stars новостной выпуск."
    else:
        try:
            final_text = fallback_builder()
        except (OSError, ValueError, TypeError, KeyError, AttributeError):
            # Даже пользовательская тестовая зависимость или ошибка
            # записи истории не может отменить обязательный слот.
            final_text = build_brawl_fallback()

        rubric = "Brawl Stars: совет дня"
        source = "verified_brawl_fallback"
        status_message = (
            "12:00 — свежих Brawl Stars материалов нет; " "создан fallback-пост."
        )

    # И новостной выпуск, и локальный fallback используют одну
    # постоянную Brawl-шапку. Текст остаётся в поле text — app.py
    # уже передаёт его Telegram как caption для image_path.
    final_text = fit_telegram_caption(final_text)
    header_path = resolve_news_header(
        BRAWL_NEWS_HEADER_PATH,
        path_checker=header_checker,
    )

    existing_posts.append(
        build_post(
            post_id=post_id,
            publish_at=datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                BRAWL_POST_HOUR,
                0,
                tzinfo=LOCAL_TIMEZONE,
            ),
            game="Brawl Stars",
            rubric=rubric,
            source=source,
            text=final_text,
            image_path=header_path,
        )
    )

    print(status_message)

    if header_path is not None:
        print("12:00 — создан Brawl news post с шапкой.")

    return 1


# --------------------------------------------------
# Советы
# --------------------------------------------------


def select_tips(count, excluded_games=None):
    if excluded_games is None:
        excluded_games = set()

    tips = load_json("tips.json")

    release_history = load_json(TIPS_GAME_HISTORY_FILE, [])
    recent_games = [game for release in release_history for game in release]
    category_history = load_json(TIPS_CATEGORY_HISTORY_FILE, {})

    selected = choose_tips(
        tips=tips,
        count=count,
        recent_games=recent_games,
        category_history=category_history,
        excluded_games=excluded_games,
        rng=random,
    )

    save_json("tips.json", tips)

    selected_games = [tip["game"] for tip in selected]
    release_history.append(selected_games)
    save_json(TIPS_GAME_HISTORY_FILE, release_history[-TIPS_RELEASE_HISTORY_LIMIT:])

    for tip in selected:
        game_categories = category_history.setdefault(tip["game"], [])
        game_categories.append(tip["category"])
        category_history[tip["game"]] = game_categories[-3:]

    save_json(TIPS_CATEGORY_HISTORY_FILE, category_history)

    for tip in selected:
        remember_game(tip["game"])

    return selected


# --------------------------------------------------
# 10:00 — выпуск дня
# --------------------------------------------------
def build_news_action(item):
    text = item.get("text", "")

    upper = text.upper()

    if "CONTRACT" in upper:
        return "🎯 Что сделать: зайди в игру " "и проверь доступные контракты."

    if "SUMMER EVENT" in upper:
        return "🎯 Что сделать: загляни в Summer Event " "и проверь его активности."

    if "EVENT" in upper:
        return (
            "🎯 Что сделать: зайди в событие " "и посмотри доступные задания и награды."
        )

    if "REWARD" in upper or "НАГРАД" in upper:
        return "🎯 Что сделать: проверь условия " "получения новых наград."

    if "NEW ITEMS" in upper or "НОВЫЕ ПРЕДМЕТЫ" in upper:
        return "🎯 Что сделать: открой игру " "и посмотри новые предметы."

    if "ТРАНСПОРТ" in upper:
        return "🎯 Что сделать: найди новый транспорт " "и проверь его в игре."

    if "BOSS" in upper or "БОСС" in upper:
        return "🎯 Что сделать: подготовься " "и попробуй нового босса."

    if "MAP" in upper or "КАРТ" in upper:
        return "🎯 Что сделать: исследуй новую карту."

    return None


def generate_morning_post():
    news_data = load_json("generated_news_data_ru.json", {"items": []})

    news_items = news_data.get("items", [])

    # --------------------------------------------------
    # Нет достойных новостей
    # --------------------------------------------------

    if not news_items:
        return None

    blocks = ["🎮 ROBLOX HUB — СЕГОДНЯ"]

    # --------------------------------------------------
    # Новости
    # --------------------------------------------------

    for item in news_items:
        emoji = item.get("emoji", "🎮")

        game = item.get("game", "Roblox")

        text = item.get("text", "")

        block = f"{emoji} {game}\n\n" f"{text}"

        action = build_news_action(item)

        if action:
            block += f"\n\n{action}"

        blocks.append(block)

    # --------------------------------------------------
    # Главное
    #
    # Берём самую сильную новость,
    # а не пишем редакционную воду.
    # --------------------------------------------------

    blocks.append("🎮 Roblox Hub")

    return "\n\n".join(blocks)


def is_verified_fallback_tip(tip):
    """
    Проверяет, можно ли использовать локальный совет утром.

    Fallback допускает только записи с заполненными игрой и
    текстом, источник которых явно относится к проверенной
    базе проекта. Это не позволяет случайной или неполной
    записи из JSON попасть в обязательный выпуск.
    """

    if not isinstance(tip, dict):
        return False

    source = tip.get("source", "")

    return bool(
        tip.get("game")
        and tip.get("text")
        and isinstance(source, str)
        and source.startswith("verified_")
    )


def build_morning_fallback(selected_tips):
    """
    Формирует утренний пост из уже выбранных локальных советов.

    Текст каждого факта переносится без пересказа. Вступление
    прямо сообщает, что подтверждённых обновлений сегодня нет,
    поэтому советы нельзя принять за свежие новости.
    """

    if not isinstance(selected_tips, (list, tuple)):
        selected_tips = []

    verified_tips = []
    selected_games = set()

    # Даже если нестандартный selector вернул несколько советов
    # одной игры, утром показываем каждую игру только один раз.
    for tip in selected_tips:
        if not is_verified_fallback_tip(tip):
            continue

        if tip["game"] in selected_games:
            continue

        verified_tips.append(tip)
        selected_games.add(tip["game"])

        if len(verified_tips) == MORNING_FALLBACK_MAX_TIPS:
            break

    if len(verified_tips) < MORNING_FALLBACK_MIN_TIPS:
        return (
            "🎮 ROBLOX HUB — УТРО\n\n"
            "Сегодня без подтверждённых игровых новостей.\n\n"
            "Следим за обновлениями и вернёмся, "
            "когда будет что рассказать 👀\n\n"
            "🎮 Roblox Hub"
        )

    blocks = [
        "🎮 ROBLOX HUB — УТРО",
        ("Сегодня без крупных подтверждённых обновлений, " "поэтому держи полезное 👇"),
    ]

    for tip in verified_tips:
        emoji = GAME_EMOJIS.get(tip["game"], "🎮")
        blocks.append(f"{emoji} {tip['game']}\n{tip['text']}")

    blocks.append("🎮 Roblox Hub")

    return "\n\n".join(blocks)


def generate_morning_fallback(tip_selector=None):
    """
    Выбирает проверенные советы для обязательного слота 10:00.

    Используем существующую select_tips(), которая сохраняет
    used-флаги, историю игр и историю категорий. Если выбрать
    три разные игры невозможно, безопасно пробуем две. Ошибка
    локального JSON не отменяет слот: build_morning_fallback()
    создаст нейтральный выпуск без конкретных фактов.
    """

    if tip_selector is None:
        tip_selector = select_tips

    selected_tips = []

    for count in (
        MORNING_FALLBACK_MAX_TIPS,
        MORNING_FALLBACK_MIN_TIPS,
    ):
        try:
            selected_tips = tip_selector(count=count)
        except (OSError, ValueError, TypeError, KeyError, RuntimeError):
            continue

        break

    return build_morning_fallback(selected_tips)


def schedule_morning_post(
    existing_posts,
    target_date,
    news_text,
    fallback_builder=None,
    header_checker=None,
):
    """
    Создаёт или обновляет обязательный photo-слот 10:00.

    Свежий news-текст всегда имеет приоритет. Если его нет,
    используем только локальный fallback. Stable ID остаётся
    общим для обоих вариантов, поэтому повторный запуск не
    создаёт дубль, а published-запись никогда не меняется.

    Возвращаем отдельно количество добавленных и обновлённых
    записей, чтобы сохранить текущую итоговую статистику.
    """

    post_id = f"{target_date}-{ROBLOX_NEWS_HOUR}"
    existing_post = find_post(existing_posts, post_id)

    if existing_post is not None and existing_post.get("status") == "published":
        print("10:00 — пост уже опубликован, не изменяем.")
        return 0, 0

    if news_text is not None:
        final_text = news_text
        rubric = "Выпуск дня"
        source = "auto_verified"
        status_message = "10:00 — создан новостной выпуск."
    else:
        # Уже подготовленный fallback не пересобираем при каждом
        # повторном запуске: иначе ротация зря потратит новые
        # советы, хотя запись с тем же ID уже находится в очереди.
        if (
            existing_post is not None
            and existing_post.get("source") == "verified_fallback"
        ):
            # Старую pending/failed запись можно безопасно
            # перевести на новый photo-формат без повторного
            # выбора советов и изменения стабильного ID.
            final_text = fit_telegram_caption(existing_post.get("text", ""))
            header_path = resolve_news_header(
                ROBLOX_NEWS_HEADER_PATH,
                path_checker=header_checker,
            )
            changed = existing_post.get("text") != final_text
            existing_post["text"] = final_text

            if header_path is None:
                changed = existing_post.pop("image_path", None) is not None or changed
            else:
                changed = existing_post.get("image_path") != header_path or changed
                existing_post["image_path"] = header_path

            print("10:00 — полезный fallback-выпуск уже существует.")

            if header_path is not None:
                print("10:00 — создан Roblox news post с шапкой.")

            return 0, int(changed)

        if fallback_builder is None:
            fallback_builder = generate_morning_fallback

        final_text = fallback_builder()
        rubric = "Утренний выпуск"
        source = "verified_fallback"
        status_message = (
            "10:00 — свежих новостей нет; " "создан полезный fallback-выпуск."
        )

    # Утренний news и fallback получают одинаковую Roblox-шапку.
    # При отсутствии файла resolve_news_header() вернёт None,
    # и build_post() сохранит рабочую text-only запись.
    final_text = fit_telegram_caption(final_text)
    header_path = resolve_news_header(
        ROBLOX_NEWS_HEADER_PATH,
        path_checker=header_checker,
    )

    if existing_post is None:
        existing_posts.append(
            build_post(
                post_id=post_id,
                publish_at=datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    ROBLOX_NEWS_HOUR,
                    0,
                    tzinfo=LOCAL_TIMEZONE,
                ),
                game="разные игры",
                rubric=rubric,
                source=source,
                text=final_text,
                image_path=header_path,
            )
        )
        print(status_message)

        if header_path is not None:
            print("10:00 — создан Roblox news post с шапкой.")

        return 1, 0

    # Pending/failed запись обновляем на месте: ID, attempts,
    # published_at и остальные поля очереди не теряются.
    existing_post["text"] = final_text
    existing_post["rubric"] = rubric
    existing_post["source"] = source

    if header_path is None:
        existing_post.pop("image_path", None)
    else:
        existing_post["image_path"] = header_path

    print(status_message)

    if header_path is not None:
        print("10:00 — создан Roblox news post с шапкой.")

    return 0, 1


# --------------------------------------------------
# Архивный генератор бесплатных предложений
#
# Функцию сохраняем для совместимости и будущего использования,
# но в новом ежедневном расписании отдельного freebie-слота нет:
# 12:00 теперь зарезервировано за Brawl Stars.
# --------------------------------------------------


def generate_freebie_post():
    freebies = load_json("freebies.json", [])

    available = [
        item
        for item in freebies
        if item.get("verified") is True and item.get("used") is not True
    ]

    if not available:
        return None

    freebie = available[0]

    for item in freebies:
        if item["id"] == freebie["id"]:
            item["used"] = True
            break

    save_json("freebies.json", freebies)

    return {
        "game": freebie.get("game", "Roblox"),
        "text": freebie["text"],
        "source": freebie.get("source", "verified_freebie"),
    }


# --------------------------------------------------
# 15:00 — Полезно знать
# --------------------------------------------------


def generate_tips_post():
    selected_tips = select_tips(count=5)
    return build_tips_post(selected_tips, GAME_EMOJIS)


# --------------------------------------------------
# 19:00 — Миф или правда
# --------------------------------------------------


def generate_myth_post():
    myths = load_json("myths.json")

    myth_history = load_json("myth_history.json", [])

    game_history = load_json("game_history.json", [])

    recent_myth_ids = myth_history[-MYTH_HISTORY_LIMIT:]

    available_myths = [
        myth
        for myth in myths
        if myth["id"] not in recent_myth_ids and myth["game"] not in game_history
    ]

    if not available_myths:
        available_myths = [myth for myth in myths if myth["id"] not in recent_myth_ids]

    if not available_myths:
        available_myths = myths

    myth = random.choice(available_myths)

    myth_history.append(myth["id"])

    save_json("myth_history.json", myth_history[-MYTH_HISTORY_LIMIT:])

    remember_game(myth["game"])

    emoji = GAME_EMOJIS.get(myth["game"], "🎮")

    text = (
        "🧠 МИФ ИЛИ ПРАВДА?\n\n"
        f"{emoji} {myth['game']}\n\n"
        f"🔥 {myth['claim']}\n\n"
        "Как думаешь — правда или миф?\n\n"
        f"{myth['answer']}\n\n"
        f"{myth['explanation']}\n\n"
        "🎮 Roblox Hub"
    )

    return (myth["game"], text)


# --------------------------------------------------
# ЦЕЛЕВАЯ ДАТА
#
# Теперь сборка запускается утром
# и готовит посты НА СЕГОДНЯ.
# --------------------------------------------------

now = datetime.now(LOCAL_TIMEZONE)

target_date = now.date()


id_15 = f"{target_date}-{TIPS_POST_HOUR}"
id_19 = f"{target_date}-{MYTH_POST_HOUR}"


# --------------------------------------------------
# Очередь
# --------------------------------------------------

existing_posts = load_json("posts.json", [])


posts_added = 0
posts_updated = 0


# --------------------------------------------------
# 10:00
#
# Слот обязателен каждый день. Свежие проверенные новости
# имеют приоритет; при их отсутствии используем локальные
# проверенные советы или последний нейтральный fallback.
# --------------------------------------------------

morning_news_text = generate_morning_post()
morning_added, morning_updated = schedule_morning_post(
    existing_posts,
    target_date,
    news_text=morning_news_text,
)
posts_added += morning_added
posts_updated += morning_updated


# --------------------------------------------------
# 12:00 — Brawl Stars
#
# Свежие HIGH/MEDIUM статьи и Balance Changes имеют приоритет.
# Если monitor недоступен или готового выпуска нет, тот же
# стабильный слот получает локальный проверенный fallback.
# --------------------------------------------------

posts_added += schedule_brawl_post(
    existing_posts,
    target_date,
    skip_fresh_material=os.getenv(BRAWL_SKIP_ENVIRONMENT_VARIABLE) == "1",
)


# --------------------------------------------------
# 15:00
# --------------------------------------------------

post_15 = find_post(existing_posts, id_15)


if post_15 is None:
    tips_games, tips_text = generate_tips_post()

    existing_posts.append(
        build_post(
            post_id=id_15,
            publish_at=datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                TIPS_POST_HOUR,
                0,
                tzinfo=LOCAL_TIMEZONE,
            ),
            game=tips_games,
            rubric="Полезно знать",
            source="verified_db",
            text=tips_text,
        )
    )

    posts_added += 1

    print(f"15:00 — Полезно знать: " f"{tips_games}")

else:
    print("15:00 — пост уже существует.")


# --------------------------------------------------
# 11:00, 14:00, 17:00, 21:00 — посты с картинками
#
# Старые image-слоты 12:00 и 22:00 больше не создаются.
# Все четыре времени обслуживает одна общая функция.
# --------------------------------------------------

posts_added += schedule_image_posts(
    existing_posts,
    target_date,
)


# --------------------------------------------------
# 19:00
# --------------------------------------------------

post_19 = find_post(existing_posts, id_19)


if post_19 is None:
    myth_game, myth_text = generate_myth_post()

    existing_posts.append(
        build_post(
            post_id=id_19,
            publish_at=datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                MYTH_POST_HOUR,
                0,
                tzinfo=LOCAL_TIMEZONE,
            ),
            game=myth_game,
            rubric="Миф или правда",
            source="verified_db",
            text=myth_text,
        )
    )

    posts_added += 1

    print(f"19:00 — Миф или правда: " f"{myth_game}")

else:
    print("19:00 — пост уже существует.")


# --------------------------------------------------
# Сохраняем
# --------------------------------------------------

existing_posts.sort(key=lambda post: post["publish_at"])


save_json("posts.json", existing_posts)


print()

print(f"Очередь на {target_date} обработана.")

print(f"Добавлено новых постов: " f"{posts_added}")

print(f"Обновлено существующих постов: " f"{posts_updated}")
