import logging
import re
import json
from main import execute_command_immediately, execute_function
from core.modules_loader import available_functions
from core.ollama_integration import ask_ollama

async def process_user_input(chat_id: int, user_input: str, telegram_client) -> None:
    """
    Process user input and determine the best response or function to execute.

    - If execution is required, AI must return: `execute:module.function
    - If no execution is required, AI must return a brief response.
    - The function ensures AI only selects functions that exist.
    """
    
    logging.info(f"📩 Processing user input from chat_id {chat_id}: {user_input}")

    # Dynamically fetch available functions to ensure AI picks valid ones
    functions = available_functions()
    
    # Generate a strict AI prompt using the user input as the topic (i.e. query)
    functions = available_functions()

    prompt = f"""
SYSTEM: You are PEARL, an AI assistant responsible for executing predefined functions based on user requests.
Your job is to analyze the user input and determine whether a function needs to be executed.
You must **always prioritize internal functions** and **only use `internet_search` as a last resort**.


### RULES:
- **Check for available functions before considering `internet_search`.**
- **If a function is relevant, execute it immediately.**
- **If multiple functions match, select the most appropriate one.**
- **If user input does not require execution, provide a concise natural response.**
- **DO NOT create or guess function names; ONLY use existing ones.**
- **DO NOT select `main()` as it is NOT an executable function.**
- ** if 'news' is stated in the user_input, execute the search_news function from the internet_search module.**
- ** if 'research' is stated in the user_input, execute the conduct_research function from the research module.**

if function doesnt require execution, reply in a friendly manner.
answer any questions or provide information to the best of your ability without making things up.
avoid comentary 
use internet_search as a last resort
play indicates play_pause function unless stated otherwise
if user asks for new function use the self_editor module
self_editor = PearlSelfEditor(repo_path)
await self_editor.self_modify(user_input)

### USER INPUT:
{user_input}

### AVAILABLE FUNCTIONS:
{json.dumps(available_functions(), indent=2)}

### RESPONSE FORMAT:
- **If execution is required:** `execute:module.function`
- **If no execution is needed:** A brief natural language response.
-
Now determine the best response.
"""



    from main import execute_function
    from modules.notification import handle_user_request as handle_notifier
    # Get AI response
    response = await ask_ollama(prompt)
    logging.info(f"🧠 AI Response: {response}")

    # Process the AI response ensuring it follows the strict format
    if response.startswith("execute:"):
        parts = response.replace("execute:", "").strip().split(".")
        if len(parts) == 2:
            module_name, function_name = parts

            # Validate function existence before execution
            available_funcs = available_functions()
            if module_name in available_funcs and function_name in available_funcs[module_name]:
                logging.info(f"⚡ Executing: {module_name}.{function_name}")

                try:
                    # Pass user_input as the required argument for functions that need it
                    if module_name == "internet_search" and function_name == "search_news":
                        result = await execute_function(module_name, function_name, query=user_input)
                    elif module_name == "research" and function_name == "conduct_research":
                        result = await execute_function(module_name, function_name, topic=user_input)
                    elif module_name == "spotify"  and function_name == "play_pause":
                        result = await execute_function(module_name, function_name)
                    elif module_name == "self_editor" and function_name == "self_modify":
                        result = await execute_function(module_name, function_name, user_input)              
                    elif module_name == "generated_unnamed" and function_name == "async_count":
                        result = await execute_function(module_name, function_name, user_input)
                    elif module_name == "notification" and function_name == "parse_notification_request":
                        result = await execute_function(handle_notifier, chat_id, user_input)
                    logging.info(f"✅ Execution Result: {result}")
                    await telegram_client.send_message(chat_id, f" {function_name} executed successfully: {result}")
                except Exception as e:
                    logging.error(f"❌ Error executing {module_name}.{function_name}: {e}")
                    await telegram_client.send_message(chat_id, f"❌ Failed to execute {function_name}. Error: {str(e)}")
            else:
                logging.warning(f"⚠️ Function {function_name} not found in {module_name}")
                await telegram_client.send_message(chat_id, f"⚠️ I couldn't find a matching function for that request.")
    else:
        await telegram_client.send_message(chat_id, response.strip())
