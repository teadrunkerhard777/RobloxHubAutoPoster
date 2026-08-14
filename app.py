import json
import os
import time
import requests

from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")
url = f"https://api.telegram.org/bot{token}/sendMessage"

LOCAL_TIMEZONE = timezone(timedelta(hours=5))


with open("posts.json", "r", encoding="utf-8") as file:
    posts = json.load(file)


now = datetime.now(LOCAL_TIMEZONE)

posts_to_publish = []


for post in posts:

    if post["status"] == "published":
        continue

    publish_at = datetime.fromisoformat(post["publish_at"])

    if publish_at <= now:
        posts_to_publish.append(post)


posts_to_publish.sort(
    key=lambda post: datetime.fromisoformat(post["publish_at"])
)


if not posts_to_publish:
    print("Сейчас нет постов для публикации.")
    raise SystemExit


print(f"Найдено постов для публикации: {len(posts_to_publish)}")


for post in posts_to_publish:

    post["attempts"] += 1
    post["last_error"] = None

    data = {
        "chat_id": "@RobloxHubRU",
        "text": post["text"]
    }

    try:
        response = requests.post(
            url,
            data=data,
            timeout=10
        )

        print(
            f"Пост #{post['id']}: "
            f"HTTP {response.status_code}"
        )

        response.raise_for_status()

        post["status"] = "published"

        post["published_at"] = (
            datetime.now(LOCAL_TIMEZONE).isoformat()
        )

        print(
            f"Пост #{post['id']} успешно опубликован."
        )

    except requests.RequestException as error:

        post["status"] = "failed"
        post["last_error"] = str(error)

        print(
            f"Ошибка публикации поста #{post['id']}: "
            f"{error}"
        )

    time.sleep(3)


with open("posts.json", "w", encoding="utf-8") as file:
    json.dump(
        posts,
        file,
        ensure_ascii=False,
        indent=2
    )


print("Очередь обновлена.")
