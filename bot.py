from fastapi import FastAPI, Request
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TOKEN")
GROUP_ID = os.getenv("GROUP_ID")  # ❗ убрали int здесь

app = FastAPI()

# ✅ Проверка, что сервер жив
@app.get("/")
async def root():
    return {"status": "ok"}

# ✅ Telegram webhook
@app.post("/bot")
async def telegram_webhook(req: Request):
    data = await req.json()
    print(data)

    try:
        if "message" in data:
            text = data["message"].get("text")
            if text:
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
                payload = {
                    "chat_id": int(GROUP_ID),  # 👈 конвертация здесь безопаснее
                    "text": text
                }

                async with httpx.AsyncClient() as client:
                    await client.post(url, data=payload)

    except Exception as e:
        print("Ошибка:", e)

    return {"ok": True}
