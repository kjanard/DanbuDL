import os
import json
import tempfile
import unittest
from pathlib import Path
from core.config import ConfigManager, DEFAULT_CONFIG


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.temp_dir.name) / "test_config.json"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_default_config_created(self):
        """Test that default configuration is written when file doesn't exist."""
        cfg = ConfigManager(filepath=self.config_path)
        self.assertTrue(self.config_path.exists())
        self.assertEqual(cfg.get("request_delay"), 1.0)
        self.assertEqual(cfg.get("default_limit"), 50)
        self.assertTrue(cfg.get("skip_existing"))

    def test_get_and_set(self):
        """Test setting values and persisting to disk."""
        cfg = ConfigManager(filepath=self.config_path)
        cfg.set("request_delay", 2.5)
        cfg.set("api_username", "test_user")

        # Reload from same file
        reloaded = ConfigManager(filepath=self.config_path)
        self.assertEqual(reloaded.get("request_delay"), 2.5)
        self.assertEqual(reloaded.get("api_username"), "test_user")

    def test_corrupted_json_fallback(self):
        """Test graceful fallback to defaults when config.json is corrupted."""
        with open(self.config_path, "w", encoding="utf-8") as f:
            f.write("{ invalid json syntax ...")

        cfg = ConfigManager(filepath=self.config_path)
        # Should not crash, should fall back to default config
        self.assertEqual(cfg.get("request_delay"), DEFAULT_CONFIG["request_delay"])
        self.assertEqual(cfg.get("default_limit"), DEFAULT_CONFIG["default_limit"])

    def test_nested_rating_dict_update(self):
        """Test that updating nested dictionary merges properly."""
        cfg = ConfigManager(filepath=self.config_path)
        cfg.set("default_ratings", {"all": True, "g": True, "s": True, "q": True, "e": True})

        reloaded = ConfigManager(filepath=self.config_path)
        ratings = reloaded.get("default_ratings")
        self.assertTrue(ratings["all"])
        self.assertTrue(ratings["e"])

    def test_deepcopy_isolation(self):
        """Test that modifying one ConfigManager doesn't mutate DEFAULT_CONFIG."""
        path1 = Path(self.temp_dir.name) / "cfg1.json"
        cfg1 = ConfigManager(filepath=path1)
        cfg1.config["default_ratings"]["e"] = True

        self.assertFalse(DEFAULT_CONFIG["default_ratings"]["e"])


if __name__ == "__main__":
    unittest.main()
