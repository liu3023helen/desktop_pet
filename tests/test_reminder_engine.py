import unittest
from datetime import datetime

from reminder_engine import ReminderEngine


def make_reminder(name="valid", reminder_time="09:30"):
    return {
        "name": name,
        "enabled": True,
        "time": reminder_time,
        "action_type": "notify_only",
    }


class ReminderLoadingTests(unittest.TestCase):
    def test_invalid_reminders_are_isolated(self):
        valid = make_reminder()
        engine = ReminderEngine({
            "reminders": [
                {"enabled": True, "time": "09:30"},
                {"name": "bad type", "enabled": True, "time": 930},
                {"name": "bad range", "enabled": True, "time": "25:00"},
                valid,
            ]
        })

        engine.load_reminders()

        self.assertEqual(engine._reminders, [valid])

    def test_non_list_reminders_config_is_rejected(self):
        engine = ReminderEngine({"reminders": {"name": "not a list"}})

        engine.load_reminders()

        self.assertEqual(engine._reminders, [])

    def test_valid_reminder_still_triggers(self):
        engine = ReminderEngine({"reminders": [make_reminder()]})
        engine.load_reminders()
        engine.get_effective_now = lambda: datetime(2026, 7, 20, 9, 30, 15)
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(reminder["name"])

        engine._check_reminders()

        self.assertEqual(fired, ["valid"])


if __name__ == "__main__":
    unittest.main()
