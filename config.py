import os

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN or BOT_TOKEN == "сюда_вставишь_токен_своего_бота":
    raise ValueError(
        "Укажи настоящий BOT_TOKEN в файле .env"
    )

if ADMIN_ID <= 0:
    print("Предупреждение: ADMIN_ID пока не настроен.")