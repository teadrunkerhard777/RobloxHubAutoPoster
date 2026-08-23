import json
import random
from datetime import datetime, timedelta, timezone

from image_library import select_daily_image

LOCAL_TIMEZONE = timezone(timedelta(hours=5))

# Картинки публикуются три раза в день.
# Один генератор обслуживает все слоты без отдельных скриптов.
IMAGE_POST_HOURS = (12, 17, 22)
IMAGE_DIRECTORY = "images/16-00"
IMAGE_HISTORY_FILE = "image_history.json"

MYTH_HISTORY_LIMIT = 3
GAME_HISTORY_LIMIT = 5


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
    Добавляет недостающие image-посты на 12:00, 17:00 и 22:00.

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


# --------------------------------------------------
# Советы
# --------------------------------------------------


def reset_tips_if_needed(tips, minimum_needed):
    unused = [tip for tip in tips if not tip.get("used", False)]

    if len(unused) >= minimum_needed:
        return tips

    for tip in tips:
        tip["used"] = False

    return tips


def select_tips(count, excluded_games=None):
    if excluded_games is None:
        excluded_games = set()

    tips = load_json("tips.json")

    tips = reset_tips_if_needed(tips, count)

    game_history = load_json("game_history.json", [])

    unused = [tip for tip in tips if not tip.get("used", False)]

    preferred = [
        tip
        for tip in unused
        if tip["game"] not in excluded_games and tip["game"] not in game_history
    ]

    fallback = [tip for tip in unused if tip["game"] not in excluded_games]

    candidates = preferred + fallback

    random.shuffle(candidates)

    selected = []
    selected_ids = set()
    selected_games = set()

    for tip in candidates:
        if tip["id"] in selected_ids:
            continue

        if tip["game"] in selected_games:
            continue

        selected.append(tip)

        selected_ids.add(tip["id"])

        selected_games.add(tip["game"])

        if len(selected) == count:
            break

    if len(selected) < count:
        raise RuntimeError(
            f"Не удалось выбрать " f"{count} советов " "по разным играм."
        )

    for tip in tips:
        if tip["id"] in selected_ids:
            tip["used"] = True

    save_json("tips.json", tips)

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


# --------------------------------------------------
# 12:00 — бесплатно
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
    selected_tips = select_tips(count=3)

    blocks = []

    for tip in selected_tips:
        emoji = GAME_EMOJIS.get(tip["game"], "🎮")

        blocks.append(f"{emoji} {tip['game']}\n" f"{tip['text']}")

    text = "💡 ПОЛЕЗНО ЗНАТЬ\n\n" + "\n\n".join(blocks) + "\n\n🎮 Roblox Hub"

    games = " + ".join(tip["game"] for tip in selected_tips)

    return games, text


# --------------------------------------------------
# 18:00 — Миф или правда
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


id_10 = f"{target_date}-10"
id_12 = f"{target_date}-12"
id_15 = f"{target_date}-15"
id_18 = f"{target_date}-18"


# --------------------------------------------------
# Очередь
# --------------------------------------------------

existing_posts = load_json("posts.json", [])


posts_added = 0
posts_updated = 0


# --------------------------------------------------
# 10:00
#
# Особое правило:
# если пост уже существует, но ещё pending,
# обновляем его свежей утренней сводкой.
# --------------------------------------------------

post_10 = find_post(existing_posts, id_10)

morning_text = generate_morning_post()


if morning_text is None:
    if (
        post_10 is not None
        and post_10.get("status") != "published"
        and post_10.get("source") == "auto_verified"
    ):
        existing_posts.remove(post_10)
        posts_updated += 1
        print(
            "10:00 — достойных свежих новостей нет; "
            "неопубликованный выпуск удалён из очереди."
        )
    else:
        print("10:00 — достойных свежих новостей нет; " "утренний выпуск не создаём.")

elif post_10 is None:

    existing_posts.append(
        build_post(
            post_id=id_10,
            publish_at=datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                10,
                0,
                tzinfo=LOCAL_TIMEZONE,
            ),
            game="разные игры",
            rubric="Выпуск дня",
            source="auto_verified",
            text=morning_text,
        )
    )

    posts_added += 1

    print("10:00 — выпуск дня добавлен.")

elif post_10.get("status") == "pending":
    post_10["text"] = morning_text
    post_10["rubric"] = "Выпуск дня"
    post_10["source"] = "auto_verified"

    posts_updated += 1

    print("10:00 — pending-выпуск обновлён " "свежими утренними данными.")

else:
    print("10:00 — пост уже опубликован, " "не изменяем.")


# --------------------------------------------------
# 12:00
# --------------------------------------------------

post_12 = find_post(existing_posts, id_12)


if post_12 is None:
    freebie = generate_freebie_post()

    if freebie is not None:
        existing_posts.append(
            build_post(
                post_id=id_12,
                publish_at=datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                    12,
                    0,
                    tzinfo=LOCAL_TIMEZONE,
                ),
                game=freebie["game"],
                rubric="Бесплатно в Roblox",
                source=freebie["source"],
                text=freebie["text"],
            )
        )

        posts_added += 1

        print("12:00 — бесплатный пост добавлен.")

    else:
        print("12:00 — подтверждённых " "бесплатных предложений нет.")

else:
    print("12:00 — пост уже существует.")


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
                15,
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
# 12:00, 17:00, 22:00 — посты с картинками
#
# Старый отдельный слот 16:00 больше не создаётся.
# Все три времени обслуживает одна общая функция.
# --------------------------------------------------

posts_added += schedule_image_posts(
    existing_posts,
    target_date,
)


# --------------------------------------------------
# 18:00
# --------------------------------------------------

post_18 = find_post(existing_posts, id_18)


if post_18 is None:
    myth_game, myth_text = generate_myth_post()

    existing_posts.append(
        build_post(
            post_id=id_18,
            publish_at=datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                18,
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

    print(f"18:00 — Миф или правда: " f"{myth_game}")

else:
    print("18:00 — пост уже существует.")


# --------------------------------------------------
# Сохраняем
# --------------------------------------------------

existing_posts.sort(key=lambda post: post["publish_at"])


save_json("posts.json", existing_posts)


print()

print(f"Очередь на {target_date} обработана.")

print(f"Добавлено новых постов: " f"{posts_added}")

print(f"Обновлено существующих постов: " f"{posts_updated}")
