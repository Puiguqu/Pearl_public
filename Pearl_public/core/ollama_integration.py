import logging
import asyncio
import re
import ollama
from datetime import datetime
from core.modules_loader import available_functions
from core.time_calendar import provide_datetime_context
from config.telegram_settings import CHAT_ID as chat_id
from core.telegram_receiver import TelegramClient

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Dictionaries for conversation history
conversation_history = {}
conversation_topics = {}

def jarvis_prompt(user_input, functions_by_module):
    """Generate an optimized prompt for PEARL based on user input and available functions."""
    try:
        logging.debug(f"Generating prompt for: {user_input}")
        functions = functions_by_module()
        datetime_context = provide_datetime_context()

        function_list = "\n".join(
            f"{module}:\n" + "\n".join(f"  - {func}" for func in funcs)
            for module, funcs in functions.items()
        )

        if "module" in user_input.lower() or "function" in user_input.lower():
            return (
                "SYSTEM: You are PEARL - Personalized Efficient Assistant for Routine and Learning.\n"
                f"CONTEXT:\n{datetime_context}\n\n"
                f"INPUT: {user_input}\n\n"
                "INSTRUCTIONS:\n"
                "1. If the user asks about available modules, list them directly.\n"
                "2. If the user asks whether a module exists, respond with Yes/No.\n"
                "3. Only execute a function if the user explicitly requests an action.\n\n"
                f"AVAILABLE FUNCTIONS:\n{function_list}"
            )

        prompt = f"""
SYSTEM: You are PEARL - Personalized Efficient Assistant for Routine and Learning.
Your primary role is to efficiently assist the user by executing predefined functions when necessary.
You should always prioritize internal functions over internet search.

### CONTEXT:
- **Current Date & Time:** {provide_datetime_context()}
- **Conversation History (last 5 messages):** {conversation_history.get(chat_id, [])}

### RULES:
1. **Prioritize available functions before external searches.**
2. **NEVER use `internet_search` unless the user explicitly requests news, research, or external information.**
3. **If a relevant function exists, execute it.**
4. **If multiple functions match, pick the best one based on user intent.**
5. **If no function is needed, provide a short, direct response.**
6. **Maintain conversation context and recognize topic shifts.**
7. **DO NOT execute functions that do not exist.**

### USER INPUT:
{user_input}

### AVAILABLE FUNCTIONS:
{json.dumps(available_functions(), indent=2)}

### RESPONSE FORMAT:
- **Execution required:** `execute:module.function`
- **No execution needed:** A brief response.

Determine the best course of action.
"""

        logging.debug(f"Generated Jarvis Prompt: {prompt}")
        return prompt

    except Exception as e:
        logging.error(f"Error in prompt generation: {e}")
        return "Error generating prompt."

def extract_function_call(response):
    """Extract function calls from AI response."""
    match = re.search(r"execute:(\w+)\.(\w+)(?:\((.*?)\))?", response)
    if match:
        module_name, function_name, args = match.groups()
        args = [arg.strip() for arg in args.split(",")] if args else []
        return module_name, function_name, args
    return None

async def ask_ollama(prompt, model="llama3.2", chat_id=None):
    """Ensures PEARL only sends clean responses and prevents backend logs from being sent."""
    try:
        logging.debug(f"Sending prompt to LLM: {prompt}")
        client = ollama.Client()

        history = conversation_history.get(chat_id, [])
        history.append(f"User: {prompt}")
        conversation_context = "\n".join(history[-5:])  # Keep last 5 interactions

        response = client.generate(model=model, prompt=conversation_context)
        output = response.get("response", "").strip()

        cleaned_output = re.sub(r"(Process User Input:|Received data from|Sending request to).*", "", output, flags=re.IGNORECASE).strip()
        cleaned_output = re.sub(r"(Next Steps:|Context:).*", "", cleaned_output, flags=re.IGNORECASE).strip()

        if "internet_search" in prompt.lower():
            cleaned_output = cleaned_output.replace("Title:", "**News Update:**\n**Title:**")
            cleaned_output = cleaned_output.replace("Summary:", "\n**Summary:**")
            cleaned_output = cleaned_output.replace("Latest Updates:", "\n**Latest Updates:**")

        logging.info(f"📌 Sending response to user: {cleaned_output}")
        return cleaned_output

    except Exception as e:
        logging.error(f"❌ Error processing AI response: {e}")
        return "Error processing AI response."

def handle_topic_change(chat_id, user_input):
    """Handle conversation topic changes and context switching."""
    global conversation_topics, conversation_history

    if chat_id not in conversation_history:
        conversation_history[chat_id] = []
        conversation_topics[chat_id] = []

    history = conversation_history[chat_id]
    history.append(user_input)

    if len(history) > 1:
        prev_topic = extract_topic(history[-2])
        current_topic = extract_topic(user_input)

        if is_new_topic(prev_topic, current_topic):
            conversation_topics[chat_id].append({
                "topic": prev_topic,
                "history": history[:-1],
                "timestamp": datetime.now().isoformat()
            })

            for saved_topic in conversation_topics[chat_id]:
                if is_related_topic(current_topic, saved_topic["topic"]):
                    history = saved_topic["history"]
                    logging.info(f"🔄 Returning to topic: {saved_topic['topic']}")
                    break
            else:
                history = [user_input]
                logging.info(f"📌 New topic: {current_topic}")

            conversation_history[chat_id] = history
        else:
            logging.info(f"✅ Continuing topic: {current_topic}")
    
    return history

def extract_topic(text):
    """Extract main topic from text."""
    words = text.lower().split()
    stop_words = {"the", "a", "an", "and", "or", "but", "in", "on", "at", "to"}
    return " ".join(w for w in words if w not in stop_words)

def is_new_topic(prev, current):
    """Check if topics are different."""
    prev_words = set(prev.split())
    current_words = set(current.split())
    overlap = len(prev_words & current_words)
    return overlap / len(prev_words | current_words) < 0.3

def is_related_topic(current, saved):
    """Check if topics are related."""
    current_words = set(current.split())
    saved_words = set(saved.split())
    return len(current_words & saved_words) / len(current_words | saved_words) > 0.5


async def process_ai_response(telegram_client: TelegramClient, chat_id: int, response: str) -> None:
    """Process AI response and execute function if applicable."""

    from main import execute_command_immediately,execute_function
    try:
        logging.info(f"🧠 AI Response Received: {response}")

        if response.startswith("Executing action:"):
            response = response.replace("Executing action:", "").strip()

        if response.startswith("execute:"):
            parts = response.replace("execute:", "").strip().split(".")
            if len(parts) == 2:
                module_name, function_name = parts
                logging.info(f"📌 AI Command Received: {module_name}.{function_name}")
                try:
                    # Pass the user_input as parameter according to the function requirements
                    if module_name == "internet_search" and function_name == "main":
                        result = await execute_function(module_name, function_name, query=user_input)
                    elif module_name == "research" and function_name == "conduct_research":
                        result = await execute_function(module_name, function_name, topic=user_input)
                    else:
                        result = await execute_function(module_name, function_name)
                    logging.info(f"✅ AI Execution Result: {result}")
                    await telegram_client.send_message(chat_id, f"Executed {function_name}: {result}")
                except Exception as e:
                    logging.error(f"❌ Error executing command from AI response: {e}")
                    await telegram_client.send_message(chat_id, "Error executing command.")
            else:
                logging.warning("⚠️ Invalid function call format received from AI")
                await telegram_client.send_message(chat_id, "Invalid function call format.")
        else:
            if chat_id and response.strip():  # Ensure both chat_id and response are valid
                await telegram_client.send_message(chat_id, text=response)
            else:
                logging.warning("⚠️ Missing chat_id or text. Message not sent.")

    except Exception as e:
        logging.error(f"❌ Error processing AI response: {e}")
        await telegram_client.send_message(chat_id, text="Error processing AI response.")

import logging
import re
import json
from main import execute_command_immediately
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
if function doesnt require execution, reply in a friendly manner.
answer any questions or provide information to the best of your ability without making things up.
avoid comentary 
use internet_search as a last resort
play indicates play_pause function unless stated otherwise

### USER INPUT:
{user_input}

### AVAILABLE FUNCTIONS:
{json.dumps(available_functions(), indent=2)}

### RESPONSE FORMAT:
- **If execution is required:** `execute:module.function`
- **If no execution is needed:** A brief natural language response.

Now determine the best response.
"""



    from main import execute_function
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
                    elif module_name == "play" or "pause" and function_name == "play_pause":
                        result = await execute_function(module_name, function_name)
                    elif module_name == "reminder" and function_name == "parse_notification_request":
                        result = await execute_function(module_name, function_name, user_input)
                    elif module_name == "sentiment_analysis" and function_name == "perform_sentiment_analysis":
                        result = await execute_function(module_name, function_name, topic=user_input)
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