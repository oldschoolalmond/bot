# Замени этот блок в main.py:
@dp.message(F.chat.id == GROUP_ID)
async def debug_handler(message: types.Message):
    print(f"Got message from group! Text: {message.text}") # Это появится в логах Railway
    if message.text and "/save_topic" in message.text:
        name = message.text.replace("/save_topic", "").strip()
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO topics VALUES (?, ?)", (message.message_thread_id, name))
            await db.commit()
        await message.answer(f"✅ Debug: Saved {name} in thread {message.message_thread_id}")
