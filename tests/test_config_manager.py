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
        self.assertIsInstance(config["holidays"], dict)
        self.assertEqual(config["reminders"][0]["schedule_type"], "daily")
        self.assertNotIn("weekdays_only", config["reminders"][0])

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

    def test_invalid_mapping_sections_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text(
                yaml.safe_dump({
                    "pet": "invalid",
                    "ui": [],
                    "weather": False,
                    "logging": "DEBUG",
                }),
                encoding="utf-8",
            )
            config = ConfigManager(str(config_path)).load()

        self.assertIsInstance(config["pet"], dict)
        self.assertIsInstance(config["ui"], dict)
        self.assertIsInstance(config["weather"], dict)
        self.assertIsInstance(config["logging"], dict)


class ConfigRecoveryTests(unittest.TestCase):
    def test_corrupt_primary_config_recovers_from_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            manager = ConfigManager(str(config_path))
            expected = {"pet": {"name": "Recoverable"}, "reminders": []}
            self.assertTrue(manager.save(expected))
            self.assertTrue(manager.backup_path.exists())
            config_path.write_text("pet: [broken", encoding="utf-8")

            config = manager.load()

        self.assertEqual(config["pet"]["name"], "Recoverable")
        self.assertTrue(manager.recovered_from_backup)
        self.assertIsNotNone(manager.last_load_error)

    def test_corrupt_config_without_backup_uses_complete_defaults(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            config_path.write_text("pet: [broken", encoding="utf-8")
            manager = ConfigManager(str(config_path))

            config = manager.load()

        self.assertFalse(manager.recovered_from_backup)
        self.assertIsNotNone(manager.last_load_error)
        self.assertIn("ui", config)
        self.assertIn("engine", config)


if __name__ == "__main__":
    unittest.main()
