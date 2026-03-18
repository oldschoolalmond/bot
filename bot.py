import os
import aiosqlite
import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
# ... остальные импорты ...

# 1. Сначала настройки
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID") or 0)
WEBHOOK_URL = os.getenv("WEBHOOK_URL")

# 2. Потом создание объектов (ВАЖНО!)
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# 3. И только ТЕПЕРЬ обработчики (твой дебаг-код)
@dp.message(F.chat.id == GROUP_ID)
async def debug_handler(message: types.Message):
    print(f"Got message from group! Text: {message.text}")
    # ... остальной код функции ...
