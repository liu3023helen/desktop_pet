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

    def test_invalid_optional_field_types_are_isolated(self):
        valid = make_reminder(name="still valid")
        engine = ReminderEngine({
            "reminders": [
                {
                    "name": "bad message",
                    "enabled": True,
                    "time": "09:30",
                    "message": ["not", "text"],
                },
                {
                    "name": "bad action",
                    "enabled": True,
                    "time": "09:30",
                    "action_type": ["notify_only"],
                },
                {
                    "name": "bad boolean",
                    "enabled": "yes",
                    "time": "09:30",
                },
                valid,
            ]
        })

        engine.load_reminders()

        self.assertEqual(engine._reminders, [valid])

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

    def test_duplicate_names_keep_skip_state_isolated_by_id(self):
        first = make_reminder(name="duplicate")
        first["id"] = "first-id"
        second = make_reminder(name="duplicate")
        second["id"] = "second-id"
        engine = ReminderEngine({"reminders": [first, second]})
        engine.load_reminders()
        engine.get_effective_now = lambda: datetime(2026, 7, 20, 9, 30, 10)
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(reminder["id"])

        engine.handle_skip_today("first-id")
        engine._check_reminders()

        self.assertEqual(fired, ["second-id"])


class ReminderThreadLifecycleTests(unittest.TestCase):
    def test_immediate_stop_is_not_lost(self):
        engine = ReminderEngine({"reminders": []})

        engine.start()
        engine.stop()

        self.assertFalse(engine.isRunning())

    def test_engine_can_restart_after_a_clean_stop(self):
        engine = ReminderEngine({"reminders": []})

        engine.start()
        engine.stop()
        engine.start()
        engine.stop()

        self.assertFalse(engine.isRunning())


class ReminderDailyResetTests(unittest.TestCase):
    def test_first_check_initializes_date_and_next_day_clears_state(self):
        engine = ReminderEngine({"reminders": []})
        clock = [datetime(2026, 7, 20, 23, 59, 59)]
        engine.get_effective_now = lambda: clock[0]

        engine._check_reminders()
        self.assertEqual(engine._last_check_date, "2026-07-20")

        engine._triggered_today.add("old-trigger")
        engine._snooze_mgr.skip_today("old-reminder")
        clock[0] += timedelta(seconds=2)
        engine._check_reminders()

        self.assertEqual(engine._last_check_date, "2026-07-21")
        self.assertEqual(engine._triggered_today, set())
        self.assertEqual(engine._snooze_mgr._skipped_today, set())


class ReminderWakeRecoveryTests(unittest.TestCase):
    def test_wake_scans_the_full_gap_and_fires_in_scheduled_order(self):
        later = make_reminder(name="later", reminder_time="10:00")
        earlier = make_reminder(name="earlier", reminder_time="09:30")
        engine = ReminderEngine({"reminders": [later, earlier]})
        engine.load_reminders()
        clock = [datetime(2026, 7, 20, 9, 0, 0)]
        engine.get_effective_now = lambda: clock[0]
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(
            (reminder["name"], reminder["_triggered_at"])
        )

        engine._check_reminders()
        clock[0] = datetime(2026, 7, 20, 11, 0, 0)
        engine._check_reminders()

        self.assertEqual(fired, [
            ("earlier", "2026-07-20T09:30:00"),
            ("later", "2026-07-20T10:00:00"),
        ])

    def test_wake_scan_keeps_only_occurrences_within_24_hours(self):
        engine = ReminderEngine({
            "reminders": [make_reminder(reminder_time="08:00")]
        })
        engine.load_reminders()
        clock = [datetime(2026, 7, 20, 7, 0, 0)]
        engine.get_effective_now = lambda: clock[0]
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(
            reminder["_triggered_at"]
        )

        engine._check_reminders()
        clock[0] = datetime(2026, 7, 21, 13, 0, 0)
        engine._check_reminders()

        self.assertEqual(fired, ["2026-07-21T08:00:00"])


class ReminderEngineSettingsTests(unittest.TestCase):
    def test_engine_settings_control_interval_and_grace_window(self):
        engine = ReminderEngine({
            "reminders": [make_reminder(reminder_time="09:30")],
            "engine": {
                "check_interval_sec": 0.25,
                "sleep_grace_period_sec": 5,
                "missed_reminder_retention_hours": 12,
            },
        })
        engine.load_reminders()
        engine.get_effective_now = lambda: datetime(2026, 7, 20, 9, 31, 10)
        fired = []
        engine._trigger_reminder = lambda reminder: fired.append(reminder)

        engine._check_reminders()
        self.assertEqual(fired, [])
        self.assertEqual(engine._check_interval_sec, 0.25)
        self.assertEqual(engine._missed_reminder_retention_hours, 12)

        engine.reload_reminders({
            "reminders": [make_reminder(reminder_time="09:30")],
            "engine": {
                "check_interval_sec": 0.5,
                "sleep_grace_period_sec": 15,
                "missed_reminder_retention_hours": 48,
            },
        })
        engine._check_reminders()

        self.assertEqual(len(fired), 1)
        self.assertEqual(engine._check_interval_sec, 0.5)
        self.assertEqual(engine._sleep_grace_period_sec, 15)
        self.assertEqual(engine._missed_reminder_retention_hours, 24)

    def test_invalid_engine_settings_use_safe_defaults(self):
        engine = ReminderEngine({
            "reminders": [],
            "engine": {
                "check_interval_sec": "fast",
                "sleep_grace_period_sec": None,
                "missed_reminder_retention_hours": "forever",
            },
        })

        self.assertEqual(engine._check_interval_sec, 1.0)
        self.assertEqual(engine._sleep_grace_period_sec, 60)
        self.assertEqual(engine._missed_reminder_retention_hours, 24)

if __name__ == "__main__":
    unittest.main()
