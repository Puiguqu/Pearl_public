# Standard library imports
import asyncio
import json
import logging
import importlib
from datetime import datetime
from typing import Any

# Third-party imports
import schedule
import httpx

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

OFFSET_FILE = "offset.json"
# Global command queue
command_queue = asyncio.Queue()


async def run_schedule():
    """Run scheduled tasks with rate limiting."""
    while True:
        try:
            schedule.run_pending()
            await asyncio.sleep(1)
        except Exception as e:
            logging.error(f"Schedule error: {e}")


def load_module(module_name: str, class_name: str) -> Any:
    """Load module class with validation."""
    spec = importlib.util.find_spec(module_name)
    if not spec:
        raise ImportError(f"Module {module_name} not found")
    module = importlib.import_module(module_name)
    return getattr(module, class_name)


# Initialize core components (for task management)
TaskManager = load_module("modules.task_manager", "TaskManager")


async def ensure_package_installed(package_name: str, chat_id: int, telegram_client: TelegramClient) -> bool:
    """Ensure package is installed with security validation."""
    # Package whitelist and aliases
    valid_packages = {
        "sklearn": "scikit-learn",
        "textblob": "textblob",
        "nltk": "nltk",
        "pandas": "pandas"
    }

    # Validate package name
    if package_name not in valid_packages:
        await telegram_client.send_message(chat_id, f"❌ Invalid package: {package_name}")
        return False

    # Get actual package name from alias
    actual_package = valid_packages[package_name]

    try:
        # Try importing first
        __import__(actual_package)
        logging.info(f"✅ Package {actual_package} already installed")
        return True
    except ImportError:
        # Install if missing
        await telegram_client.send_message(chat_id, f"📦 Installing {actual_package}...")
        await install_package(actual_package, chat_id, telegram_client)
        return True
    except Exception as e:
        logging.error(f"❌ Error with {actual_package}: {e}")
        return False


def load_offset() -> Any:
    """Load the offset from a file."""
    try:
        with open(OFFSET_FILE, "r") as f:
            return json.load(f).get("offset", None)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def save_offset(offset: int) -> None:
    """Save the offset to a file."""
    with open(OFFSET_FILE, "w") as f:
        json.dump({"offset": offset}, f)


import asyncio
import importlib
import logging
from typing import Any

async def execute_function(module_name: str, function_name: str, *args: Any, telegram_client: "TelegramClient" = None, chat_id: int = None, **kwargs: Any) -> Any:
    """
    Executes a function from the dynamically updated list of available functions.
    If the function is not found, logs an error and notifies via telegram if telegram_client and chat_id are provided.
    """
    # Ensure functions update dynamically
    functions = available_functions()
    
    if module_name not in functions or function_name not in functions[module_name]:
        available_funcs = ", ".join(functions.get(module_name, []))
        error_msg = f"❌ Error: Function `{function_name}` not found in `{module_name}`. Try one of: {available_funcs}"
        logging.error(error_msg)
        if telegram_client is not None and chat_id is not None:
            await telegram_client.send_message(chat_id, text=error_msg)
        return None  # Ensure a return value

    try:
        logging.info(f"🔍 Attempting to import module: modules.{module_name}")
        module = importlib.import_module(f"modules.{module_name}")
        
        logging.info(f"✅ Successfully imported: {module_name}")

        function = getattr(module, function_name, None)
        if not function:
            raise AttributeError(f"Could not load function `{function_name}` from module `{module_name}`")

        logging.info(f"⚡ Executing: {module_name}.{function_name}(*{args}, **{kwargs})")

        # Check if function is async or sync
        if asyncio.iscoroutinefunction(function):
            result = await function(*args, **kwargs)
        else:
            result = function(*args, **kwargs)

        logging.info(f"✅ Success: {module_name}.{function_name} → {result}")
        return result  # Ensure result is always returned

    except ModuleNotFoundError:
        error_msg = f"❌ Module `{module_name}` not found. Ensure it is correctly installed and accessible."
        logging.error(error_msg)
        if telegram_client and chat_id:
            await telegram_client.send_message(chat_id, text=error_msg)
        return None

    except AttributeError as e:
        error_msg = f"❌ Error: {str(e)}"
        logging.error(error_msg)
        if telegram_client and chat_id:
            await telegram_client.send_message(chat_id, text=error_msg)
        return None

    except Exception as e:
        error_msg = f"❌ Unexpected error in `{module_name}.{function_name}`: {str(e)}"
        logging.error(error_msg)
        if telegram_client and chat_id:
            await telegram_client.send_message(chat_id, text=error_msg)
        return None



# A helper function to parse a command string and execute the corresponding function:
async def execute_command(command: str, *args, **kwargs) -> Any:
    """
    Parse a command string and execute the corresponding function.
    
    Expected command format:
        "execute:module_name.function_name"
    """
    logging.info(f"📌 Received execute command: {command}")
    
    if not command.startswith("execute:"):
        logging.error(f"❌ Invalid command format: {command}")
        return "Invalid command: missing 'execute:' prefix."
    
    try:
        # Remove the "execute:" prefix and split by '.'
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


async def process_ai_response(telegram_client: TelegramClient, chat_id: int, response: str) -> None:
    """Process AI response and execute function if applicable."""
    try:
        logging.info(f"🧠 AI Response Received: {response}")

        # Remove any prefix if present
        if response.startswith("Executing action:"):
            response = response.replace("Executing action:", "").strip()

        # Check if response indicates a function execution
        if response.startswith("execute:"):
            parts = response.replace("execute:", "").strip().split(".")
            if len(parts) == 2:
                module_name, function_name = parts
                logging.info(f"📌 AI Command Received: {module_name}.{function_name}")

                # Execute the function and log its result
                result = await execute_function(module_name, function_name)
                logging.info(f"✅ AI Execution Result: {result}")
                await telegram_client.send_message(chat_id, f"Executed {function_name}: {result}")
            else:
                logging.warning("⚠️ Invalid function call format received from AI")
                await telegram_client.send_message(chat_id, "Invalid function call format.")
        else:
            await telegram_client.send_message(chat_id, response)

    except Exception as e:
        logging.error(f"❌ Error processing AI response: {e}")
        await telegram_client.send_message(chat_id, "Error processing AI response.")


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


async def send_daily_greeting(telegram_client: TelegramClient, chat_id: int) -> None:
    """Send a daily greeting to the user at 7:30 AM."""
    prompt = (
        "You are PEARL - Personalized Efficient Assistant for Routine and Learning. "
        "Generate a unique and cheerful morning greeting message for the user."
    )
    message = await ask_ollama(prompt)
    logging.info(f"Sending daily greeting to {chat_id}: {message}")
    await telegram_client.send_message(chat_id, message)


def schedule_daily_greeting(telegram_client: TelegramClient, chat_id: int) -> None:
    """Schedule the daily greeting at 7:30 AM."""
    schedule.every().day.at("07:30").do(
        lambda: asyncio.create_task(send_daily_greeting(telegram_client, chat_id))
    )


async def check_required_packages(telegram_client: TelegramClient) -> None:
    """Ensure all required packages are installed."""
    required_packages = {
        "sklearn": "For machine learning capabilities",
        "textblob": "For natural language processing",
        "nltk": "For text analysis",
        "pandas": "For data handling"
    }
    
    for package, purpose in required_packages.items():
        logging.info(f"🔍 Checking {package} ({purpose})")
        await ensure_package_installed(package, CHAT_ID, telegram_client)


async def function_executor():
    """
    Continuously checks the command queue and executes commands.
    """
    logging.info("Function Executor started.")
    while True:
        # Wait for a command to be available in the queue
        if not command_queue.empty():
            command = await command_queue.get()
            result = await execute_command(command)
            await command_queue.put(command)
            logging.info(f"🔧 Re-queued command: {command}")

        logging.info(f"Function Executor: Received command: {command}")
        logging.info("✅ Function Executor is running...")
        logging.info(f"📌 Commands in queue: {command_queue.qsize()}")

        try:
            result = await execute_command(command)
            await command_queue.put(command)
            logging.info(f"Function Executor: Command '{command}' executed with result: {result}")
            # Optionally, you might want to notify the user about the result using your telegram_client.
        except Exception as e:
            logging.error(f"Function Executor: Error executing command '{command}': {e}")
        finally:
            command_queue.task_done()
        await asyncio.sleep(1)  # Add a small delay to prevent tight loop

async def command_execute(command: str, *args, **kwargs) -> Any:
    """
    Immediately execute a command string.
    
    Expected command format:
        "execute:module_name.function_name"
    """
    logging.info(f"📌 Received immediate execute command: {command}")
    
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
        logging.info(f"✅ Immediate execution result: {result}")

        return result
    
    except Exception as e:
        logging.error(f"❌ Error parsing command '{command}': {e}")
        return f"Error parsing command: {e}"

async def execute_command_immediately(command: str) -> Any:
    """
    Immediately executes the given command without using a queue.
    The command should be in the format: execute:module.function.
    """
    logging.info(f"Immediate Execution: Received command: {command}")
    try:
        # Execute the command directly without queueing
        result = await execute_command(command)
        logging.info(f"Immediate Execution: Command '{command}' executed with result: {result}")
        return result
    except Exception as e:
        logging.error(f"Immediate Execution: Error executing command '{command}': {e}")
        return f"Error executing command: {e}"

from core.learning import init_learning_db

async def main():
    telegram_client = None
    try:

        await init_learning_db()

        # Initialize Telegram client and start it
        telegram_client = TelegramClient(BOT_TOKEN)
        await telegram_client.start()
        
        offset = load_offset()
        
        # Run scheduled tasks concurrently
        asyncio.create_task(run_schedule())
        
        # Ensure required packages are installed
        await check_required_packages(telegram_client)
        
        # Initialize Task Manager and load tasks
        task_manager = TaskManager()
        await task_manager.initialize_db()
        await task_manager.load_tasks()
        
        chat_id = CHAT_ID
        
        # Send startup greeting and schedule daily greeting
        await send_startup_greeting(telegram_client, chat_id)
        schedule_daily_greeting(telegram_client, chat_id)
        
        # Load offset for update polling
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