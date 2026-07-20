import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt5.QtCore import QDate, QTime, Qt
from PyQt5.QtWidgets import QApplication

from config_manager import ConfigManager
from reminder_dialog import ReminderDialog, ReminderFormDialog


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

    def test_legacy_weekday_rule_is_loaded_and_migrated(self):
        self.dialog = ReminderFormDialog(reminder_data={
            "name": "Legacy",
            "enabled": False,
            "time": "09:30",
            "weekdays_only": True,
            "action_type": "notify_only",
        })

        self.assertEqual(self.dialog._schedule_combo.currentData(), "workday")

        self.dialog._on_ok()
        result = self.dialog.get_result()

        self.assertEqual(result["schedule_type"], "workday")
        self.assertNotIn("weekdays_only", result)

    def test_one_time_rule_shows_date_and_saves_pending_status(self):
        self.dialog = ReminderFormDialog()
        self.dialog._name_edit.setText("One time")
        self.dialog._schedule_combo.setCurrentIndex(
            self.dialog._schedule_combo.findData("once")
        )
        future_date = QDate.currentDate().addDays(2)
        self.dialog._date_edit.setDate(future_date)

        self.assertTrue(self.dialog._date_edit.isVisibleTo(self.dialog))

        self.dialog._on_ok()
        result = self.dialog.get_result()

        self.assertEqual(result["schedule_type"], "once")
        self.assertEqual(result["date"], future_date.toString("yyyy-MM-dd"))
        self.assertEqual(result["status"], "pending")

    def test_new_one_time_rule_rejects_past_time(self):
        self.dialog = ReminderFormDialog()
        self.dialog._name_edit.setText("Past")
        self.dialog._schedule_combo.setCurrentIndex(
            self.dialog._schedule_combo.findData("once")
        )
        self.dialog._date_edit.setDate(QDate.currentDate().addDays(-1))
        self.dialog._time_edit.setTime(QTime(0, 0))

        with patch("reminder_dialog.QMessageBox.warning") as warning:
            self.dialog._on_ok()

        warning.assert_called_once()
        self.assertEqual(self.dialog.get_result(), {})

    def test_rescheduling_completed_reminder_resets_pending_status(self):
        self.dialog = ReminderFormDialog(reminder_data={
            "id": "completed-once",
            "name": "Completed",
            "enabled": False,
            "time": "09:30",
            "schedule_type": "once",
            "date": "2026-01-01",
            "status": "completed",
            "action_type": "notify_only",
        })
        future_date = QDate.currentDate().addDays(2)
        self.dialog._date_edit.setDate(future_date)

        self.dialog._on_ok()
        result = self.dialog.get_result()

        self.assertFalse(result["enabled"])
        self.assertEqual(result["status"], "pending")
        self.assertEqual(result["date"], future_date.toString("yyyy-MM-dd"))

    def test_switching_to_recurring_rule_removes_one_time_state(self):
        self.dialog = ReminderFormDialog(reminder_data={
            "id": "old-once",
            "name": "Old once",
            "enabled": False,
            "time": "09:30",
            "schedule_type": "once",
            "date": "2026-01-01",
            "status": "expired",
            "action_type": "notify_only",
        })
        self.dialog._schedule_combo.setCurrentIndex(
            self.dialog._schedule_combo.findData("daily")
        )

        self.dialog._on_ok()
        result = self.dialog.get_result()

        self.assertEqual(result["schedule_type"], "daily")
        self.assertNotIn("date", result)
        self.assertNotIn("status", result)


class ReminderManagementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_manager = ConfigManager(
            str(Path(self.temp_dir.name) / "config.yaml")
        )

    def tearDown(self):
        if hasattr(self, "dialog"):
            self.dialog.close()

    def _open_with(self, reminder):
        self.config_manager.save({"reminders": [reminder]})
        self.dialog = ReminderDialog(self.config_manager)

    def test_table_displays_one_time_rule_and_status(self):
        self._open_with({
            "id": "table-once",
            "name": "Table once",
            "enabled": False,
            "time": "09:30",
            "schedule_type": "once",
            "date": "2026-07-20",
            "status": "completed",
        })

        self.assertEqual(self.dialog._table.columnCount(), 6)
        self.assertEqual(
            self.dialog._table.item(0, 3).text(),
            "指定日期 2026-07-20",
        )
        self.assertEqual(self.dialog._table.item(0, 4).text(), "已完成")

    def test_past_one_time_reminder_cannot_be_enabled_directly(self):
        self._open_with({
            "id": "past-once",
            "name": "Past once",
            "enabled": False,
            "time": "00:00",
            "schedule_type": "once",
            "date": "2000-01-01",
            "status": "expired",
        })

        with patch("reminder_dialog.QMessageBox.warning") as warning:
            self.dialog._on_toggle_enable(0, Qt.Checked)

        warning.assert_called_once()
        saved = self.config_manager.load()["reminders"][0]
        self.assertFalse(saved["enabled"])
        self.assertEqual(saved["status"], "expired")

    def test_future_one_time_reminder_can_be_reenabled(self):
        future_date = QDate.currentDate().addDays(2).toString("yyyy-MM-dd")
        self._open_with({
            "id": "future-once",
            "name": "Future once",
            "enabled": False,
            "time": "23:59",
            "schedule_type": "once",
            "date": future_date,
            "status": "completed",
        })

        self.dialog._on_toggle_enable(0, Qt.Checked)

        saved = self.config_manager.load()["reminders"][0]
        self.assertTrue(saved["enabled"])
        self.assertEqual(saved["status"], "pending")


if __name__ == "__main__":
    unittest.main()
