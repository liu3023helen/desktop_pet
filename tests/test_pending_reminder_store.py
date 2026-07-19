import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from pending_reminder_store import PendingReminderStore


class PendingReminderStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.path = Path(self.temp_dir.name) / "pending.yaml"
        self.store = PendingReminderStore(self.path, retention_hours=24)
        self.now = datetime(2026, 7, 20, 12, 0, 0)

    @staticmethod
    def reminder(reminder_id, name):
        return {
            "id": reminder_id,
            "name": name,
            "message": name,
            "time": "09:00",
        }

    def test_records_are_saved_atomically_and_loaded_in_time_order(self):
        later = self.store.create_record(
            self.reminder("later", "Later"),
            self.now - timedelta(minutes=5),
        )
        earlier = self.store.create_record(
            self.reminder("earlier", "Earlier"),
            self.now - timedelta(minutes=10),
        )

        self.store.append(later, now=self.now)
        self.store.append(earlier, now=self.now)
        loaded = self.store.load(now=self.now)

        self.assertEqual(
            [item["reminder_key"] for item in loaded],
            ["earlier", "later"],
        )
        self.assertTrue(self.path.exists())
        self.assertTrue(self.store.backup_path.exists())
        self.assertFalse(self.path.with_suffix(".yaml.tmp").exists())

    def test_records_older_than_24_hours_are_removed(self):
        expired = self.store.create_record(
            self.reminder("expired", "Expired"),
            self.now - timedelta(hours=24, seconds=1),
        )
        current = self.store.create_record(
            self.reminder("current", "Current"),
            self.now - timedelta(hours=23, minutes=59),
        )
        self.store.save([expired, current])

        loaded = self.store.load(now=self.now)

        self.assertEqual([item["reminder_key"] for item in loaded], ["current"])
        self.assertEqual(len(self.store._read_document(self.path)), 1)

    def test_corrupt_primary_recovers_from_backup(self):
        record = self.store.create_record(
            self.reminder("recover", "Recover"), self.now
        )
        self.store.save([record])
        self.path.write_text("items: [broken", encoding="utf-8")

        loaded = self.store.load(now=self.now)

        self.assertEqual([item["reminder_key"] for item in loaded], ["recover"])

    def test_invalid_records_are_ignored(self):
        valid = self.store.create_record(
            self.reminder("valid", "Valid"), self.now
        )
        self.store.save([
            {"record_id": "bad", "status": "pending"},
            valid,
        ])

        loaded = self.store.load(now=self.now)

        self.assertEqual(loaded, [valid])

    def test_replace_and_remove_update_a_single_record(self):
        record = self.store.create_record(
            self.reminder("task", "Task"), self.now
        )
        self.store.append(record, now=self.now)
        record["status"] = "snoozed"
        record["snooze_until"] = (self.now + timedelta(minutes=10)).isoformat()

        self.store.replace(record, now=self.now)
        self.assertEqual(self.store.load(now=self.now)[0]["status"], "snoozed")

        self.store.remove(record["record_id"], now=self.now)
        self.assertEqual(self.store.load(now=self.now), [])


if __name__ == "__main__":
    unittest.main()
