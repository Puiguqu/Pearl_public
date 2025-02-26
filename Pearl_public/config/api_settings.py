# Configuration for external API integrations

# Example: Open-Meteo API (Free and requires no API key)
OPEN_METEO_BASE_URL = "https://api.open-meteo.com/v1/forecast"

# Example: Google Calendar API
GOOGLE_API_KEY = "<YOUR_GOOGLE_API_KEY>"
GOOGLE_CALENDAR_BASE_URL = "https://www.googleapis.com/calendar/v3/calendars"

# Example: Custom API
CUSTOM_API_KEY = "<YOUR_CUSTOM_API_KEY>"
CUSTOM_API_BASE_URL = "https://api.example.com/v1"

# Utility function to validate API keys (optional)
def validate_api_keys():
    missing_keys = []
    if GOOGLE_API_KEY == "<YOUR_GOOGLE_API_KEY>":
        missing_keys.append("Google API")
    if CUSTOM_API_KEY == "<YOUR_CUSTOM_API_KEY>":
        missing_keys.append("Custom API")

    if missing_keys:
        raise ValueError(f"Missing API keys for: {', '.join(missing_keys)}")

# Run validation on import
try:
    validate_api_keys()
except ValueError as e:
    print(e)
