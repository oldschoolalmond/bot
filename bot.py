import os
import aiosqlite
import uvicorn
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from dotenv import load_dotenv

# 1. ЗАГРУЗКА НАСТРОЕК (Важно: сначала это!)
load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
# Если GROUP_ID не подтянется, бот не упадет, а выдаст 0 (но лучше проверь в Railway)
try:
    GROUP_ID = int(os.getenv("GROUP_ID"))
except:
    GROUP_ID = 0

WEBHOOK_URL = os.getenv("WEBHOOK_URL")
DB_PATH = "/app/data/bot_data.db" if os.path.exists("/app/data") else "bot_data.db"

# 2. СОЗДАНИЕ ОБЪЕКТОВ
bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# 3. ФУНКЦИИ И ОБРАБОТЧИКИ
async def init_db():
    if not os.path.exists("/app/data") and "/app/data" in DB_PATH:
        os.makedirs("/app/data", exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS topics (thread_id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS user_states (user_id INTEGER PRIMARY KEY, thread_id INTEGER)")
        await db.commit()

@dp.message(F.chat.id == GROUP_ID, Command("save_topic"))
async def save_topic(message: types.Message):
    name = message.text.replace("/save_topic", "").strip()
    if name:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO topics VALUES (?, ?)", (message.message_thread_id, name))
            await db.commit()
        await message.answer(f"✅ Section '{name}' added.")

@dp.message(CommandStart(), F.chat.type == "private")
async def start_private(message: types.Message):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT name FROM topics") as cursor:
            topics = await cursor.fetchall()
    
    if not topics:
        return await message.answer("No sections found. Admin must set them up in the group first.")

    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=t[0])] for t in topics], resize_keyboard=True)
    await message.answer("Please select a section for your post:", reply_markup=kb)

@dp.message(F.chat.type == "private")
async def handle_msg(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT thread_id FROM topics WHERE name = ?", (message.text,)) as cursor:
            topic = await cursor.fetchone()
        
        if topic:
            await db.execute("INSERT OR REPLACE INTO user_states VALUES (?, ?)", (user_id, topic[0]))
            await db.commit()
            return await message.answer(f"✅ Target: {message.text}\nSend your message.")

        async with db.execute("SELECT thread_id FROM user_states WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
    if row:
        try:
            # СТАРЫЙ ДОБРЫЙ МЕТОД (Copy)
            await bot.copy_message(
                chat_id=GROUP_ID, 
                from_chat_id=message.chat.id, 
                message_id=message.message_id, 
                message_thread_id=row[0]
            )
            await message.answer("🚀 Published!")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")

# 4. ЗАПУСК И ВЕБХУК
@app.on_event("startup")
async def on_startup():
    await init_db()
    # Указываем /webhook, чтобы не было 404
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook", drop_pending_updates=True)

@app.post("/webhook")
async def webhook(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8000)))
