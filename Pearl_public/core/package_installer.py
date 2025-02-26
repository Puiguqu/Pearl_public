import subprocess
import sys
import asyncio
import logging
from core.telegram_receiver import TelegramClient

logging.basicConfig(level=logging.INFO)

async def install_package(package_name: str, chat_id: int, telegram_client: TelegramClient):
    """
    Install a Python package dynamically using pip.
    
    Args:
        package_name (str): The name of the package to install.
        chat_id (int): The Telegram chat ID to send responses to.
        telegram_client (TelegramClient): The Telegram client instance to send messages.
    """
    try:
        # Validate package name
        if not package_name.isidentifier():
            await telegram_client.send_message(chat_id, f"❌ Invalid package name: {package_name}")
            return

        # Check if already installed
        try:
            __import__(package_name)
            await telegram_client.send_message(chat_id, f"✅ Package {package_name} already installed")
            return
        except ImportError:
            pass

        # Install package
        await telegram_client.send_message(chat_id, f"📦 Installing {package_name}...")
        process = subprocess.Popen(
            [sys.executable, "-m", "pip", "install", package_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        output, error = process.communicate()

        if process.returncode == 0:
            await telegram_client.send_message(chat_id, f"✅ Successfully installed {package_name}")
        else:
            error_msg = error.decode('utf-8')
            logging.error(f"Installation failed: {error_msg}")
            await telegram_client.send_message(chat_id, f"❌ Error installing `{package_name}`: {error_msg}")

    except Exception as e:
        logging.error(f"Error installing package: {e}")
        await telegram_client.send_message(chat_id, "❌ An error occurred while installing the package.")
