import json
import os
import copy
from pathlib import Path

import logging

logger = logging.getLogger("DanbuDL.Config")

DEFAULT_CONFIG = {
    "download_dir": str(Path.cwd() / "downloads"),
    "request_delay": 1.0,
    "max_concurrent": 2,
    "save_metadata": True,
    "metadata_format": "txt",  # "txt" or "json"
    "skip_existing": True,
    "download_quality": "original",  # "original" or "large"
    "api_username": "",
    "api_key": "",
    "default_ratings": {
        "all": False,
        "g": True,
        "s": True,
        "q": False,
        "e": False
    },
    "default_limit": 50,
    "file_naming": "{id}_{md5}.{ext}"  # "{id}.{ext}", "{id}_{md5}.{ext}", "{artist}_{id}.{ext}"
}

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config.json"


class ConfigManager:
    def __init__(self, filepath=CONFIG_FILE):
        self.filepath = Path(filepath)
        self.config = copy.deepcopy(DEFAULT_CONFIG)
        self.load()

    def load(self):
        if self.filepath.exists():
            try:
                with open(self.filepath, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    if isinstance(saved, dict):
                        for k, v in saved.items():
                            if isinstance(v, dict) and isinstance(self.config.get(k), dict):
                                self.config[k].update(v)
                            else:
                                self.config[k] = v
            except Exception as e:
                logger.debug(f"[Config] Error loading config: {e}")
        else:
            self.save()

    def save(self):
        try:
            self.filepath.parent.mkdir(parents=True, exist_ok=True)
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.debug(f"[Config] Error saving config: {e}")

    def get(self, key, default=None):
        return self.config.get(key, default)

    def set(self, key, value):
        self.config[key] = value
        self.save()
