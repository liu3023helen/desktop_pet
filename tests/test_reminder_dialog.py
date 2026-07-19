import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication

from reminder_dialog import ReminderFormDialog


class ReminderFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        if hasattr(self, "dialog"):
            self.dialog.close()

    def test_action_switch_hides_only_url_label(self):
        self.dialog = ReminderFormDialog()

        self.assertEqual(self.dialog._action_combo.currentIndex(), 1)
        self.assertEqual(self.dialog._action_combo.currentText(), "播放动画")
        self.assertTrue(self.dialog._url_label.isHidden())
        name_label = next(
            label for label in self.dialog.findChildren(type(self.dialog._url_label))
            if label.text() == "提醒名称"
        )
        self.assertFalse(name_label.isHidden())

    def test_edit_preserves_extension_fields_and_disabled_state(self):
        self.dialog = ReminderFormDialog(reminder_data={
            "name": "Existing",
            "enabled": False,
            "time": "09:30",
            "action_type": "notify_only",
            "custom_field": {"keep": True},
        })

        self.dialog._on_ok()
        result = self.dialog.get_result()

        self.assertFalse(result["enabled"])
        self.assertEqual(result["custom_field"], {"keep": True})
        self.assertTrue(result["id"])

    def test_open_url_requires_a_target(self):
        self.dialog = ReminderFormDialog()
        self.dialog._name_edit.setText("Open link")
        self.dialog._action_combo.setCurrentIndex(0)
        self.dialog._url_edit.clear()

        with patch("reminder_dialog.QMessageBox.warning") as warning:
            self.dialog._on_ok()

        warning.assert_called_once()
        self.assertEqual(self.dialog.get_result(), {})

    def test_new_reminder_saves_play_animation_by_default(self):
        self.dialog = ReminderFormDialog()
        self.dialog._name_edit.setText("Animated reminder")

        self.dialog._on_ok()

        self.assertEqual(
            self.dialog.get_result()["action_type"],
            "play_animation",
        )


if __name__ == "__main__":
    unittest.main()
