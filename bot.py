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
# Путь для Railway Volume (убедись, что создала Volume в панели Railway)
DB_PATH = "/app/data/bot_data.db" if os.path.exists("/app/data") else "bot_data.db"

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS topics (thread_id INTEGER PRIMARY KEY, name TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS user_states (user_id INTEGER PRIMARY KEY, thread_id INTEGER)")
        await db.commit()

# --- Логика в группе (Регистрация разделов) ---
@dp.message(F.chat.id == GROUP_ID, Command("save_topic"))
async def save_topic(message: types.Message):
    name = message.text.replace("/save_topic", "").strip()
    if not name:
        return await message.answer("Usage: /save_topic Section Name")
    
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO topics VALUES (?, ?)", (message.message_thread_id, name))
        await db.commit()
    await message.answer(f"✅ Section '{name}' linked successfully.")

# --- Логика в личке (Интерфейс на английском) ---
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
        # Проверяем выбор раздела кнопкой
        async with db.execute("SELECT thread_id FROM topics WHERE name = ?", (message.text,)) as cursor:
            topic = await cursor.fetchone()
        
        if topic:
            await db.execute("INSERT OR REPLACE INTO user_states VALUES (?, ?)", (user_id, topic[0]))
            await db.commit()
            return await message.answer(f"✅ Target: **{message.text}**\n\nSend your message now.")

        # Получаем текущий выбранный раздел юзера
        async with db.execute("SELECT thread_id FROM user_states WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            
    if row:
        thread_id = row[0]
        try:
            # АЛЬТЕРНАТИВНЫЙ МЕТОД: Отправляем как новое сообщение
            if message.text:
                await bot.send_message(chat_id=GROUP_ID, text=message.text, message_thread_id=thread_id)
            elif message.photo:
                await bot.send_photo(chat_id=GROUP_ID, photo=message.photo[-1].file_id, caption=message.caption, message_thread_id=thread_id)
            elif message.video:
                await bot.send_video(chat_id=GROUP_ID, video=message.video.file_id, caption=message.caption, message_thread_id=thread_id)
            elif message.document:
                await bot.send_document(chat_id=GROUP_ID, document=message.document.file_id, caption=message.caption, message_thread_id=thread_id)
            else:
                # Если тип сложный, используем copy (но анонимность должна быть вкл в ТГ)
                await bot.copy_message(chat_id=GROUP_ID, from_chat_id=message.chat.id, message_id=message.message_id, message_thread_id=thread_id)
            
            await message.answer("🚀 Published successfully!")
        except Exception as e:
            await message.answer(f"❌ Error: {e}")
    else:
        await message.answer("⚠️ Select a section first.")

# --- Fast API & Webhook ---
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
