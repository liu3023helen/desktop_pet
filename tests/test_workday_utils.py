import unittest
from datetime import date

import workday_utils
from reminder_engine import ReminderEngine


class HolidayOverrideTests(unittest.TestCase):
    def setUp(self):
        self.original = workday_utils.HOLIDAY_OVERRIDE.copy()

    def tearDown(self):
        workday_utils.set_holiday_override(self.original)

    def test_overrides_support_holidays_and_makeup_workdays(self):
        workday_utils.set_holiday_override({
            date(2026, 10, 1): False,
            "2026-10-04": True,
            "bad-date": False,
            "2026-10-02": "false",
        })

        self.assertFalse(workday_utils.is_workday(date(2026, 10, 1)))
        self.assertTrue(workday_utils.is_workday(date(2026, 10, 4)))
        self.assertEqual(
            workday_utils.HOLIDAY_OVERRIDE,
            {"2026-10-01": False, "2026-10-04": True},
        )

    def test_engine_reload_replaces_holiday_rules(self):
        engine = ReminderEngine({
            "reminders": [],
            "holidays": {"2026-10-01": False},
        })
        self.assertFalse(workday_utils.is_workday(date(2026, 10, 1)))

        engine.reload_reminders({
            "reminders": [],
            "holidays": {"2026-10-01": True},
        })

        self.assertTrue(workday_utils.is_workday(date(2026, 10, 1)))

    def test_builtin_calendar_handles_holiday_and_makeup_workday(self):
        workday_utils.set_holiday_override({})

        self.assertTrue(workday_utils.has_builtin_calendar(2026))
        self.assertFalse(workday_utils.is_workday(date(2026, 1, 2)))
        self.assertTrue(workday_utils.is_rest_day(date(2026, 1, 2)))
        self.assertTrue(workday_utils.is_workday(date(2026, 1, 4)))
        self.assertFalse(workday_utils.is_rest_day(date(2026, 1, 4)))

    def test_rest_day_includes_ordinary_weekend(self):
        workday_utils.set_holiday_override({})

        self.assertTrue(workday_utils.is_rest_day(date(2026, 7, 18)))
        self.assertFalse(workday_utils.is_rest_day(date(2026, 7, 20)))

    def test_user_override_takes_precedence_over_builtin_calendar(self):
        workday_utils.set_holiday_override({"2026-01-02": True})

        self.assertTrue(workday_utils.is_workday(date(2026, 1, 2)))

    def test_future_year_warns_once_and_falls_back_to_weekdays(self):
        workday_utils.set_holiday_override({})
        workday_utils._WARNED_MISSING_YEARS.discard(2027)

        with self.assertLogs(workday_utils.logger, level="WARNING") as logs:
            self.assertFalse(workday_utils.is_workday(date(2027, 1, 2)))
            self.assertTrue(workday_utils.is_workday(date(2027, 1, 4)))

        self.assertEqual(len(logs.output), 1)
        self.assertIn("未内置 2027 年", logs.output[0])


if __name__ == "__main__":
    unittest.main()
