import unittest
from datetime import datetime, timedelta

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


class ReminderDeduplicationTests(unittest.TestCase):
    def test_reminders_sharing_a_minute_trigger_independently(self):
        engine = ReminderEngine({
            "reminders": [
                make_reminder(name="first"),
                make_reminder(name="second"),
            ]
        })
        engine.load_reminders()
        engine.get_effective_now = lambda: datetime(2026, 7, 20, 9, 30, 15)
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(reminder["name"])

        engine._check_reminders()
        engine._check_reminders()

        self.assertEqual(fired, ["first", "second"])
        self.assertEqual(len(engine._triggered_today), 2)

    def test_identical_legacy_reminders_use_their_position_as_fallback(self):
        first = make_reminder(name="duplicate")
        second = make_reminder(name="duplicate")
        engine = ReminderEngine({"reminders": [first, second]})
        engine.load_reminders()
        engine.get_effective_now = lambda: datetime(2026, 7, 20, 9, 30, 15)
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(reminder)

        engine._check_reminders()

        self.assertEqual(fired, [first, second])


class ReminderSnoozeTests(unittest.TestCase):
    def test_snoozed_reminder_triggers_once_when_due(self):
        engine = ReminderEngine({"reminders": [make_reminder()]})
        engine.load_reminders()
        clock = [datetime(2026, 7, 20, 9, 30, 10)]
        engine.get_effective_now = lambda: clock[0]
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(clock[0])

        engine.handle_snooze("valid", 5)
        clock[0] += timedelta(minutes=4, seconds=59)
        engine._check_reminders()
        self.assertEqual(fired, [])

        clock[0] += timedelta(seconds=1)
        engine._check_reminders()
        engine._check_reminders()

        self.assertEqual(fired, [datetime(2026, 7, 20, 9, 35, 10)])
        self.assertIsNone(
            engine._snooze_mgr.get_snooze_time("valid", now=clock[0])
        )


if __name__ == "__main__":
    unittest.main()
