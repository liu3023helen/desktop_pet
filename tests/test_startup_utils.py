import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import startup_utils


class AutostartCommandTests(unittest.TestCase):
    def test_frozen_command_quotes_path_with_spaces(self):
        app_path = r"F:\Program Files\Desktop Pet\DesktopPet.exe"
        with patch.object(sys, "frozen", True, create=True), patch(
            "startup_utils.get_exe_path", return_value=app_path
        ):
            command = startup_utils.get_autostart_command()

        self.assertEqual(command, f'"{app_path}"')

    def test_development_command_uses_pythonw_and_quotes_both_paths(self):
        interpreter = r"C:\Python Runtime\python.exe"
        script = r"F:\Program Files\Desktop Pet\main.py"
        with patch.object(sys, "frozen", False, create=True), patch.object(
            sys, "executable", interpreter
        ), patch("startup_utils.get_exe_path", return_value=script), patch.object(
            Path, "exists", return_value=True
        ):
            command = startup_utils.get_autostart_command()

        self.assertEqual(
            command,
            '"C:\\Python Runtime\\pythonw.exe" '
            '"F:\\Program Files\\Desktop Pet\\main.py"',
        )

    def test_registry_receives_generated_command(self):
        command = r'"F:\Program Files\Desktop Pet\DesktopPet.exe"'
        key = object()
        with patch("startup_utils.winreg.OpenKey", return_value=key), patch(
            "startup_utils.winreg.DeleteValue"
        ), patch("startup_utils.winreg.SetValueEx") as set_value, patch(
            "startup_utils.winreg.CloseKey"
        ), patch("startup_utils.get_autostart_command", return_value=command):
            result = startup_utils.set_auto_start(True)

        self.assertTrue(result)
        set_value.assert_called_once_with(
            key,
            startup_utils.APP_NAME,
            0,
            startup_utils.winreg.REG_SZ,
            command,
        )


if __name__ == "__main__":
    unittest.main()
