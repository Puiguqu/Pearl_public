import logging
import asyncio
import re
import ollama
from datetime import datetime
from core.modules_loader import available_functions
from core.time_calendar import provide_datetime_context
from modules.self_editor import implement_feature
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

        prompt = (
            "SYSTEM: YOU are PEARL - Personalized Efficient Assistant for Routine and Learning.\n"
            f"CONTEXT:\n{datetime_context}\n\n"
            f"INPUT: {user_input}\n\n"
            "INSTRUCTIONS:\n"
            "1. Answer directly without AI pleasantries\n"
            "2. Use internet_search for research needs\n"
            "3. Use available functions only\n"
            "4. Suggest new features only when necessary\n"
            "5. Track conversation topics\n"
            "6. Maintain context across topic switches\n\n"
            "7. Provide a detailed analysis for research topics when requested\n"
            "8. Avoid sending code directly to users, instead implement and test it\n\n"
            "9. if topic is the same, maintain context\n"
            "10. if topic changes, save context and history\n"
            "11. note that AVAILABLE FUNCTIONS: are not part of user input\n"
            "12. if news is requested always provide up-to-date news\n\n"
            "13. if topic is switched, automatically start new conversation using handle_conversation\n"
            "14. keep responses short\n"
            f"AVAILABLE FUNCTIONS:\n{function_list}"
        )

        logging.debug(f"Generated Jarvis Prompt: {prompt}")
        return prompt

    except Exception as e:
        logging.error(f"Error in prompt generation: {e}")
        return "Error generating prompt."

async def process_user_input(chat_id: int, user_input: str, telegram_client) -> None:
    """Process user input and determine the best response or function to execute."""
    logging.info(f"📩 Processing user input from chat_id {chat_id}: {user_input}")

    functions = available_functions()
    # Generate a prompt for AI processing.
    prompt = (
        f"User input: {user_input}\n\n"
        f"Determine the best response or function to execute based on the available functions: {functions}.\n"
        f"If execution is required, return 'execute:module.function'. Otherwise, return a response."
    )
    
    response = await ask_ollama(prompt)

    if response.startswith("execute:"):
        command = response.strip()
        result = await execute_command(command)
        await telegram_client.send_message(chat_id, text=f"Executed command result: {result}")
    else:
        await telegram_client.send_message(chat_id, text=response)

def extract_function_call(response):
    """Extract function calls from AI response."""
    match = re.search(r"execute:(\w+)\.(\w+)(?:\((.*?)\))?", response)
    if match:
        module_name, function_name, args = match.groups()
        args = [arg.strip() for arg in args.split(",")] if args else []
        return module_name, function_name, args
    return None

async def ask_ollama(prompt, model="llama3.2", chat_id=chat_id):
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

async def ask_ollama_and_implement(prompt, modules_path="modules"):
    """Implement new features from LLM response."""
    try:
        client = ollama.Client()
        response = client.generate(model="llama3.2", prompt=prompt)
        feature_name = response.get("feature_name")
        feature_code = response.get("feature_code")

        if not feature_name or not feature_code:
            search_results = await google_search_with_summaries_ollama(prompt, chat_id=chat_id)
            return f"Feature extraction failed. Performed an internet search instead:\n{search_results}"

        return await implement_feature(feature_code, feature_name, modules_path)
        
    except Exception as e:
        logging.error(f"Error implementing feature: {e}")
        return f"Error implementing feature: {e}"

async def process_ai_response(telegram_client: TelegramClient, chat_id: int, response: str) -> None:
    """Process AI response and execute function if applicable."""
    try:
        logging.info(f"🧠 AI Response Received: {response}")

        if response.startswith("Executing action:"):
            response = response.replace("Executing action:", "").strip()

        if response.startswith("execute:"):
            parts = response.replace("execute:", "").strip().split(".")
            if len(parts) == 2:
                module_name, function_name = parts
                logging.info(f"📌 AI Command Received: {module_name}.{function_name}")

                # 🚀 **Immediate Execution Instead of Queuing**
                result = await execute_function(module_name, function_name)
                logging.info(f"✅ AI Execution Result: {result}")
                await telegram_client.send_message(chat_id, text=f"Executed {function_name}: {result}")

            else:
                logging.warning("⚠️ Invalid function call format received from AI")
                await telegram_client.send_message(chat_id, text="Invalid function call format.")
        else:
            await telegram_client.send_message(chat_id, text=response)

    except Exception as e:
        logging.error(f"❌ Error processing AI response: {e}")
        await telegram_client.send_message(chat_id, text="Error processing AI response.")
