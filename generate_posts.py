import json
import random

from datetime import datetime, timedelta, timezone


LOCAL_TIMEZONE = timezone(timedelta(hours=5))

MYTH_HISTORY_LIMIT = 3
GAME_HISTORY_LIMIT = 5


def build_post(
    post_id,
    publish_at,
    game,
    rubric,
    text,
    source
):
    return {
        "id": post_id,
        "publish_at": publish_at.isoformat(),
        "game": game,
        "rubric": rubric,
        "source": source,
        "text": text,
        "status": "pending",
        "published_at": None,
        "attempts": 0,
        "last_error": None
    }


def load_json(filename):
    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:
        return json.load(file)


def save_json(filename, data):
    with open(
        filename,
        "w",
        encoding="utf-8"
    ) as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_text(filename):
    with open(
        filename,
        "r",
        encoding="utf-8"
    ) as file:
        return file.read().strip()


def remember_game(game):
    history = load_json(
        "game_history.json"
    )

    history.append(game)

    save_json(
        "game_history.json",
        history[-GAME_HISTORY_LIMIT:]
    )


def generate_tips_post():
    tips = load_json(
        "tips.json"
    )

    game_history = load_json(
        "game_history.json"
    )

    unused_tips = [
        tip
        for tip in tips
        if not tip["used"]
    ]

    # Если база закончилась —
    # начинаем новый цикл.
    if len(unused_tips) < 2:
        for tip in tips:
            tip["used"] = False

        unused_tips = tips.copy()

    # Сначала стараемся не брать
    # недавно использованные игры.
    preferred_tips = [
        tip
        for tip in unused_tips
        if tip["game"] not in game_history
    ]

    if len(preferred_tips) >= 2:
        candidates = preferred_tips
    else:
        candidates = unused_tips.copy()

    random.shuffle(candidates)

    first_tip = None
    second_tip = None

    for tip in candidates:
        if first_tip is None:
            first_tip = tip
            continue

        if tip["game"] != first_tip["game"]:
            second_tip = tip
            break

    # Страховка на случай,
    # если подходящей пары не нашлось.
    if second_tip is None and first_tip is not None:
        for tip in unused_tips:
            if tip["game"] != first_tip["game"]:
                second_tip = tip
                break

    if first_tip is None or second_tip is None:
        raise RuntimeError(
            "Не удалось выбрать два совета "
            "по разным играм."
        )

    # Только теперь отмечаем советы
    # использованными.
    selected_ids = {
        first_tip["id"],
        second_tip["id"]
    }

    for tip in tips:
        if tip["id"] in selected_ids:
            tip["used"] = True

    save_json(
        "tips.json",
        tips
    )

    remember_game(
        first_tip["game"]
    )

    remember_game(
        second_tip["game"]
    )

    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "       🎮 ПОЛЕЗНО ЗНАТЬ 🎮\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎯 {first_tip['game']}\n"
        f"💡 {first_tip['text']}\n\n"
        f"🎯 {second_tip['game']}\n"
        f"💡 {second_tip['text']}\n\n"
        "🎮 Roblox Hub"
    )

    games = (
        f"{first_tip['game']} + "
        f"{second_tip['game']}"
    )

    return games, text


def generate_myth_post():
    myths = load_json(
        "myths.json"
    )

    myth_history = load_json(
        "myth_history.json"
    )

    game_history = load_json(
        "game_history.json"
    )

    recent_myth_ids = (
        myth_history[
            -MYTH_HISTORY_LIMIT:
        ]
    )

    available_myths = [
        myth
        for myth in myths
        if myth["id"] not in recent_myth_ids
        and myth["game"] not in game_history
    ]

    if not available_myths:
        available_myths = [
            myth
            for myth in myths
            if myth["id"] not in recent_myth_ids
        ]

    if not available_myths:
        available_myths = myths

    myth = random.choice(
        available_myths
    )

    myth_history.append(
        myth["id"]
    )

    save_json(
        "myth_history.json",
        myth_history[
            -MYTH_HISTORY_LIMIT:
        ]
    )

    remember_game(
        myth["game"]
    )

    text = (
        "━━━━━━━━━━━━━━━━━━━━━\n"
        "      🧠 МИФ ИЛИ ПРАВДА? 🧠\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🎮 {myth['game']}\n\n"
        f"🔥 {myth['claim']} 🔥\n\n"
        "Как думаешь — правда или миф?\n\n"
        f"{myth['answer']}\n\n"
        f"{myth['explanation']}\n\n"
        "🎮 Roblox Hub"
    )

    return myth["game"], text


# --------------------------------------------------
# Определяем дату завтрашней очереди
# --------------------------------------------------

now = datetime.now(
    LOCAL_TIMEZONE
)

tomorrow = (
    now + timedelta(days=1)
).date()


tomorrow_ids = {
    f"{tomorrow}-10",
    f"{tomorrow}-15",
    f"{tomorrow}-18"
}


# --------------------------------------------------
# СНАЧАЛА проверяем существующую очередь
# --------------------------------------------------

try:
    existing_posts = load_json(
        "posts.json"
    )
except FileNotFoundError:
    existing_posts = []


existing_ids = {
    str(post["id"])
    for post in existing_posts
}


existing_tomorrow_ids = (
    tomorrow_ids & existing_ids
)


if existing_tomorrow_ids == tomorrow_ids:
    print()
    print(
        f"Очередь на {tomorrow} "
        "уже полностью существует."
    )

    print(
        "Новые советы и миф "
        "не выбирались."
    )

    print(
        "История использования "
        "не изменена."
    )

    print(
        "Добавлено новых постов: 0"
    )

    raise SystemExit


# --------------------------------------------------
# Только если очереди ещё нет —
# создаём контент
# --------------------------------------------------

news_text = load_text(
    "generated_news_post_ru.txt"
)


tips_games, tips_text = (
    generate_tips_post()
)


myth_game, myth_text = (
    generate_myth_post()
)


new_posts = [
    build_post(
        post_id=f"{tomorrow}-10",
        publish_at=datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            10,
            0,
            tzinfo=LOCAL_TIMEZONE
        ),
        game="разные игры",
        rubric="Сводка новостей",
        source="auto_verified",
        text=news_text
    ),

    build_post(
        post_id=f"{tomorrow}-15",
        publish_at=datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            15,
            0,
            tzinfo=LOCAL_TIMEZONE
        ),
        game=tips_games,
        rubric="Полезно знать",
        source="verified_db",
        text=tips_text
    ),

    build_post(
        post_id=f"{tomorrow}-18",
        publish_at=datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            18,
            0,
            tzinfo=LOCAL_TIMEZONE
        ),
        game=myth_game,
        rubric="Миф или правда",
        source="verified_db",
        text=myth_text
    )
]


posts_added = 0


for post in new_posts:

    if str(post["id"]) in existing_ids:
        print(
            f"Пост {post['id']} "
            "уже существует — пропускаем."
        )

        continue

    existing_posts.append(
        post
    )

    posts_added += 1


existing_posts.sort(
    key=lambda post: post["publish_at"]
)


save_json(
    "posts.json",
    existing_posts
)


print()
print("Очередь подготовлена.")
print(
    f"Дата новых постов: {tomorrow}"
)
print(
    f"Добавлено новых постов: {posts_added}"
)

print(
    "10:00 — Сводка новостей"
)

print(
    f"15:00 — Полезно знать: "
    f"{tips_games}"
)

print(
    f"18:00 — Миф или правда: "
    f"{myth_game}"
)
