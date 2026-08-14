import json
import os
import time
import requests

from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

url = f"https://api.telegram.org/bot{token}/sendMessage"


with open("posts.json", "r", encoding="utf-8") as file:
    posts = json.load(file)


now = datetime.now().astimezone()

posts_to_publish = []

for post in posts:

    if post["published"]:
        continue

    publish_at = datetime.fromisoformat(post["publish_at"])

    if publish_at <= now:
        posts_to_publish.append(post)


posts_to_publish.sort(
    key=lambda post: datetime.fromisoformat(post["publish_at"])
)


if not posts_to_publish:
    print("Сейчас нет просроченных постов.")
    raise SystemExit


print(f"Найдено постов для публикации: {len(posts_to_publish)}")


for post in posts_to_publish:

    data = {
        "chat_id": "@RobloxHubRU",
        "text": post["text"]
    }

    response = requests.post(
        url,
        data=data,
        timeout=10
    )

    print(
        f"Пост #{post['id']}:",
        response.status_code
    )

    response.raise_for_status()

    post["published"] = True

    print(
        f"Пост #{post['id']} опубликован "
        f"(план: {post['publish_at']})"
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
