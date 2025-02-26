import asyncio
import logging
from core.modules_loader import available_functions
from core.ollama_integration import jarvis_prompt, ask_ollama, process_ai_response
from core.telegram_receiver import TelegramClient
from config.telegram_settings import CHAT_ID, BOT_TOKEN
from main import execute_function
import httpx
import aiohttp

# Configure logging
logging.basicConfig(level=logging.DEBUG)
Telegram_client = TelegramClient(BOT_TOKEN)

# Modify the function signature to provide default values so it can be executed without errors.
async def handle_conversation(user_input: str = "", chat_id: int = 0) -> None:
    """
    Processes user input and determines an appropriate response or function execution.
    When called without parameters, uses default empty input and chat_id 0.
    """
    logging.info(f"📩 Handling conversation for chat_id {chat_id}: {user_input}")

    if Telegram_client.session is None or Telegram_client.session.closed:
        logging.warning("🔄 TelegramClient session was not initialized. Restarting session.")
        await Telegram_client.start()

    functions = available_functions()
    prompt = (
         f"SYSTEM: You are PEARL, an AI assistant.\n\n"
         f"USER INPUT: {user_input}\n\n"
         f"AVAILABLE FUNCTIONS:\n{functions}\n\n"
         f"Determine the best response or function execution.\n"
         f"if no execution is requred return a friendly response."
         f"answer any questions or provide information to the best of your ability without making things up."
         f"If execution is required, return 'execute:module.function'. Otherwise, return a direct response in natural language."
    )

    response = await ask_ollama(prompt)
    response = response.strip() if response.strip() else "I'm not sure how to respond to that."

    # Process potential function execution commands from AI
    if response.startswith("execute:"):
        try:
            module_name, function_name = response.replace("execute:", "").strip().split(".")
            logging.info(f"📌 AI Command Received: {module_name}.{function_name}")
            
            # Execute function
            if module_name == "internet_search" and function_name == "search_news":
                result = await execute_function(module_name, function_name, query=user_input)
            elif module_name == "research" and function_name == "conduct_research":
                result = await execute_function(module_name, function_name, topic=user_input)
            else:
                result = await execute_function(module_name, function_name)

            logging.info(f"✅ AI Execution Result: {result}")

            if not chat_id:
                from config.telegram_settings import CHAT_ID
                chat_id = CHAT_ID

            # ✅ Prevent sending "Executed ... : None"
            if result and str(result).strip().lower() != "none":
                await Telegram_client.send_message(chat_id, text=f"Executed {function_name}: {result}")

        except Exception as e:
            logging.error(f"❌ Error executing command from AI response: {e}")
            if not chat_id:
                from config.telegram_settings import CHAT_ID
                chat_id = CHAT_ID
            await Telegram_client.send_message(chat_id, text="Error executing command.")
    else:
        # Use default CHAT_ID if chat_id is falsy
        if not chat_id:
            from config.telegram_settings import CHAT_ID
            chat_id = CHAT_ID
        if chat_id and response.strip():
            await Telegram_client.send_message(chat_id, text=response)
        else:
            logging.warning("⚠️ Missing chat_id or text. Message not sent.")
