from fastapi import FastAPI, Request
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

# Состояние пользователя: chat_id -> выбранный topic_id
USER_TOPICS = {}

app = FastAPI()

async def get_forum_topics():
    """Получаем список разделов форума из группы"""
    url = f"https://api.telegram.org/bot{TOKEN}/getForumTopics?chat_id={GROUP_ID}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()
        topics = {}
        if data.get("ok"):
            for t in data["result"]:
                # name -> message_thread_id
                topics[t["name"]] = t["message_thread_id"]
        return topics

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/bot")
async def telegram_webhook(req: Request):
    try:
        data = await req.json()
        chat_id = None
        text = None
        callback_data = None

        if "message" in data:
            chat_id = data["message"]["chat"]["id"]
            text = data["message"].get("text")
        elif "callback_query" in data:
            callback_data = data["callback_query"]["data"]
            chat_id = data["callback_query"]["from"]["id"]

        # Если нажали кнопку выбора раздела
        if callback_data:
            topics = await get_forum_topics()
            if callback_data in topics:
                USER_TOPICS[chat_id] = topics[callback_data]
                reply = f"Раздел '{callback_data}' выбран ✅"
            else:
                reply = "Этот раздел больше не существует!"
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(url, json={"chat_id": chat_id, "text": reply})
            return {"ok": True}

        # Если пишем сообщение
        if text:
            topic_id = USER_TOPICS.get(chat_id)
            if not topic_id:
                # Получаем разделы и формируем кнопки
                topics = await get_forum_topics()
                keyboard = {"inline_keyboard": [[{"text": name, "callback_data": name}] for name in topics.keys()]}
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                async with httpx.AsyncClient() as client:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": "Выберите раздел форума для публикации:",
                        "reply_markup": keyboard
                    })
                return {"ok": True}

            # Раздел выбран, отправляем сообщение в группу
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {"chat_id": GROUP_ID, "text": text, "message_thread_id": topic_id}
            async with httpx.AsyncClient() as client:
                resp = await client.post(url, json=payload)
                print("Send message response:", await resp.text())

        return {"ok": True}

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}
