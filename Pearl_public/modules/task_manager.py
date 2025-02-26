import datetime
import heapq
import logging
import asyncio
import aiosqlite

logging.basicConfig(level=logging.DEBUG)


class TaskManager:
    def __init__(self, db_path="tasks.db"):
        self.db_path = db_path
        self.tasks = {}
        self.reminders = []  # Min-heap to manage reminder timings
        self.lock = asyncio.Lock()

    async def initialize_db(self):
        """
        Initialize the database to store tasks and reminders.
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    description TEXT,
                    due_datetime TEXT,
                    created_at TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS reminders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER,
                    reminder_time TEXT,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                )
            """)
            await db.commit()

    async def load_tasks(self):
        """
        Load tasks and reminders from the database into memory.
        """
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT * FROM tasks") as cursor:
                async for row in cursor:
                    task_id = row[0]
                    self.tasks[task_id] = {
                        "name": row[1],
                        "description": row[2],
                        "due_datetime": datetime.datetime.fromisoformat(row[3]),
                        "created_at": datetime.datetime.fromisoformat(row[4]),
                    }

            async with db.execute("SELECT * FROM reminders") as cursor:
                async for row in cursor:
                    reminder_time = datetime.datetime.fromisoformat(row[2])
                    task_id = row[1]
                    heapq.heappush(self.reminders, (reminder_time, task_id))

        logging.info("Loaded tasks and reminders from the database.")

    async def create_task(self, name, description, due_datetime):
        """
        Create a new task and schedule reminders.

        Args:
            name (str): The name of the task.
            description (str): A brief description of the task.
            due_datetime (datetime): The due date and time of the task.

        Returns:
            int: The task ID.
        """
        async with aiosqlite.connect(self.db_path) as db:
            created_at = datetime.datetime.now().isoformat()
            due_datetime_str = due_datetime.isoformat()

            # Insert task into the database
            cursor = await db.execute("""
                INSERT INTO tasks (name, description, due_datetime, created_at)
                VALUES (?, ?, ?, ?)
            """, (name, description, due_datetime_str, created_at))
            task_id = cursor.lastrowid
            await db.commit()

        self.tasks[task_id] = {
            "name": name,
            "description": description,
            "due_datetime": due_datetime,
            "created_at": datetime.datetime.now(),
        }

        # Schedule reminders
        await self.schedule_reminders(task_id, due_datetime)
        logging.info(f"Task created: {self.tasks[task_id]}")
        return task_id

    async def schedule_reminders(self, task_id, due_datetime):
        """Schedule reminders for a task."""
        now = datetime.datetime.now()
        reminder_intervals = [
            datetime.timedelta(days=1),
            datetime.timedelta(hours=12),
            datetime.timedelta(minutes=30),
            datetime.timedelta(minutes=0)  # At due time
        ]

        # Generate reminder times
        reminders = [
            (due_datetime - interval, task_id)
            for interval in reminder_intervals
        ]

        # Filter out past reminders
        valid_reminders = [(t, tid) for t, tid in reminders if t > now]

        async with aiosqlite.connect(self.db_path) as db:
            # Clear existing reminders
            await db.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
            
            # Add new reminders
            for reminder_time, task_id in valid_reminders:
                heapq.heappush(self.reminders, (reminder_time, task_id))
                await db.execute(
                    "INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
                    (task_id, reminder_time.isoformat())
                )
            await db.commit()

        logging.info(f"Scheduled {len(valid_reminders)} reminders for Task {task_id}")
        return len(valid_reminders)

    async def reminder_scheduler(self, send_reminder_callback):
        """
        Continuously check for reminders and execute the callback when it's time.

        Args:
            send_reminder_callback (callable): Function to call when a reminder is due.
        """
        while True:
            now = datetime.datetime.now()

            if not self.reminders:
                await self.load_tasks()  # Refresh reminders periodically
                sleep_time = 60  # If no reminders, check every minute
            else:
                next_reminder_time, task_id = self.reminders[0]
                sleep_time = max((next_reminder_time - now).total_seconds(), 1)

            await asyncio.sleep(sleep_time)

            while self.reminders and self.reminders[0][0] <= datetime.datetime.now():
                reminder_time, task_id = heapq.heappop(self.reminders)
                task = self.tasks.get(task_id, None)
                if task:
                    message = f"Task '{task['name']}' is due! ⏳"
                    await send_reminder_callback(task_id, message)

    async def list_tasks(self):
        """
        List all tasks.

        Returns:
            str: A formatted string of all tasks.
        """
        if not self.tasks:
            return "No tasks found."

        tasks = "\n".join(
            f"{task_id}: {task['name']} (Due: {task['due_datetime']})"
            for task_id, task in self.tasks.items()
        )
        return f"Your tasks:\n{tasks}"

    async def delete_task(self, task_id):
        """
        Delete a task and its reminders.

        Args:
            task_id (int): The ID of the task to delete.

        Returns:
            str: Status message with emoji.
        """
        if task_id in self.tasks:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
                await db.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
                await db.commit()

            # Remove from memory
            del self.tasks[task_id]

            # Update reminder heap
            self.reminders = [(r, t) for r, t in self.reminders if t != task_id]
            heapq.heapify(self.reminders)

            logging.info(f"Task {task_id} and its reminders deleted.")
            return f"✅ Task {task_id} deleted successfully."
        
        return f"❌ Task {task_id} not found."

    async def cleanup_overdue_tasks(self):
        """
        Periodically delete tasks whose due date has passed.
        """
        while True:
            now = datetime.datetime.now()
            overdue_task_ids = [
                task_id for task_id, task in self.tasks.items()
                if task["due_datetime"] < now
            ]

            for task_id in overdue_task_ids:
                await self.delete_task(task_id)
                logging.info(f"Deleted overdue task {task_id}")

            # Run the cleanup every hour
            await asyncio.sleep(3600)

    async def update_task(self, task_id, name=None, description=None, due_datetime=None):
        """Update an existing task."""
        if task_id not in self.tasks:
            return "Task not found."

        async with aiosqlite.connect(self.db_path) as db:
            update_fields = []
            params = []

            if name:
                update_fields.append("name = ?")
                params.append(name)
                self.tasks[task_id]["name"] = name

            if description:
                update_fields.append("description = ?")
                params.append(description)
                self.tasks[task_id]["description"] = description

            if due_datetime:
                update_fields.append("due_datetime = ?")
                params.append(due_datetime.isoformat())
                self.tasks[task_id]["due_datetime"] = due_datetime
                # Update reminders
                await db.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
                await db.execute(
                    "INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
                    (task_id, due_datetime.isoformat())
                )

            if update_fields:
                query = f"UPDATE tasks SET {', '.join(update_fields)} WHERE id = ?"
                params.append(task_id)
                await db.execute(query, params)
                await db.commit()
                return f"Task {task_id} updated successfully."
            
            return "No updates provided."

    async def send_reminder(self, task_id, message):
        """Send reminder notification via Telegram."""
        from core.telegram_receiver import send_message
        from config.telegram_settings import CHAT_ID
        
        task = self.tasks.get(task_id)
        if task:
            due_time = task["due_datetime"].strftime("%Y-%m-%d %H:%M")
            formatted_message = (
                f"🔔 Reminder: {message}\n"
                f"📝 Task: {task['name']}\n"
                f"⏰ Due: {due_time}"
            )
            await send_message(CHAT_ID, formatted_message)
