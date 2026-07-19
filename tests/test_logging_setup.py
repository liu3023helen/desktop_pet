import logging
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from startup_utils import setup_logging


class LoggingSetupTests(unittest.TestCase):
    def _remove_handlers(self):
        root = logging.getLogger()
        for handler in list(root.handlers):
            if getattr(handler, "_desktop_pet_handler", False):
                root.removeHandler(handler)
                handler.close()

    def tearDown(self):
        self._remove_handlers()

    def test_configured_path_and_level_are_applied(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "startup_utils.get_app_dir", return_value=Path(temp_dir)
        ):
            logger = setup_logging("DEBUG", "logs/custom.log")
            logger.debug("configured message")
            for handler in logging.getLogger().handlers:
                handler.flush()
            log_path = Path(temp_dir) / "data" / "logs" / "custom.log"
            contents = log_path.read_text(encoding="utf-8")
            self._remove_handlers()

        self.assertEqual(logging.getLogger().level, logging.DEBUG)
        self.assertIn("configured message", contents)

    def test_parent_traversal_falls_back_inside_data_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir, patch(
            "startup_utils.get_app_dir", return_value=Path(temp_dir)
        ):
            setup_logging("INFO", "../outside.log")
            file_handlers = [
                handler for handler in logging.getLogger().handlers
                if getattr(handler, "baseFilename", None)
                and getattr(handler, "_desktop_pet_handler", False)
            ]
            actual_path = Path(file_handlers[0].baseFilename)
            self._remove_handlers()

        expected = Path(temp_dir) / "data" / "logs" / "pet.log"
        self.assertEqual(actual_path, expected)


if __name__ == "__main__":
    unittest.main()
