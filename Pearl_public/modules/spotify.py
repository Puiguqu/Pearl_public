import spotipy
import logging
import asyncio
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException

# Configure logging
logging.basicConfig(level=logging.INFO)

# Spotify API Credentials
SPOTIFY_CONFIG = {
    "client_id": "5b03944c24434f9c8e3f1a41e3883eed",
    "client_secret": "4edf3fe3a69d4f94ab64a1544f6dcab3",
    "redirect_uri": "http://localhost:8888/callback",
    "scope": "user-modify-playback-state user-read-playback-state user-read-currently-playing app-remote-control"
}

class SpotifyController:
    def __init__(self):
        """Initialize Spotify API client"""
        self.sp = None
        self.device_id = None
        self.authenticate()

    def authenticate(self):
        """Authenticate with Spotify API"""
        try:
            self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(**SPOTIFY_CONFIG))
            logging.info("✅ Successfully authenticated with Spotify")
            self.refresh_device()
        except Exception as e:
            logging.error(f"❌ Spotify Authentication failed: {e}")
            self.sp = None

    def list_available_devices(self):
        """Returns a list of available devices"""
        try:
            devices = self.sp.devices()
            if not devices['devices']:
                return []

            return [{"id": d["id"], "name": d["name"], "type": d["type"], "active": d["is_active"]} for d in devices['devices']]
        except SpotifyException as e:
            logging.error(f"❌ Error retrieving Spotify devices: {e}")
            return []

    def refresh_device(self, preferred_device_name=None):
        """Refreshes the active device."""
        devices = self.list_available_devices()
        if not devices:
            logging.error("❌ No active Spotify devices found. Open Spotify on a device and start playing.")
            self.device_id = None
            return False

        logging.info(f"🔍 Available devices: {devices}")

        # Use preferred device if specified
        if preferred_device_name:
            for device in devices:
                if device["name"].lower() == preferred_device_name.lower():
                    self.device_id = device["id"]
                    logging.info(f"✅ Using preferred device: {device['name']}")
                    return True

        # Select the first active device
        for device in devices:
            if device["active"]:
                self.device_id = device["id"]
                logging.info(f"✅ Using active device: {device['name']}")
                return True

        # Fallback to first available device
        self.device_id = devices[0]["id"]
        logging.info(f"📱 Using fallback device: {devices[0]['name']}")
        return True

    async def execute_with_device_check(self, action, *args):
        """Ensures a device is available before executing an action"""
        if not self.device_id and not self.refresh_device():
            return "❌ No active Spotify device found. Open Spotify and start playing."

        try:
            if asyncio.iscoroutinefunction(action):
                return await action(*args)
            else:
                return action(*args)
        except SpotifyException as e:
            logging.error(f"❌ Spotify API Error: {e}")
            return f"Error: {str(e)}"
        except Exception as e:
            logging.error(f"❌ Unexpected error: {e}")
            return f"Error: {str(e)}"

    # Exposed functions for Pearl
    async def play_pause(self):
        """Toggle play/pause"""
        current_playback = self.sp.current_playback()
        if current_playback and current_playback['is_playing']:
            return await self.execute_with_device_check(self.sp.pause_playback, self.device_id)
        else:
            return await self.execute_with_device_check(self.sp.start_playback, self.device_id)

    async def skip_track(self):
        """Skip to the next track"""
        return await self.execute_with_device_check(self.sp.next_track, self.device_id)

    async def previous_track(self):
        """Go back to the previous track"""
        return await self.execute_with_device_check(self.sp.previous_track, self.device_id)

    async def set_volume(self, volume: int):
        """Set volume level (0-100)"""
        if not (0 <= volume <= 100):
            return "❌ Invalid volume (must be 0-100)"
        return await self.execute_with_device_check(self.sp.volume, volume, self.device_id)

    async def play_song(self, query: str):
        """Search for a song and play it"""
        results = self.sp.search(q=query, limit=1, type='track')
        if not results['tracks']['items']:
            return "❌ Song not found"

        track = results['tracks']['items'][0]
        return await self.execute_with_device_check(self.sp.start_playback, device_id=self.device_id, uris=[track['uri']])

    async def shuffle(self, enable: bool = True):
        """Enable or disable shuffle mode"""
        return await self.execute_with_device_check(self.sp.shuffle, enable, self.device_id)

    async def repeat_mode(self, mode: str = "track"):
        """Set repeat mode ('track', 'context', or 'off')"""
        if mode not in ["track", "context", "off"]:
            return "❌ Invalid mode. Use 'track', 'context', or 'off'."
        return await self.execute_with_device_check(self.sp.repeat, mode, self.device_id)

    async def get_current_track(self):
        """Get currently playing track details"""
        current_playback = self.sp.current_playback()
        if not current_playback or not current_playback['is_playing']:
            return "❌ No track currently playing"

        track = current_playback['item']
        return f"🎶 Now playing: {track['name']} by {', '.join([artist['name'] for artist in track['artists']])}"

# Create an instance of the controller
controller = SpotifyController()

# Expose functions so Pearl recognizes them
async def play_pause(): #toggle play/pause state
    return await controller.play_pause()

async def skip_track():
    return await controller.skip_track()

async def previous_track():
    return await controller.previous_track()

async def set_volume(volume: int):
    return await controller.set_volume(volume)

async def play_song(query: str):
    return await controller.play_song(query)

async def shuffle(enable: bool = True):
    return await controller.shuffle(enable)

async def repeat_mode(mode: str):
    return await controller.repeat_mode(mode)

async def get_current_track():
    return await controller.get_current_track()
