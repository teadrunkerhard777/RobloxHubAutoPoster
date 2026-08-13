import json
import os
import requests

from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

url = f"https://api.telegram.org/bot{token}/sendMessage"


with open("posts.json", "r", encoding="utf-8") as file:
    posts = json.load(file)


post_to_publish = None

for post in posts:
    if not post["published"]:
        post_to_publish = post
        break


if post_to_publish is None:
    print("Нет постов для публикации.")
    raise SystemExit


data = {
    "chat_id": "@RobloxHubRU",
    "text": post_to_publish["text"]
}


try:
    response = requests.post(url, data=data, timeout=10)

    print("HTTP status:", response.status_code)
    print(response.json())

    response.raise_for_status()

except requests.RequestException as error:
    print("Ошибка при публикации в Telegram:")
    print(error)
    raise


post_to_publish["published"] = True


with open("posts.json", "w", encoding="utf-8") as file:
    json.dump(posts, file, ensure_ascii=False, indent=2)


print(
    f"Пост #{post_to_publish['id']} опубликован "
    "и отмечен как published."
)
