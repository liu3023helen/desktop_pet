import tempfile
import unittest
from pathlib import Path

import yaml

from config_manager import ConfigManager


class ConfigDefaultsTests(unittest.TestCase):
    def test_missing_config_uses_complete_template_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manager = ConfigManager(str(Path(temp_dir) / "missing.yaml"))

            config = manager.load()

        for section in (
            "pet",
            "reminders",
            "time_sync",
            "weather",
            "ui",
            "engine",
            "logging",
            "holidays",
        ):
            self.assertIn(section, config)

    def test_partial_config_is_deep_merged_with_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                yaml.safe_dump({"pet": {"name": "Custom"}}, allow_unicode=True),
                encoding="utf-8",
            )
            manager = ConfigManager(str(config_path))

            config = manager.load()

        self.assertEqual(config["pet"]["name"], "Custom")
        self.assertEqual(config["pet"]["style"], "shinchan")
        self.assertIn("window_size", config["ui"])
        self.assertIn("check_interval_sec", config["engine"])


if __name__ == "__main__":
    unittest.main()
