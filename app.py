import os
import requests

from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = {
    "chat_id": "@RobloxHubRU",
    "text": "ГИТ ЭКШН!!!"
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

except requests.RequestException as error:
    print("Ошибка соединения с Telegram:")
    print(error)
