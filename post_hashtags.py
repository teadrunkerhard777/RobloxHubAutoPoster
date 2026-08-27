import re

HITS_RUBRIC = "Новинки и хиты Roblox"
TIPS_RUBRIC = "Полезно знать"
IMAGE_RUBRIC = "Картинка дня"

GAME_HASHTAG_OVERRIDES = {
    "Animal Hospital (Anomaly)": "AnimalHospital",
    "+1 Speed Keyboard Escape": "SpeedKeyboardEscape",
}

IMAGE_HASHTAGS = (
    "#Roblox",
    "#BrawlStars",
    "#StealABrainrot",
    "#99Nights",
)


def game_hashtag(game):
    """Возвращает латинский hashtag названия игры без пробелов."""

    if game in GAME_HASHTAG_OVERRIDES:
        return f"#{GAME_HASHTAG_OVERRIDES[game]}"

    normalized = re.sub(r"[^A-Za-z0-9]", "", game or "")
    return f"#{normalized}" if normalized else None


def hashtags_for_post(rubric, game, source=None):
    """Определяет не более четырёх тегов из метаданных поста."""

    if source == "image_library" or rubric == IMAGE_RUBRIC:
        return IMAGE_HASHTAGS

    if game == "Brawl Stars" or (rubric or "").startswith("Brawl Stars"):
        return ("#BrawlStars", "#ПолезноЗнать", "#RobloxHub")

    if rubric == HITS_RUBRIC:
        title_tag = game_hashtag(game)
        tags = ["#Roblox"]
        if title_tag:
            tags.append(title_tag)
        tags.append("#НовинкиRoblox")
        return tuple(tags[:3])

    if rubric == TIPS_RUBRIC:
        return ("#Roblox", "#ПолезноЗнать", "#RobloxHub")

    return ()


def add_post_hashtags(text, rubric, game, source=None):
    """Добавляет вычисленные теги через пустую строку и без дублей."""

    tags = hashtags_for_post(rubric, game, source=source)
    if not tags:
        return text or ""

    hashtag_line = " ".join(tags)
    normalized_text = (text or "").rstrip()

    if normalized_text.endswith(hashtag_line):
        return normalized_text

    if normalized_text:
        return f"{normalized_text}\n\n{hashtag_line}"

    return hashtag_line


def update_pending_post_hashtags(posts):
    """Дополняет очередь, не изменяя уже опубликованный архив."""

    updated = 0

    for post in posts:
        if post.get("status") == "published":
            continue

        current_text = post.get("text", "")
        tagged_text = add_post_hashtags(
            current_text,
            post.get("rubric"),
            post.get("game"),
            source=post.get("source"),
        )

        if tagged_text != current_text:
            post["text"] = tagged_text
            updated += 1

    return updated
