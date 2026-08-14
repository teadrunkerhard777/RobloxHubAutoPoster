import json
import random

from datetime import datetime, timedelta, timezone


LOCAL_TIMEZONE = timezone(timedelta(hours=5))

MYTH_HISTORY_LIMIT = 3
GAME_HISTORY_LIMIT = 5


def build_post(post_id, publish_at, game, rubric, text):
    return {
        "id": post_id,
        "publish_at": publish_at.isoformat(),
        "game": game,
        "rubric": rubric,
        "source": "manual",
        "text": text,
        "status": "pending",
        "published_at": None,
        "attempts": 0,
        "last_error": None
    }


def load_json(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return json.load(file)


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            data,
            file,
            ensure_ascii=False,
            indent=2
        )


def load_text(filename):
    with open(filename, "r", encoding="utf-8") as file:
        return file.read().strip()


def remember_game(game):
    history = load_json("game_history.json")

    history.append(game)

    save_json(
        "game_history.json",
        history[-GAME_HISTORY_LIMIT:]
    )


def generate_myth_post():
    myths = load_json("myths.json")
    myth_history = load_json("myth_history.json")
    game_history = load_json("game_history.json")

    recent_myth_ids = myth_history[-MYTH_HISTORY_LIMIT:]

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

    myth = random.choice(available_myths)

    myth_history.append(myth["id"])

    save_json(
        "myth_history.json",
        myth_history[-MYTH_HISTORY_LIMIT:]
    )

    remember_game(myth["game"])

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


now = datetime.now(LOCAL_TIMEZONE)
tomorrow = (now + timedelta(days=1)).date()

news_text = load_text("generated_news_post_ru.txt")
myth_game, myth_text = generate_myth_post()


posts = [
    build_post(
        post_id=1,
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
        text=news_text
    ),

    build_post(
        post_id=2,
        publish_at=datetime(
            tomorrow.year,
            tomorrow.month,
            tomorrow.day,
            15,
            0,
            tzinfo=LOCAL_TIMEZONE
        ),
        game="две разные игры",
        rubric="Полезная карточка",
        text="🖼 Полезная карточка Roblox Hub"
    ),

    build_post(
        post_id=3,
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
        text=myth_text
    )
]


save_json(
    "posts.json",
    posts
)


print("Очередь на завтра создана.")
print(f"Дата: {tomorrow}")
print(f"Количество постов: {len(posts)}")
print("Новостная сводка загружена.")
print(f"Миф или правда: {myth_game}")
