import logging
import asyncio
from core.modules_loader import available_functions
from core.time_calendar import provide_datetime_context
from modules.self_editor import implement_feature

# Configure logging
logging.basicConfig(level=logging.DEBUG)

# Dictionary to store conversation history for each chat_id
conversation_history = {}

from config.telegram_settings import CHAT_ID as chat_id

def jarvis_prompt(user_input, functions_by_module):
    """
    Generate a prompt for PEARL to determine actions based on user input and dynamically imported features.

    Args:
        user_input (str): The user's input for the assistant.

    Returns:
        str: A prompt to be sent to the Ollama LLM.
    """
    try:
        logging.debug(f"Generating prompt for user input: {user_input}")
        functions = functions_by_module()  # Dynamically fetch available functions grouped by module
        datetime_context = provide_datetime_context()  # Get the current datetime context

        # Log the available features
        for module, funcs in functions.items():
            logging.debug(f"Module: {module}")
            for func in funcs:
                logging.debug(f"  - {func}")

        # Generate the prompt with available functions and datetime context
        function_list = "\n".join(
            f"{module}:\n" + "\n".join(f"  - {func}" for func in funcs)
            for module, funcs in functions.items()
        )
        prompt = (
            f"You are PEARL - Personalized Efficient Assistant for Routine and Learning.\n"
            f"The current context is:\n{datetime_context}\n\n"
            f"User Input: {user_input}\n"
            "Based on the user input and available features, execute the appropriate action directly.\n"
            f"{function_list}\n\n"
            "If no feature matches the request, propose a new feature name and description. "
            "Keep responses concise and suggest only if necessary. Default to the internet_search module if needed."
            "Keep your response concise and avoid reflective commentary or tags."
            "If the user asks about current news, execute the internet search module and summarize the results. Provide only live and accurate news updates, along with the date of publication for the article."
        )
        logging.debug(f"Generated prompt: {prompt}")
        return prompt

    except Exception as e:
        logging.error(f"Error generating Jarvis prompt: {e}")
        return "Error generating prompt."


import re

async def ask_ollama(prompt, model="deepseek-r1", chat_id=None):
    """
    Interact with DeepSeek LLM and optionally send the response to a Telegram user.
    
    Args:
        prompt (str): The prompt to send to the LLM.
        model (str): The model to use (default: deepseek-r1).
        chat_id (int, optional): Telegram chat ID to send the response to.

    Returns:
        str: The filtered response from the LLM.
    """
    import ollama  # Local import to avoid circular dependencies

    try:
        logging.debug(f"Sending prompt to DeepSeek: {prompt}")
        client = ollama.Client()

        # Retrieve conversation history for the chat_id
        history = conversation_history.get(chat_id, [])
        history.append(f"User: {prompt}")
        conversation_context = "\n".join(history)

        retries = 3  # Retry up to 3 times on transient errors
        for attempt in range(retries):
            try:
                response = client.generate(model=model, prompt=conversation_context)
                output = response.get("response", "")

                # Remove text inside <think> tags
                cleaned_output = re.sub(r"<think>.*?</think>", "", output, flags=re.DOTALL).strip()

                logging.debug(f"Filtered response from DeepSeek: {cleaned_output}")

                if chat_id:
                    from core.telegram_receiver import send_message
                    await send_message(chat_id, cleaned_output)

                    # Update conversation history
                    if f"AI: {cleaned_output}" not in history:
                        history.append(f"AI: {cleaned_output}")
                    conversation_history[chat_id] = history

                return cleaned_output

            except (ollama.ClientError, ConnectionError) as e:
                logging.warning(f"Transient error during DeepSeek interaction (attempt {attempt + 1}): {e}")
                if attempt < retries - 1:
                    continue
                else:
                    raise

    except AttributeError as e:
        logging.error(f"Error interacting with DeepSeek (AttributeError): {e}")
        return "Error interacting with DeepSeek."

    except Exception as e:
        logging.error(f"Error interacting with DeepSeek: {e}")
        return "Error interacting with DeepSeek."


import asyncio
from core.ollama_integration import ask_ollama
from modules.self_editor import implement_feature
from modules.internet_search import google_search_with_summaries_ollama

async def ask_ollama_and_implement(prompt, modules_path="modules"):
    """
    Send a prompt to Ollama, extract the feature name and code, and implement it dynamically.

    Args:
        prompt (str): The prompt to send to Ollama.
        modules_path (str): Path to save the generated feature.

    Returns:
        str: Status message.
    """
    response = await ask_ollama(prompt)

    if not response:
        return "No response from Ollama."

    try:
        # Ensure response is a dictionary and extract the required keys
        response_data = eval(response) if isinstance(response, str) else response
        feature_name = response_data.get("feature_name")
        feature_code = response_data.get("feature_code")

        if not feature_name or not feature_code:
            # Perform an internet search as a fallback
            search_results = await google_search_with_summaries_ollama(prompt, chat_id="YOUR_CHAT_ID")
            return f"Feature extraction failed. Performed an internet search instead:\n{search_results}"

        # Implement the feature dynamically
        return await implement_feature(feature_code, feature_name, modules_path)

    except Exception as e:
        return f"Error processing Ollama response: {e}"
