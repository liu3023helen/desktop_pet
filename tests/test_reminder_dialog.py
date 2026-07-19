import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtWidgets import QApplication, QPushButton

from reminder_dialog import ReminderFormDialog, ReminderInteractionDialog


class ReminderFormTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def tearDown(self):
        if hasattr(self, "dialog"):
            self.dialog.close()

    def test_action_switch_hides_only_url_label(self):
        self.dialog = ReminderFormDialog()

        self.dialog._action_combo.setCurrentIndex(1)

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
        self.dialog._url_edit.clear()

        with patch("reminder_dialog.QMessageBox.warning") as warning:
            self.dialog._on_ok()

        warning.assert_called_once()
        self.assertEqual(self.dialog.get_result(), {})


class ReminderInteractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_snooze_button_emits_name_and_minutes(self):
        dialog = ReminderInteractionDialog({"name": "Stand up", "message": "Move"})
        emitted = []
        dialog.snooze_requested.connect(
            lambda name, minutes: emitted.append((name, minutes))
        )

        dialog.findChild(QPushButton, "snooze_5_button").click()

        self.assertEqual(emitted, [("Stand up", 5)])

    def test_skip_and_complete_buttons_emit_actions(self):
        skip_dialog = ReminderInteractionDialog({"name": "Task"})
        skipped = []
        skip_dialog.skip_today_requested.connect(skipped.append)
        skip_dialog.findChild(QPushButton, "skip_today_button").click()

        complete_dialog = ReminderInteractionDialog({"name": "Task"})
        completed = []
        complete_dialog.complete_requested.connect(completed.append)
        complete_dialog.findChild(QPushButton, "complete_button").click()

        self.assertEqual(skipped, ["Task"])
        self.assertEqual(completed, ["Task"])


if __name__ == "__main__":
    unittest.main()
