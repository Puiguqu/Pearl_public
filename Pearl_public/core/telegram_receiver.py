import aiohttp
import asyncio
import logging
from typing import Optional, Dict, Any

from config.telegram_settings import BOT_TOKEN, CHAT_ID
from core.modules_loader import available_functions
from utils.logger import log_error, log_info, log_warning

# API URLs and constants
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
SEND_MESSAGE_URL = f"{TELEGRAM_API_URL}/sendMessage"
GET_UPDATES_URL = f"{TELEGRAM_API_URL}/getUpdates"
MAX_MESSAGE_LENGTH = 4096
DEFAULT_TIMEOUT = 30

# Global list to keep track of messages Pearl sends
tracking_sent_messages = []


class TelegramClient:
    """Persistent Telegram API client with enhanced security."""

    def __init__(self, token: str):
        self.token = token
        self.bot_id: Optional[int] = None
        self.session: Optional[aiohttp.ClientSession] = None

    async def start(self):
        """Initialize the client session and store bot_id."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=DEFAULT_TIMEOUT))
        bot_info = await self.get_me()
        self.bot_id = bot_info.get("id")
        log_info(f"✅ Bot started with ID: {self.bot_id}")

    async def get_me(self) -> dict:
        """Retrieve bot information from Telegram API."""
        url = f"{TELEGRAM_API_URL}/getMe"
        async with self.session.get(url) as response:
            response_data = await response.json()
            return response_data.get("result", {})

    async def get_updates(self, offset: Optional[int] = None, max_retries: int = 5, timeout: int = 30) -> list:
        """
        Fetch updates from the Telegram API with retry logic.
        
        Args:
            offset (int, optional): Identifier of the first update to be returned.
            max_retries (int): Maximum number of retries on failure.
            timeout (int): Timeout for the request in seconds.
            
        Returns:
            list: A list of update objects.
        """
        params = {'offset': offset} if offset is not None else {}
        retries = 0

        while retries < max_retries:
            try:
                async with self.session.get(GET_UPDATES_URL, params=params) as response:
                    if response.status == 200:
                        updates = await response.json()
                        logging.debug(f"Received updates: {updates}")
                        return updates.get("result", [])
                    else:
                        log_error(f"Failed to get updates: {response.status} - {await response.text()}")
            except aiohttp.ClientError as e:
                retries += 1
                log_warning(f"Connection error, retrying ({retries}/{max_retries}): {e}")
                await asyncio.sleep(2 ** retries)
            except asyncio.TimeoutError:
                retries += 1
                log_warning(f"Request timeout, retrying ({retries}/{max_retries})")
                await asyncio.sleep(2 ** retries)
            except Exception as e:
                log_error(f"Unexpected error: {e}")
                break

        log_error("Max retries reached. Could not fetch updates.")
        return []

    async def send_message(self, chat_id: int, text: str, max_retries: int = 3) -> bool:
        """Send a message to Telegram."""
        if not chat_id or not text:
            log_warning("⚠️ Missing chat_id or text")
            return False

        if self.session is None:
            log_error("❌ TelegramClient session is not initialized. Restarting session.")
            self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30))

        for attempt in range(max_retries):
            try:
                message = str(text)[:4096]  # Telegram's message limit
                payload = {
                    "chat_id": chat_id,
                    "text": message,
                }
                async with self.session.post(SEND_MESSAGE_URL, json=payload) as response:
                    if response.status == 200:
                        log_info(f"✅ Message sent to {chat_id}")
                        return True
                    else:
                        log_error(f"❌ Failed: {response.status} - {await response.text()}")
            except asyncio.CancelledError:
                log_warning("⚠️ Send cancelled")
                raise
            except Exception as e:
                log_error(f"❌ Error: {str(e)}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff

        return False

    async def handle_update(self, update: Dict[str, Any]) -> None:

        from core.command_handler import process_user_input
        """
        Process an incoming update while preventing the bot from processing its own messages.
        
        Only messages from the authorized user (CHAT_ID) are allowed.
        """
        try:
            message = update.get("message")
            if message:
                sender = message.get("from", {})
                if sender:
                    # Skip messages from the bot itself
                    if sender.get("id") == self.bot_id:
                        return

                    # Only allow messages from the authorized user
                    allowed_user_id = CHAT_ID
                    if sender.get("id") != allowed_user_id:
                        log_info(f"Unauthorized message from {sender.get('id')} ignored.")
                        return

                log_info(f"📩 From {sender.get('username', 'Unknown')}: {message.get('text', '').strip()}")
                await process_user_input(message.get("chat", {}).get("id"), message.get("text", "").strip(), self)
        except Exception as e:
            log_error(f"❌ Update error: {str(e)}")

    async def stop(self):
        """Gracefully close the client session."""
        if self.session:
            await self.session.close()
            self.session = None
            log_info("✅ TelegramClient stopped")


async def main():
    BOT_TOKEN = BOT_TOKEN
    telegram_client = TelegramClient(BOT_TOKEN)
    await telegram_client.start()  # Ensure session is initialized before use

    offset = None
    try:
        while True:
            updates = await telegram_client.get_updates(offset)
            for update in updates:
                await telegram_client.handle_update(update)
                update_id = update.get("update_id")
                if update_id is not None:
                    offset = update_id + 1
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        log_info("Shutting down...")
    finally:
        await telegram_client.stop()  # Ensure session is closed properly

if __name__ == "__main__":
    asyncio.run(main())
