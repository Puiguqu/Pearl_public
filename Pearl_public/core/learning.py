import aiosqlite
import datetime
import logging

logging.basicConfig(level=logging.INFO)

DATABASE_NAME = "learning.db"

async def init_learning_db():
    """
    Creates (if needed) a table for storing user input.
    """
    async with aiosqlite.connect(DATABASE_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_input TEXT,
                timestamp TEXT
            )
        """)
        await db.commit()

async def store_user_input(chat_id: int, text: str):
    """
    Store the user's input text into the user_knowledge table.
    """
    try:
        timestamp = datetime.datetime.now().isoformat()
        async with aiosqlite.connect(DATABASE_NAME) as db:
            await db.execute(
                "INSERT INTO user_knowledge (chat_id, user_input, timestamp) VALUES (?, ?, ?)",
                (chat_id, text, timestamp)
            )
            await db.commit()
        logging.info(f"Learning module: Stored user input -> {text}")
    except Exception as e:
        logging.error(f"Error storing user input: {e}")

async def retrieve_all_user_input(chat_id: int):
    """
    Retrieve ALL user input stored for the given chat_id.
    """
    rows = []
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT user_input, timestamp FROM user_knowledge WHERE chat_id=? ORDER BY id ASC",
            (chat_id,)
        ) as cursor:
            async for row in cursor:
                rows.append(row)
    return rows

async def retrieve_recent_user_input(chat_id: int, limit: int = 5):
    """
    Retrieve only the N most-recent user inputs for the given chat_id.
    You might feed these back into the LLM for more context.
    """
    rows = []
    async with aiosqlite.connect(DATABASE_NAME) as db:
        async with db.execute(
            "SELECT user_input, timestamp FROM user_knowledge WHERE chat_id=? ORDER BY id DESC LIMIT ?",
            (chat_id, limit)
        ) as cursor:
            async for row in cursor:
                rows.append(row)
    # Because we used DESC in the query, reverse rows so the oldest is first
    return list(reversed(rows))
