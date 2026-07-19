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


if __name__ == "__main__":
    unittest.main()
