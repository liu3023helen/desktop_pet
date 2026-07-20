import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pomodoro import (
    PHASE_FOCUS,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    STATUS_AWAITING,
    STATUS_PAUSED,
    STATUS_RUNNING,
    PomodoroStore,
    PomodoroTimer,
)


class PomodoroTimerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "pomodoro.yaml"
        self.now = datetime(2026, 7, 20, 9, 0, 0)
        self.timer = PomodoroTimer(
            store=PomodoroStore(self.path),
            now_provider=lambda: self.now,
        )

    def test_defaults_are_manual_and_hide_during_focus(self):
        self.assertFalse(self.timer.settings["auto_start_break"])
        self.assertFalse(self.timer.settings["auto_start_focus"])
        self.assertTrue(self.timer.settings["hide_during_focus"])

    def test_focus_uses_absolute_end_time_and_survives_restart(self):
        self.timer.start_focus(label="Write tests")
        restarted = PomodoroTimer(
            store=PomodoroStore(self.path),
            now_provider=lambda: self.now,
        )

        snapshot = restarted.snapshot()

        self.assertEqual(snapshot["phase"], PHASE_FOCUS)
        self.assertEqual(snapshot["status"], STATUS_RUNNING)
        self.assertEqual(snapshot["remaining_seconds"], 25 * 60)
        self.assertEqual(snapshot["label"], "Write tests")

    def test_focus_completion_records_daily_stats_and_awaits_break(self):
        self.timer.start_focus()
        self.now += timedelta(minutes=25)

        event = self.timer.tick()
        snapshot = self.timer.snapshot()

        self.assertEqual(event.event_type, "focus_completed")
        self.assertEqual(event.next_phase, PHASE_SHORT_BREAK)
        self.assertFalse(event.auto_started)
        self.assertEqual(snapshot["status"], STATUS_AWAITING)
        self.assertEqual(snapshot["today"], {
            "completed": 1,
            "focus_minutes": 25,
        })

    def test_recovered_focus_is_recorded_on_scheduled_end_date(self):
        self.now = datetime(2026, 7, 20, 23, 50, 0)
        self.timer.start_focus(minutes=20)
        self.now = datetime(2026, 7, 21, 8, 0, 0)

        event = self.timer.tick()

        self.assertTrue(event.recovered)
        self.assertEqual(
            self.timer.stats["2026-07-21"],
            {"completed": 1, "focus_minutes": 20},
        )

    def test_every_fourth_focus_awaits_long_break(self):
        for index in range(4):
            self.timer.start_focus()
            self.now += timedelta(minutes=25)
            event = self.timer.tick()
            if index < 3:
                self.assertEqual(event.next_phase, PHASE_SHORT_BREAK)

        self.assertEqual(event.next_phase, PHASE_LONG_BREAK)
        self.assertEqual(self.timer.snapshot()["completed_in_set"], 4)

    def test_start_next_runs_the_awaiting_phase(self):
        self.timer.start_focus(minutes=1)
        self.now += timedelta(minutes=1)
        self.timer.tick()

        self.timer.start_next()

        snapshot = self.timer.snapshot()
        self.assertEqual(snapshot["phase"], PHASE_SHORT_BREAK)
        self.assertEqual(snapshot["status"], STATUS_RUNNING)
        self.assertEqual(snapshot["remaining_seconds"], 5 * 60)

    def test_pause_and_resume_preserve_remaining_time(self):
        self.timer.start_focus(minutes=10)
        self.now += timedelta(minutes=3, seconds=10)

        self.timer.pause()

        self.assertEqual(self.timer.snapshot()["status"], STATUS_PAUSED)
        self.assertEqual(self.timer.snapshot()["remaining_seconds"], 410)
        self.now += timedelta(hours=1)

        self.timer.resume()

        self.assertEqual(self.timer.snapshot()["status"], STATUS_RUNNING)
        self.assertEqual(self.timer.snapshot()["remaining_seconds"], 410)

    def test_auto_start_break_can_be_enabled(self):
        self.timer.update_settings({
            **self.timer.settings,
            "focus_minutes": 1,
            "auto_start_break": True,
        })
        self.timer.start_focus()
        self.now += timedelta(minutes=1)

        event = self.timer.tick()

        self.assertTrue(event.auto_started)
        self.assertEqual(self.timer.snapshot()["phase"], PHASE_SHORT_BREAK)
        self.assertEqual(self.timer.snapshot()["status"], STATUS_RUNNING)

    def test_stop_clears_session_but_keeps_stats(self):
        self.timer.start_focus(minutes=1)
        self.now += timedelta(minutes=1)
        self.timer.tick()

        self.timer.stop()

        snapshot = self.timer.snapshot()
        self.assertEqual(snapshot["status"], "idle")
        self.assertEqual(snapshot["today"]["completed"], 1)

    def test_invalid_settings_use_bounded_defaults(self):
        timer = PomodoroTimer(
            settings={
                "focus_minutes": 0,
                "short_break_minutes": "bad",
                "long_break_minutes": 999,
                "long_break_every": 1,
                "auto_start_break": "false",
            },
            store=PomodoroStore(self.path),
        )

        self.assertEqual(timer.settings["focus_minutes"], 1)
        self.assertEqual(timer.settings["short_break_minutes"], 5)
        self.assertEqual(timer.settings["long_break_minutes"], 120)
        self.assertEqual(timer.settings["long_break_every"], 2)
        self.assertFalse(timer.settings["auto_start_break"])

    def test_partial_settings_update_preserves_other_values(self):
        self.timer.update_settings({"focus_minutes": 45})

        self.assertEqual(self.timer.settings["focus_minutes"], 45)
        self.assertEqual(self.timer.settings["short_break_minutes"], 5)
        self.assertTrue(self.timer.settings["hide_during_focus"])


class PomodoroStoreTests(unittest.TestCase):
    def test_corrupt_primary_recovers_from_backup(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "pomodoro.yaml"
            store = PomodoroStore(path)
            store.save(None, {
                "2026-07-20": {"completed": 2, "focus_minutes": 50}
            })
            path.write_text("version: [broken", encoding="utf-8")

            document = store.load()

        self.assertEqual(
            document["stats"]["2026-07-20"],
            {"completed": 2, "focus_minutes": 50},
        )


if __name__ == "__main__":
    unittest.main()
