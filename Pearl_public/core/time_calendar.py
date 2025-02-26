import datetime
import logging

logging.basicConfig(level=logging.DEBUG)

def get_current_datetime():
    """
    Get the current date and time.

    Returns:
        dict: A dictionary containing the current date and time in various formats.
    """
    now = datetime.datetime.now()
    return {
        "datetime": now,
        "date": now.date().isoformat(),
        "time": now.time().isoformat(timespec='seconds'),
        "weekday": now.strftime("%A"),
    }

def parse_date_time_request(user_input):
    """
    Parse user input to extract date and time information.

    Args:
        user_input (str): The user's input requesting date or time information.

    Returns:
        str: A natural language response with the requested date/time details.
    """
    try:
        now = get_current_datetime()

        # Determine the type of request based on input keywords
        if "time" in user_input.lower():
            return f"The current time is {now['time']}."
        elif "date" in user_input.lower():
            return f"Today's date is {now['date']} ({now['weekday']})."
        elif "day" in user_input.lower():
            return f"Today is {now['weekday']}."
        else:
            return "I can provide the current date, time, or weekday. What would you like to know?"

    except Exception as e:
        logging.error(f"Error parsing date/time request: {e}")
        return "Sorry, I couldn't understand your request for date or time information."

# Integration for other modules or LLM parsing
def provide_datetime_context():
    """
    Provide the current datetime context as a formatted string for parsing by Llama3.2.

    Returns:
        str: A formatted string with the current datetime context.
    """
    now = get_current_datetime()
    return (
        f"The current date is {now['date']}, the time is {now['time']}, "
        f"and today is {now['weekday']}."
    )
