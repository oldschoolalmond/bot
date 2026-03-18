from fastapi import FastAPI, Request
import httpx
import os

TOKEN = os.getenv("TOKEN")

app = FastAPI()

@app.get("/")
async def root():
    return {"status": "ok"}

@app.post("/bot")
async def telegram_webhook(req: Request):
    try:
        data = await req.json()
        print(data)

        if "message" in data:
            text = data["message"].get("text")
            chat_id = data["message"]["chat"]["id"]

            if text:
                url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

                async with httpx.AsyncClient() as client:
                    await client.post(url, json={
                        "chat_id": chat_id,
                        "text": f"Ты написал: {text}"
                    })

        return {"ok": True}

    except Exception as e:
        print("ERROR:", e)
        return {"error": str(e)}
