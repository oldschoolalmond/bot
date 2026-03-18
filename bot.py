import os
import aiosqlite
import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

load_dotenv()

# Настройки
TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
# Путь для Railway Volume (создайте Volume с Mount Path /app/data)
DB_PATH = "/app/data/bot_data.db" if os.path.exists("/app/data") else "bot_data.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS topics (thread_id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS user_states (user_id INTEGER PRIMARY KEY, thread_id INTEGER)")
        await db.commit()

# --- Регистрация топиков в группе ---
@dp.message(F.chat.id == GROUP_ID, Command("save_topic"))
async def save_topic(message: types.Message):
    name = message.text.replace("/save_topic", "").strip()
    if not name:
        return await message.answer("Использование: /save_topic Название")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO topics VALUES (?, ?)", (message.message_thread_id, name))
        await db.commit()
    await message.answer(f"✅ Раздел '{name}' добавлен!")

# --- Работа в личке ---
@dp.message(CommandStart(), F.chat.type == "private")
async def start_private(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM topics") as cursor:
            topics = await cursor.fetchall()
    
    if not topics:
        return await message.answer("Разделы еще не настроены админом в группе.")

    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t[0])] for t in topics], resize_keyboard=True)
    await message.answer("Выберите раздел для публикации:", reply_markup=kb)

@dp.message(F.chat.type == "private")
async def handle_msg(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        # Если нажата кнопка с названием топика
        async with db.execute("SELECT thread_id FROM topics WHERE name = ?", (message.text,)) as cursor:
            topic = await cursor.fetchone()
        
        if topic:
            await db.execute("INSERT OR REPLACE INTO user_states VALUES (?, ?)", (message.from_user.id, topic[0]))
            await db.commit()
            return await message.answer(f"👌 Ок, теперь всё, что вы напишете, отправится в '{message.text}'")

        # Если это просто сообщение — пересылаем
        async with db.execute("SELECT thread_id FROM user_states WHERE user_id = ?", (message.from_user.id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                await bot.copy_message(chat_id=GROUP_ID, from_chat_id=message.chat.id, 
                                       message_id=message.message_id, message_thread_id=row[0])
                await message.answer("🚀 Опубликовано!")
            else:
                await message.answer("Сначала выберите раздел кнопкой.")

# --- Webhook ---
@app.on_event("startup")
async def on_startup():
    await init_db()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", drop_pending_updates=True)

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
