import asyncio
import json
import logging
import importlib
from datetime import datetime
from typing import Any

# Third-party imports
import schedule

# Local imports
from config.telegram_settings import BOT_TOKEN, CHAT_ID
from core.modules_loader import available_functions
from core.telegram_receiver import TelegramClient
from core.ollama_integration import ask_ollama
from core.package_installer import install_package

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log")
    ]
)

def load_offset() -> Any:
    """Load the offset from a file."""
    try:
        with open(OFFSET_FILE, "r") as f:
            return json.load(f).get("offset", None)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def load_module(module_name: str, class_name: str) -> Any:
    """Load module class with validation."""
    spec = importlib.util.find_spec(module_name)
    if not spec:
        raise ImportError(f"Module {module_name} not found")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)
OFFSET_FILE = "offset.json"


TaskManager = load_module("modules.task_manager", "TaskManager")

async def execute_function(module_name: str, function_name: str, *args: Any, **kwargs: Any) -> Any:
    """Execute a function from loaded modules with enhanced error handling."""
    try:
        logging.info(f"🔎 Validating: {module_name}.{function_name}")
        functions = available_functions()
        
        # Validate function exists
        if module_name not in functions or function_name not in functions[module_name]:
            raise ValueError(f"Function {function_name} not found in {module_name}")

        # Import and get function
        module = importlib.import_module(f"modules.{module_name}")
        function = getattr(module, function_name, None)
        if not function:
            raise AttributeError(f"Could not load {function_name} from {module_name}")

        # Execute function and log result
        logging.info(f"⚡ Executing: {module_name}.{function_name}(*{args}, **{kwargs})")
        result = await function(*args, **kwargs) if asyncio.iscoroutinefunction(function) else function(*args, **kwargs)
        logging.info(f"✅ Success: {module_name}.{function_name} → {result}")
        return result

    except Exception as e:
        logging.error(f"❌ Error in {module_name}.{function_name}: {str(e)}")
        return f"Error: {str(e)}"


async def send_startup_greeting(telegram_client: TelegramClient, chat_id: int) -> None:
    """Send a startup greeting to the user."""
    prompt = (
        "You are PEARL - Personalized Efficient Assistant for Routine and Learning. "
        "Generate a unique and friendly startup greeting message for the bot. "
        "Tell the user about the bot's capabilities and how it can help them."
    )
    message = await ask_ollama(prompt)
    logging.info(f"Sending startup greeting to {chat_id}: {message}")
    await telegram_client.send_message(chat_id, message)

async def execute_command(command: str, *args, **kwargs) -> Any:
    """
    Parses a command string and executes the corresponding function.
    
    Expected command format:
        "execute:module_name.function_name"
    """
    logging.info(f"📌 Received execute command: {command}")
    
    if not command.startswith("execute:"):
        logging.error(f"❌ Invalid command format: {command}")
        return "Invalid command: missing 'execute:' prefix."
    
    try:
        command_body = command[len("execute:"):].strip()
        parts = command_body.split(".")
        
        if len(parts) != 2:
            logging.error(f"❌ Invalid function call format: {command_body}")
            return f"Invalid function call format: {command_body}"

        module_name, function_name = parts
        logging.info(f"📌 Extracted module: {module_name}, function: {function_name}")

        result = await execute_function(module_name, function_name, *args, **kwargs)
        logging.info(f"✅ Execution result: {result}")

        return result
    
    except Exception as e:
        logging.error(f"❌ Error parsing command '{command}': {e}")
        return f"Error parsing command: {e}"

async def main():
    telegram_client = None
    try:
        telegram_client = TelegramClient(BOT_TOKEN)
        await telegram_client.start()
        
        # Other initializations ...
        
        task_manager = TaskManager()
        await task_manager.initialize_db()
        await task_manager.load_tasks()
        
        chat_id = CHAT_ID
        await send_startup_greeting(telegram_client, chat_id)
        
        offset = load_offset()
        
        # Main update loop
        while True:
            updates = await telegram_client.get_updates(offset)
            for update in updates:
                await telegram_client.handle_update(update)
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1
                    save_offset(offset)
            await asyncio.sleep(1)
            
    except Exception as e:
        logging.error(f"❌ Fatal error: {e}")
    finally:
        if telegram_client:
            await telegram_client.stop()
        logging.info("✅ Shutdown complete")

if __name__ == "__main__":
    asyncio.run(main())