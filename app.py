import os
import requests

from dotenv import load_dotenv


load_dotenv()

token = os.getenv("TELEGRAM_BOT_TOKEN")

url = f"https://api.telegram.org/bot{token}/sendMessage"

data = {
    "chat_id": "@RobloxHubRU",
    "text": "☁️ Тест будущего Render AutoPoster!\n\nСкрипт запустился, отправил этот пост и завершил работу."
}

try:
    response = requests.post(url, data=data, timeout=10)

    print("HTTP status:", response.status_code)
    print(response.json())

except requests.RequestException as error:
    print("Ошибка соединения с Telegram:")
    print(error)
