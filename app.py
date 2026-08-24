import json
import os
import time
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
api_url = f"https://api.telegram.org/bot{token}"

LOCAL_TIMEZONE = timezone(timedelta(hours=5))

# Image-посты разрешено отправлять только в их часовом окне.
# Это защищает от случайной поздней публикации при ручном запуске.
IMAGE_PUBLISH_HOURS = (11, 14, 17, 21)


def is_image_post(post):
    """Проверяет, содержит ли запись файл изображения."""
    return bool(post.get("image_path"))


def should_publish_post(post, now):
    """
    Определяет, можно ли отправлять запись в текущий момент.

    Обычные текстовые посты сохраняют прежнюю логику: любой
    просроченный pending/failed пост можно отправить. Картинки
    публикуются только в назначенный час 11, 14, 17 или 21.

    Повторный запуск безопасен: published-запись сразу
    исключается и не отправляется второй раз.
    """

    if post.get("status") == "published":
        return False

    publish_at = datetime.fromisoformat(post["publish_at"])

    if publish_at > now:
        return False

    if not is_image_post(post):
        return True

    local_publish_at = publish_at.astimezone(LOCAL_TIMEZONE)
    local_now = now.astimezone(LOCAL_TIMEZONE)

    if local_publish_at.hour not in IMAGE_PUBLISH_HOURS:
        return False

    return (
        local_publish_at.date() == local_now.date()
        and local_publish_at.hour == local_now.hour
    )


with open("posts.json", "r", encoding="utf-8") as file:
    posts = json.load(file)


now = datetime.now(LOCAL_TIMEZONE)

posts_to_publish = []


for post in posts:
    if should_publish_post(post, now):
        posts_to_publish.append(post)


posts_to_publish.sort(key=lambda post: datetime.fromisoformat(post["publish_at"]))


if not posts_to_publish:
    print("Сейчас нет постов для публикации.")
    raise SystemExit


print(f"Найдено постов для публикации: {len(posts_to_publish)}")


for post in posts_to_publish:

    post["attempts"] += 1
    post["last_error"] = None

    try:
        image_path = post.get("image_path")

        if image_path:
            data = {"chat_id": "@RobloxHubRU"}

            if post.get("text"):
                data["caption"] = post["text"]

            with open(image_path, "rb") as image_file:
                response = requests.post(
                    f"{api_url}/sendPhoto",
                    data=data,
                    files={"photo": image_file},
                    timeout=30,
                )
        else:
            response = requests.post(
                f"{api_url}/sendMessage",
                data={"chat_id": "@RobloxHubRU", "text": post["text"]},
                timeout=10,
            )

        print(f"Пост #{post['id']}: " f"HTTP {response.status_code}")

        response.raise_for_status()

        post["status"] = "published"

        post["published_at"] = datetime.now(LOCAL_TIMEZONE).isoformat()

        print(f"Пост #{post['id']} успешно опубликован.")

    except (OSError, requests.RequestException) as error:

        post["status"] = "failed"
        post["last_error"] = str(error)

        print(f"Ошибка публикации поста #{post['id']}: " f"{error}")

    time.sleep(3)


with open("posts.json", "w", encoding="utf-8") as file:
    json.dump(posts, file, ensure_ascii=False, indent=2)


print("Очередь обновлена.")
