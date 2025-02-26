import spotipy
from spotipy.oauth2 import SpotifyOAuth

# Your credentials
SPOTIFY_CONFIG = {
    "client_id": "5b03944c24434f9c8e3f1a41e3883eed",
    "client_secret": "4edf3fe3a69d4f94ab64a1544f6dcab3",
    "redirect_uri": "http://localhost:8888/callback",
    "scope": "user-modify-playback-state user-read-playback-state user-read-currently-playing app-remote-control"
}

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(**SPOTIFY_CONFIG))

# Test authentication
try:
    print("Current User:", sp.current_user())
except spotipy.SpotifyException as e:
    print("Error:", e)

devices = sp.devices()
print("Devices:", devices)

def play_pause():
    sp = get_spotify_client()
    try:
        device_id = get_active_device(sp)
        current = sp.current_playback()
        print("Current Playback:", current)  # Debugging line
        
        if current and current['is_playing']:
            sp.pause_playback(device_id=device_id)
            return "Playback paused"
        else:
            sp.start_playback(device_id=device_id)
            return "Playback started"
    except Exception as e:
        return f"Error: {str(e)}"

def get_active_device(sp):
    devices = sp.devices()
    for device in devices['devices']:
        if device['is_active']:  # Get the actively playing device
            return device['id']
    raise Exception("No active devices found. Start playing a song first!")
