from fastapi import FastAPI, Request
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

# Словарь разделов форума: имя -> message_thread_id
FORUM_TOPICS = {
    "Новости": 1111,
    "Анонсы": 2222,
    "Вопросы": 3333
}

# Состояние пользователя: user_id -> выбранный topic_id
USER_TOPICS = {}

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/bot")
async def telegram_webhook(req: Request):
    try:
        data = await req.json()
        print(data)

        chat_id = None
        text = None
        callback_data = None

        # Проверяем обычные сообщения
        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text")

        # Проверяем нажатия кнопок (callback_query)
        elif "callback_query" in data:
            callback_data = data["callback_query"]["data"]
            chat_id = data["callback_query"]["from"]["id"]

        # Если пользователь нажал кнопку выбора раздела
        if callback_data:
            if callback_data in FORUM_TOPICS:
                USER_TOPICS[chat_id] = FORUM_TOPICS[callback_data]
                reply = f"Раздел '{callback_data}' выбран ✅"
            else:
                reply = "Неизвестный раздел!"
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(url, json={"chat_id": chat_id, "text": reply})
            return {"ok": True}

        # Если пользователь пишет текстовое сообщение
        if text:
            # Проверяем, есть ли выбранный раздел
            topic_id = USER_TOPICS.get(chat_id)
            if not topic_id:
                # Отправляем кнопки выбора раздела
                keyboard = {
                    "inline_keyboard": [
                        [{"text": name, "callback_data": name}] for name in FORUM_TOPICS.keys()
                    ]
                }
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": "Выберите раздел для публикации:",
                        "reply_markup": keyboard
                    })
                return {"ok": True}

            # Если раздел выбран, отправляем сообщение в группу и раздел форума
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": GROUP_ID,
                "text": text,
                "message_thread_id": topic_id
            }
            async with httpx.AsyncClient() as client:
                await client.post(url, json=payload)

        return {"ok": True}

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}
