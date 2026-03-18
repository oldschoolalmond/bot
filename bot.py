import os
import asyncio
import aiosqlite
from fastapi import FastAPI, Request
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# === НАСТРОЙКИ ===
TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
GROUP_ID = os.getenv("GROUP_ID", "-100...") # ID вашей группы
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://your-app.up.railway.app")
DB_NAME = "bot_data.db" # База данных SQLite

bot = Bot(token=TOKEN)
dp = Dispatcher()
app = FastAPI()

# === БАЗА ДАННЫХ ===
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        # Таблица для разделов (топиков)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS topics (
                thread_id INTEGER PRIMARY KEY,
                name TEXT
            )
        """)
        # Таблица для запоминания, какой раздел выбрал юзер в личке
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_states (
                user_id INTEGER PRIMARY KEY,
                selected_thread_id INTEGER
            )
        """)
        await db.commit()

# === ЛОГИКА В ГРУППЕ (СБОР ТОПИКОВ) ===

# 1. Автоматический перехват создания нового топика
@dp.message(F.chat.id == int(GROUP_ID), F.forum_topic_created)
async def catch_new_topic(message: types.Message):
    topic_name = message.forum_topic_created.name
    thread_id = message.message_thread_id
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO topics (thread_id, name) VALUES (?, ?)", 
            (thread_id, topic_name)
        )
        await db.commit()
    await message.answer(f"🤖 Раздел «{topic_name}» автоматически добавлен в меню бота!")

# 2. Ручное добавление старых топиков (пишем /save_topic Имя раздела прямо в топике)
@dp.message(Command("save_topic"), F.chat.id == int(GROUP_ID))
async def save_existing_topic(message: types.Message):
    # Убираем команду из текста, оставляем только название
    topic_name = message.text.replace("/save_topic", "").strip()
    if not topic_name:
        await message.answer("Укажите название: /save_topic Название раздела")
        return
        
    thread_id = message.message_thread_id
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT OR REPLACE INTO topics (thread_id, name) VALUES (?, ?)", 
            (thread_id, topic_name)
        )
        await db.commit()
    await message.answer(f"✅ Раздел «{topic_name}» сохранен в базу!")

# === ЛОГИКА В ЛИЧНЫХ СООБЩЕНИЯХ (ПУБЛИКАЦИЯ) ===

# 1. Команда /start и вывод кнопок
@dp.message(CommandStart(), F.chat.type == "private")
async def cmd_start(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name FROM topics") as cursor:
            topics = await cursor.fetchall()
            
    if not topics:
        await message.answer("Разделы еще не добавлены. Админ должен добавить их в группе.")
        return

    # Создаем клавиатуру из базы данных
    buttons = [[KeyboardButton(text=row[0])] for row in topics]
    keyboard = ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)
    
    await message.answer("Выберите раздел, куда хотите отправить сообщение:", reply_markup=keyboard)

# 2. Обработка всех остальных текстовых сообщений и картинок в личке
@dp.message(F.chat.type == "private")
async def handle_private_message(message: types.Message):
    user_id = message.from_user.id
    text = message.text or message.caption or ""

    async with aiosqlite.connect(DB_NAME) as db:
        # Проверяем, не является ли текст названием топика (клик по кнопке)
        async with db.execute("SELECT thread_id FROM topics WHERE name = ?", (text,)) as cursor:
            topic = await cursor.fetchone()
            
        if topic:
            # Юзер выбрал топик - сохраняем его выбор
            thread_id = topic[0]
            await db.execute(
                "INSERT OR REPLACE INTO user_states (user_id, selected_thread_id) VALUES (?, ?)", 
                (user_id, thread_id)
            )
            await db.commit()
            await message.answer(f"✅ Выбран раздел: {text}\n\nТеперь отправьте сюда сообщение (текст, фото, видео), и я опубликую его в группе.")
            return

        # Если это не клик по кнопке раздела, значит юзер прислал контент для публикации
        async with db.execute("SELECT selected_thread_id FROM user_states WHERE user_id = ?", (user_id,)) as cursor:
            state = await cursor.fetchone()

    # Если раздел выбран - пересылаем контент
    if state:
        thread_id = state[0]
        try:
            # copy_message копирует любой тип контента: текст, фото, файлы
            await bot.copy_message(
                chat_id=GROUP_ID,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
                message_thread_id=thread_id
            )
            await message.answer("🚀 Успешно опубликовано!")
        except Exception as e:
            await message.answer(f"❌ Ошибка отправки (возможно, меня удалили из топика): {e}")
    else:
        await message.answer("⚠️ Сначала выберите раздел с помощью кнопок меню.")

# === FASTAPI ЗАПУСК И WEBHOOK ===

@app.on_event("startup")
async def on_startup():
    await init_db()
    await bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
    print("Бот запущен, вебхук установлен!")

@app.post("/webhook")
async def webhook_endpoint(request: Request):
    update = types.Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"status": "ok"}
