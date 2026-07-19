"""Persistent storage for reminders waiting for user acknowledgement."""
import logging
import shutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

import yaml

from utils import get_app_dir

logger = logging.getLogger(__name__)


class PendingReminderStore:
    """Atomically persist pending reminders and discard stale entries."""

    VERSION = 1
    VALID_STATUSES = frozenset({"pending", "active", "snoozed"})

    def __init__(
        self,
        path: Optional[Path] = None,
        retention_hours: int = 24,
    ):
        self.path = Path(path) if path else get_app_dir() / "data" / "pending_reminders.yaml"
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self.retention = timedelta(hours=max(1, int(retention_hours)))
        self._lock = threading.RLock()

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _reminder_key(reminder: Dict[str, Any]) -> str:
        value = reminder.get("_runtime_id", reminder.get("id", reminder.get("name", "")))
        return str(value).strip()

    def create_record(
        self,
        reminder: Dict[str, Any],
        triggered_at: datetime,
        status: str = "pending",
        snooze_until: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        if status not in self.VALID_STATUSES:
            raise ValueError(f"invalid pending reminder status: {status}")
        reminder_key = self._reminder_key(reminder)
        if not reminder_key:
            raise ValueError("pending reminder requires a stable identifier")

        return {
            "record_id": uuid4().hex,
            "reminder_key": reminder_key,
            "triggered_at": triggered_at.isoformat(timespec="seconds"),
            "status": status,
            "snooze_until": (
                snooze_until.isoformat(timespec="seconds") if snooze_until else None
            ),
            "reminder": dict(reminder),
        }

    def _read_document(self, path: Path) -> List[Dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
        if not isinstance(document, dict) or document.get("version") != self.VERSION:
            raise ValueError("unsupported pending reminder document")
        items = document.get("items", [])
        if not isinstance(items, list):
            raise ValueError("pending reminder items must be a list")
        return items

    def _normalize(
        self,
        items: List[Dict[str, Any]],
        now: datetime,
    ) -> List[Dict[str, Any]]:
        normalized = []
        cutoff = now - self.retention
        for item in items:
            if not isinstance(item, dict):
                continue
            triggered_at = self._parse_datetime(item.get("triggered_at"))
            reminder = item.get("reminder")
            if (
                not isinstance(item.get("record_id"), str)
                or not item["record_id"].strip()
                or not isinstance(item.get("reminder_key"), str)
                or not item["reminder_key"].strip()
                or triggered_at is None
                or triggered_at < cutoff
                or item.get("status") not in self.VALID_STATUSES
                or not isinstance(reminder, dict)
            ):
                continue

            snooze_until = item.get("snooze_until")
            if snooze_until is not None and self._parse_datetime(snooze_until) is None:
                continue
            normalized.append(dict(item))

        normalized.sort(key=lambda item: item["triggered_at"])
        return normalized

    def load(self, now: Optional[datetime] = None) -> List[Dict[str, Any]]:
        with self._lock:
            now = now or datetime.now()
            if not self.path.exists():
                return []

            source_items = None
            try:
                source_items = self._read_document(self.path)
            except Exception as error:
                logger.error(f"读取待处理提醒失败: {error}")
                if self.backup_path.exists():
                    try:
                        source_items = self._read_document(self.backup_path)
                        logger.warning("已从备份恢复待处理提醒")
                    except Exception as backup_error:
                        logger.error(f"读取待处理提醒备份失败: {backup_error}")

            if source_items is None:
                return []

            normalized = self._normalize(source_items, now)
            if normalized != source_items:
                self.save(normalized)
            return normalized

    def save(self, items: List[Dict[str, Any]]) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            document = {"version": self.VERSION, "items": items}
            try:
                with open(temp_path, "w", encoding="utf-8") as handle:
                    yaml.safe_dump(
                        document,
                        handle,
                        allow_unicode=True,
                        sort_keys=False,
                    )
                temp_path.replace(self.path)
                shutil.copy2(self.path, self.backup_path)
            finally:
                temp_path.unlink(missing_ok=True)

    def append(self, record: Dict[str, Any], now: Optional[datetime] = None) -> None:
        with self._lock:
            items = self.load(now=now)
            items.append(record)
            items.sort(key=lambda item: item["triggered_at"])
            self.save(items)

    def remove(self, record_id: str, now: Optional[datetime] = None) -> None:
        with self._lock:
            items = [
                item for item in self.load(now=now)
                if item.get("record_id") != record_id
            ]
            self.save(items)

    def replace(self, record: Dict[str, Any], now: Optional[datetime] = None) -> None:
        with self._lock:
            items = self.load(now=now)
            updated = False
            for index, item in enumerate(items):
                if item.get("record_id") == record.get("record_id"):
                    items[index] = record
                    updated = True
                    break
            if not updated:
                items.append(record)
            items.sort(key=lambda item: item["triggered_at"])
            self.save(items)
