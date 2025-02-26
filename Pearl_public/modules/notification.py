import asyncio
import re
import logging
from datetime import datetime, timedelta
from core.telegram_receiver import TelegramClient
from config.telegram_settings import CHAT_ID

# Dictionary to store scheduled notifications
scheduled_notifications = {}

async def parse_notification_request(user_input):
    """
    Extracts the time and message from the user input.

    Example inputs:
    - "Remind me to take my medicine at 10pm"
    - "Remind me to send my sister to the airport at 5pm"
    - "Set an alarm for 7:30 AM to go for a jog"
    
    Returns:
    - A dictionary with 'time' (datetime object) and 'message' (str) if successful.
    - None if parsing fails.
    """
    try:
        time_pattern = r'(\d{1,2}:\d{2}\s?(?:AM|PM|am|pm)?)|(\d{1,2}\s?(?:AM|PM|am|pm)?)|(\d{1,2}:\d{2})|(\d{1,2})'
        match = re.search(time_pattern, user_input, re.IGNORECASE)

        if not match:
            logging.debug(f"Failed to extract time from: {user_input}")
            return None

        extracted_time = match.group().strip()
        logging.debug(f"Extracted time: {extracted_time}")

        current_time = datetime.now()
        notification_time = None

        try:
            if 'AM' in extracted_time.upper() or 'PM' in extracted_time.upper():
                if ":" in extracted_time:
                    parsed_time = datetime.strptime(extracted_time, "%I:%M %p")
                else:
                    parsed_time = datetime.strptime(extracted_time, "%I %p")
            else:
                if ":" in extracted_time:
                    parsed_time = datetime.strptime(extracted_time, "%H:%M")
                else:
                    parsed_time = datetime.strptime(extracted_time, "%H")

            notification_time = datetime.combine(current_time.date(), parsed_time.time())

            if notification_time < current_time:
                notification_time += timedelta(days=1)

        except ValueError:
            logging.debug(f"Failed to convert extracted time: {extracted_time}")
            return None

        message = re.sub(time_pattern, "", user_input, count=1).strip(" .!?")
        if not message:
            message = "Reminder"

        logging.debug(f"Parsed request - Time: {notification_time}, Message: {message}")
        return {"time": notification_time, "message": message}

    except Exception as e:
        logging.error(f"Exception in parse_notification_request: {e}")
        return None


async def schedule_notification(chat_id, time, message):
    """
    Schedule a notification for the specified time.
    """
    delay = (time - datetime.now()).total_seconds()
    
    if delay <= 0:
        return "❌ The specified time is invalid or has already passed."

    asyncio.create_task(_send_notification_after_delay(chat_id, time, message))
    return f"✅ Notification scheduled for {time.strftime('%I:%M %p')}."


async def _send_notification_after_delay(chat_id, time, message):
    """Helper function to delay and send a notification."""
    delay = (time - datetime.now()).total_seconds()
    await asyncio.sleep(delay)
    
    telegram_client = TelegramClient()  # Ensure an instance is used
    await telegram_client.send_message(chat_id, message)


async def handle_user_request(user_input, chat_id):
    """
    Handles user notification requests asynchronously.
    """
    try:
        logging.info(f"📩 Processing user request: {user_input}")

        parsed_request = await parse_notification_request(user_input)

        if not parsed_request:
            error_msg = "❌ Failed to parse notification request. Please provide a valid time format like '5pm' or '17:00'."
            logging.error(error_msg)
            return error_msg

        notification_time = parsed_request.get('time')
        message = parsed_request.get('message')

        if not notification_time or not isinstance(notification_time, datetime):
            error_msg = f"❌ Invalid time extracted: {notification_time}"
            logging.error(error_msg)
            return error_msg

        if chat_id not in scheduled_notifications:
            scheduled_notifications[chat_id] = []

        response = await schedule_notification(chat_id, notification_time, message)
        scheduled_notifications[chat_id].append(response)

        logging.info(response)
        return response

    except Exception as e:
        error_msg = f"❌ Error in handle_user_request: {str(e)}"
        logging.error(error_msg)
        return error_msg
