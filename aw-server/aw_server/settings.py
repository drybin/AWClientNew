import json
from pathlib import Path

from aw_core.dirs import get_config_dir

# Default central server (GFP/TIM) before settings.json exists; overridden after user saves in Settings.
CENTRAL_DEFAULTS = {
    "gfpsEnabled": True,
    "gfpsServerIP": "188.225.44.153",
    "gfpsServerPort": 5700,
}


class Settings:
    def __init__(self, testing: bool):
        filename = "settings.json" if not testing else "settings-testing.json"
        self.config_file = Path(get_config_dir("aw-server")) / filename
        self.load()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        return self.set(key, value)

    def load(self):
        if self.config_file.exists():
            with open(self.config_file) as f:
                self.data = json.load(f)
        else:
            self.data = {}

    def save(self):
        with open(self.config_file, "w") as f:
            json.dump(self.data, f, indent=4)

    def get(self, key: str, default=None):
        if not key:
            merged = dict(self.data)
            for gk, gv in CENTRAL_DEFAULTS.items():
                if gk not in merged:
                    merged[gk] = gv
            return merged
        if key in self.data:
            return self.data[key]
        if key in CENTRAL_DEFAULTS:
            return CENTRAL_DEFAULTS[key]
        return default

    def set(self, key, value):
        if value:
            self.data[key] = value
        else:
            if key in self.data:
                del self.data[key]
        self.save()
