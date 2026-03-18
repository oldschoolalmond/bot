from fastapi import FastAPI, Request
import httpx
import os
from dotenv import load_dotenv

# Загружаем токен и ID группы из .env
load_dotenv()
TOKEN = os.getenv("TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

app = FastAPI()

@app.post("/bot")
async def telegram_webhook(req: Request):
    data = await req.json()
    if "message" in data:
        text = data["message"].get("text")
        if text:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {"chat_id": GROUP_ID, "text": text}
            async with httpx.AsyncClient() as client:
                await client.post(url, data=payload)
    return {"ok": True}
