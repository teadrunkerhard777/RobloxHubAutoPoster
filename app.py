import json
import os
import requests

from datetime import datetime
from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

url = f"https://api.telegram.org/bot{token}/sendMessage"


with open("posts.json", "r", encoding="utf-8") as file:
    posts = json.load(file)


now = datetime.now().astimezone()

post_to_publish = None

for post in posts:

    if post["published"]:
        continue

    publish_at = datetime.fromisoformat(post["publish_at"])

    if publish_at <= now:
        post_to_publish = post
        break


if post_to_publish is None:
    print("Сейчас нет постов, время публикации которых уже наступило.")
    raise SystemExit


data = {
    "chat_id": "@RobloxHubRU",
    "text": post_to_publish["text"]
}


response = requests.post(url, data=data, timeout=10)

print("HTTP status:", response.status_code)
print(response.json())

response.raise_for_status()


post_to_publish["published"] = True


with open("posts.json", "w", encoding="utf-8") as file:
    json.dump(posts, file, ensure_ascii=False, indent=2)


print(
    f"Пост #{post_to_publish['id']} опубликован "
    f"по расписанию {post_to_publish['publish_at']}."
)
