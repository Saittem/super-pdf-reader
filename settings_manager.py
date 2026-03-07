import json
import os

SETTINGS_FILE = "pdf_settings.json"

def load_settings():
    """Loads the saved reading positions from a JSON file."""
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_position(filepath, page_num, zoom):
    """Saves the current page and zoom level for a specific file."""
    settings = load_settings()
    settings[filepath] = {"page": page_num, "zoom": zoom}
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f, indent=4)

def get_position(filepath):
    """Retrieves the saved position for a file, defaulting to page 0 and 1.0 zoom."""
    settings = load_settings()
    return settings.get(filepath, {"page": 0, "zoom": 1.0})