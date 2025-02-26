import asyncio
import logging
from core.ollama_integration import ask_ollama
from core.function_executor import execute_command
from core.telegram_receiver import TelegramClient
from config.telegram_settings import BOT_TOKEN, CHAT_ID

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Initialize global command queue
command_queue = asyncio.Queue()

async def process_user_input(chat_id: int, user_input: str, telegram_client: TelegramClient):
    """Process user input by sending it to Ollama, determining execution, and handling responses."""
    logging.info(f"📩 Processing user input from chat_id {chat_id}: {user_input}")
    response = await ask_ollama(user_input)
    
    if response.startswith("execute:"):
        await command_queue.put(response.strip())
        await telegram_client.send_message(chat_id, f"🛠 Command queued: {response.strip()}")
    else:
        await telegram_client.send_message(chat_id, response)

async def function_executor():
    """Continuously process commands from the queue and execute them."""
    logging.info("⚡ Function Executor started.")
    while True:
        command = await command_queue.get()
        logging.info(f"🔧 Executing command: {command}")
        try:
            result = await execute_command(command)
            high_level_response = await ask_ollama(f"Confirm execution and summarize results: {result}")
            logging.info(f"✅ Execution result: {high_level_response}")
        except Exception as e:
            logging.error(f"❌ Error executing command '{command}': {e}")
            high_level_response = f"Error: {e}"
        finally:
            await telegram_client.send_message(CHAT_ID, high_level_response)
            command_queue.task_done()

async def main():
    """Main function handling Telegram input, Ollama processing, and function execution."""
    telegram_client = TelegramClient(BOT_TOKEN)
    await telegram_client.start()
    
    # Start function executor
    asyncio.create_task(function_executor())
    
    while True:
        updates = await telegram_client.get_updates()
        for update in updates:
            await telegram_client.handle_update(user_input=update["message"])
        await asyncio.sleep(1)

if __name__ == "__main__":
    asyncio.run(main())
