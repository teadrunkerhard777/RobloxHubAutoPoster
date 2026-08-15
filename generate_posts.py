import json
import random

from datetime import datetime, timedelta, timezone


LOCAL_TIMEZONE = timezone(timedelta(hours=5))

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
    "Blade Ball": "⚔️"
}


# --------------------------------------------------
# Вспомогательные функции
# --------------------------------------------------

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


def load_json(filename, default=None):
    try:
        with open(
            filename,
            "r",
            encoding="utf-8"
        ) as file:
            return json.load(file)

    except FileNotFoundError:
        if default is not None:
            return default

        raise


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
        "game_history.json",
        []
    )

    history.append(game)

    save_json(
        "game_history.json",
        history[-GAME_HISTORY_LIMIT:]
    )


# --------------------------------------------------
# Бесплатно
# --------------------------------------------------

def generate_freebie_post():
    freebies = load_json(
        "freebies.json",
        []
    )

    available = [
        item
        for item in freebies
        if item.get("verified") is True
        and item.get("used") is not True
    ]

    if not available:
        return None

    freebie = available[0]

    freebie_id = freebie["id"]

    for item in freebies:
        if item["id"] == freebie_id:
            item["used"] = True
            break

    save_json(
        "freebies.json",
        freebies
    )

    return {
        "game": freebie.get(
            "game",
            "Roblox"
        ),
        "text": freebie["text"],
        "source": freebie.get(
            "source",
            "verified_freebie"
        )
    }


# --------------------------------------------------
# Полезно знать
# --------------------------------------------------

def generate_tips_post():
    tips = load_json(
        "tips.json"
    )

    game_history = load_json(
        "game_history.json",
        []
    )

    unused_tips = [
        tip
        for tip in tips
        if not tip["used"]
    ]

    if len(unused_tips) < 3:
        for tip in tips:
            tip["used"] = False

        unused_tips = tips.copy()

    preferred_tips = [
        tip
        for tip in unused_tips
        if tip["game"] not in game_history
    ]

    if len(preferred_tips) >= 3:
        candidates = preferred_tips.copy()
    else:
        candidates = unused_tips.copy()

    random.shuffle(candidates)

    selected_tips = []
    selected_games = set()

    for tip in candidates:
        if tip["game"] in selected_games:
            continue

        selected_tips.append(tip)
        selected_games.add(
            tip["game"]
        )

        if len(selected_tips) == 3:
            break

    if len(selected_tips) < 3:
        for tip in unused_tips:
            if tip["game"] in selected_games:
                continue

            selected_tips.append(tip)
            selected_games.add(
                tip["game"]
            )

            if len(selected_tips) == 3:
                break

    if len(selected_tips) < 3:
        raise RuntimeError(
            "Не удалось выбрать три совета "
            "по трём разным играм."
        )

    selected_ids = {
        tip["id"]
        for tip in selected_tips
    }

    for tip in tips:
        if tip["id"] in selected_ids:
            tip["used"] = True

    save_json(
        "tips.json",
        tips
    )

    for tip in selected_tips:
        remember_game(
            tip["game"]
        )

    blocks = []

    for tip in selected_tips:
        emoji = GAME_EMOJIS.get(
            tip["game"],
            "🎮"
        )

        block = (
            f"{emoji} {tip['game']}\n"
            f"{tip['text']}"
        )

        blocks.append(block)

    text = (
        "💡 ПОЛЕЗНО ЗНАТЬ\n\n"
        + "\n\n".join(blocks)
        + "\n\n🎮 Roblox Hub"
    )

    games = " + ".join(
        tip["game"]
        for tip in selected_tips
    )

    return games, text


# --------------------------------------------------
# Миф или правда
# --------------------------------------------------

def generate_myth_post():
    myths = load_json(
        "myths.json"
    )

    myth_history = load_json(
        "myth_history.json",
        []
    )

    game_history = load_json(
        "game_history.json",
        []
    )

    recent_myth_ids = myth_history[
        -MYTH_HISTORY_LIMIT:
    ]

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

    emoji = GAME_EMOJIS.get(
        myth["game"],
        "🎮"
    )

    text = (
        "🧠 МИФ ИЛИ ПРАВДА?\n\n"

        f"{emoji} {myth['game']}\n\n"

        f"🔥 {myth['claim']}\n\n"

        "Как думаешь — правда или миф?\n\n"

        f"{myth['answer']}\n\n"

        f"{myth['explanation']}\n\n"

        "🎮 Roblox Hub"
    )

    return myth["game"], text


# --------------------------------------------------
# Дата завтрашней очереди
# --------------------------------------------------

now = datetime.now(
    LOCAL_TIMEZONE
)

tomorrow = (
    now + timedelta(days=1)
).date()


id_10 = f"{tomorrow}-10"
id_12 = f"{tomorrow}-12"
id_15 = f"{tomorrow}-15"
id_18 = f"{tomorrow}-18"


# --------------------------------------------------
# Загружаем текущую очередь
# --------------------------------------------------

existing_posts = load_json(
    "posts.json",
    []
)

existing_ids = {
    str(post["id"])
    for post in existing_posts
}


posts_added = 0


# --------------------------------------------------
# 10:00 — утренний выпуск
# --------------------------------------------------

if id_10 not in existing_ids:
    news_text = load_text(
        "generated_news_post_ru.txt"
    )

    post_10 = build_post(
        post_id=id_10,
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
    )

    existing_posts.append(
        post_10
    )

    existing_ids.add(
        id_10
    )

    posts_added += 1

    print(
        "10:00 — утренний выпуск добавлен."
    )

else:
    print(
        "10:00 — пост уже существует."
    )


# --------------------------------------------------
# 12:00 — Бесплатно
# --------------------------------------------------

if id_12 not in existing_ids:
    freebie = generate_freebie_post()

    if freebie is not None:
        post_12 = build_post(
            post_id=id_12,
            publish_at=datetime(
                tomorrow.year,
                tomorrow.month,
                tomorrow.day,
                12,
                0,
                tzinfo=LOCAL_TIMEZONE
            ),
            game=freebie["game"],
            rubric="Бесплатно в Roblox",
            source=freebie["source"],
            text=freebie["text"]
        )

        existing_posts.append(
            post_12
        )

        existing_ids.add(
            id_12
        )

        posts_added += 1

        print(
            "12:00 — бесплатный пост добавлен."
        )

    else:
        print(
            "12:00 — подтверждённых "
            "бесплатных предложений нет."
        )

else:
    print(
        "12:00 — пост уже существует."
    )


# --------------------------------------------------
# 15:00 — Полезно знать
# --------------------------------------------------

if id_15 not in existing_ids:
    tips_games, tips_text = (
        generate_tips_post()
    )

    post_15 = build_post(
        post_id=id_15,
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
    )

    existing_posts.append(
        post_15
    )

    existing_ids.add(
        id_15
    )

    posts_added += 1

    print(
        f"15:00 — Полезно знать: "
        f"{tips_games}"
    )

else:
    print(
        "15:00 — пост уже существует."
    )


# --------------------------------------------------
# 18:00 — Миф или правда
# --------------------------------------------------

if id_18 not in existing_ids:
    myth_game, myth_text = (
        generate_myth_post()
    )

    post_18 = build_post(
        post_id=id_18,
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

    existing_posts.append(
        post_18
    )

    existing_ids.add(
        id_18
    )

    posts_added += 1

    print(
        f"18:00 — Миф или правда: "
        f"{myth_game}"
    )

else:
    print(
        "18:00 — пост уже существует."
    )


# --------------------------------------------------
# Сохраняем очередь
# --------------------------------------------------

existing_posts.sort(
    key=lambda post: post["publish_at"]
)

save_json(
    "posts.json",
    existing_posts
)


print()
print(
    f"Очередь на {tomorrow} обработана."
)

print(
    f"Добавлено новых постов: "
    f"{posts_added}"
)
