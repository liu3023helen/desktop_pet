"""Persistent Pomodoro state machine independent from the Qt user interface."""
import logging
import math
import shutil
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, Optional

import yaml

from utils import get_app_dir

logger = logging.getLogger(__name__)

PHASE_FOCUS = "focus"
PHASE_SHORT_BREAK = "short_break"
PHASE_LONG_BREAK = "long_break"
STATUS_IDLE = "idle"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_AWAITING = "awaiting"

DEFAULT_SETTINGS = {
    "focus_minutes": 25,
    "short_break_minutes": 5,
    "long_break_minutes": 15,
    "long_break_every": 4,
    "auto_start_break": False,
    "auto_start_focus": False,
    "hide_during_focus": True,
}


@dataclass(frozen=True)
class PomodoroEvent:
    event_type: str
    completed_phase: str
    next_phase: str
    auto_started: bool
    recovered: bool


class PomodoroStore:
    """Atomically persist the active session and daily statistics."""

    VERSION = 1

    def __init__(self, path: Optional[Path] = None):
        self.path = (
            Path(path)
            if path is not None
            else get_app_dir() / "data" / "pomodoro.yaml"
        )
        self.backup_path = self.path.with_suffix(self.path.suffix + ".bak")
        self._lock = threading.RLock()

    @staticmethod
    def empty_document() -> Dict[str, Any]:
        return {
            "version": PomodoroStore.VERSION,
            "session": None,
            "stats": {},
        }

    def _read(self, path: Path) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as handle:
            document = yaml.safe_load(handle) or {}
        if not isinstance(document, dict) or document.get("version") != self.VERSION:
            raise ValueError("unsupported pomodoro document")
        return document

    @staticmethod
    def _normalize_stats(value: Any) -> Dict[str, Dict[str, int]]:
        if not isinstance(value, dict):
            return {}
        normalized = {}
        for date_key, item in value.items():
            if not isinstance(date_key, str) or not isinstance(item, dict):
                continue
            try:
                datetime.strptime(date_key, "%Y-%m-%d")
                completed = max(0, int(item.get("completed", 0)))
                focus_minutes = max(0, int(item.get("focus_minutes", 0)))
            except (TypeError, ValueError):
                continue
            normalized[date_key] = {
                "completed": completed,
                "focus_minutes": focus_minutes,
            }
        return dict(sorted(normalized.items())[-400:])

    @staticmethod
    def _normalize_session(value: Any) -> Optional[Dict[str, Any]]:
        if value is None:
            return None
        if not isinstance(value, dict):
            return None
        if value.get("phase") not in {
            PHASE_FOCUS,
            PHASE_SHORT_BREAK,
            PHASE_LONG_BREAK,
        }:
            return None
        if value.get("status") not in {
            STATUS_RUNNING,
            STATUS_PAUSED,
            STATUS_AWAITING,
        }:
            return None
        try:
            duration_seconds = max(60, int(value.get("duration_seconds", 0)))
            remaining_seconds = max(0, int(value.get("remaining_seconds", 0)))
            completed_in_set = max(0, int(value.get("completed_in_set", 0)))
        except (TypeError, ValueError):
            return None

        end_at = value.get("end_at")
        if value["status"] == STATUS_RUNNING:
            try:
                datetime.fromisoformat(end_at)
            except (TypeError, ValueError):
                return None
        elif end_at is not None:
            return None

        return {
            "phase": value["phase"],
            "status": value["status"],
            "duration_seconds": duration_seconds,
            "remaining_seconds": remaining_seconds,
            "end_at": end_at,
            "completed_in_set": completed_in_set,
            "label": str(value.get("label", ""))[:80],
        }

    def load(self) -> Dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                return self.empty_document()
            document = None
            try:
                document = self._read(self.path)
            except Exception as error:
                logger.error(f"读取番茄钟状态失败: {error}")
                if self.backup_path.exists():
                    try:
                        document = self._read(self.backup_path)
                        logger.warning("已从备份恢复番茄钟状态")
                    except Exception as backup_error:
                        logger.error(f"读取番茄钟状态备份失败: {backup_error}")
            if document is None:
                return self.empty_document()
            return {
                "version": self.VERSION,
                "session": self._normalize_session(document.get("session")),
                "stats": self._normalize_stats(document.get("stats")),
            }

    def save(
        self,
        session: Optional[Dict[str, Any]],
        stats: Dict[str, Dict[str, int]],
    ) -> None:
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            document = {
                "version": self.VERSION,
                "session": session,
                "stats": stats,
            }
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


class PomodoroTimer:
    """A manually-started Pomodoro timer with durable transitions."""

    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        store: Optional[PomodoroStore] = None,
        now_provider: Optional[Callable[[], datetime]] = None,
    ):
        self.store = store or PomodoroStore()
        self._now_provider = now_provider or datetime.now
        self.settings = self.normalize_settings(settings or {})
        document = self.store.load()
        self.session = document["session"]
        self.stats = document["stats"]

    @staticmethod
    def normalize_settings(value: Dict[str, Any]) -> Dict[str, Any]:
        value = value if isinstance(value, dict) else {}

        def bounded_int(key: str, minimum: int, maximum: int) -> int:
            raw = value.get(key, DEFAULT_SETTINGS[key])
            if isinstance(raw, bool):
                return DEFAULT_SETTINGS[key]
            try:
                return max(minimum, min(maximum, int(raw)))
            except (TypeError, ValueError):
                return DEFAULT_SETTINGS[key]

        def boolean(key: str) -> bool:
            raw = value.get(key, DEFAULT_SETTINGS[key])
            return raw if isinstance(raw, bool) else DEFAULT_SETTINGS[key]

        return {
            "focus_minutes": bounded_int("focus_minutes", 1, 180),
            "short_break_minutes": bounded_int("short_break_minutes", 1, 60),
            "long_break_minutes": bounded_int("long_break_minutes", 1, 120),
            "long_break_every": bounded_int("long_break_every", 2, 12),
            "auto_start_break": boolean("auto_start_break"),
            "auto_start_focus": boolean("auto_start_focus"),
            "hide_during_focus": boolean("hide_during_focus"),
        }

    def update_settings(self, settings: Dict[str, Any]) -> None:
        merged = dict(self.settings)
        if isinstance(settings, dict):
            merged.update(settings)
        self.settings = self.normalize_settings(merged)

    def _save(self) -> None:
        self.store.save(self.session, self.stats)

    def _duration_for(self, phase: str) -> int:
        setting = {
            PHASE_FOCUS: "focus_minutes",
            PHASE_SHORT_BREAK: "short_break_minutes",
            PHASE_LONG_BREAK: "long_break_minutes",
        }[phase]
        return self.settings[setting] * 60

    def _begin(
        self,
        phase: str,
        duration_seconds: int,
        now: datetime,
        label: str = "",
        completed_in_set: int = 0,
    ) -> None:
        self.session = {
            "phase": phase,
            "status": STATUS_RUNNING,
            "duration_seconds": max(60, int(duration_seconds)),
            "remaining_seconds": max(60, int(duration_seconds)),
            "end_at": (now + timedelta(seconds=duration_seconds)).isoformat(
                timespec="seconds"
            ),
            "completed_in_set": max(0, int(completed_in_set)),
            "label": str(label).strip()[:80],
        }
        self._save()

    def start_focus(
        self,
        minutes: Optional[int] = None,
        label: str = "",
        now: Optional[datetime] = None,
    ) -> None:
        now = now or self._now_provider()
        completed_in_set = (
            self.session.get("completed_in_set", 0) if self.session else 0
        )
        duration = self.normalize_settings({
            **self.settings,
            "focus_minutes": minutes or self.settings["focus_minutes"],
        })["focus_minutes"] * 60
        self._begin(
            PHASE_FOCUS,
            duration,
            now,
            label=label,
            completed_in_set=completed_in_set,
        )

    def start_next(self, now: Optional[datetime] = None) -> None:
        if self.session is None or self.session["status"] != STATUS_AWAITING:
            raise ValueError("no Pomodoro phase is awaiting start")
        now = now or self._now_provider()
        self._begin(
            self.session["phase"],
            self._duration_for(self.session["phase"]),
            now,
            label=self.session.get("label", ""),
            completed_in_set=self.session.get("completed_in_set", 0),
        )

    def pause(self, now: Optional[datetime] = None) -> None:
        if self.session is None or self.session["status"] != STATUS_RUNNING:
            raise ValueError("Pomodoro is not running")
        now = now or self._now_provider()
        end_at = datetime.fromisoformat(self.session["end_at"])
        self.session["remaining_seconds"] = max(
            0, math.ceil((end_at - now).total_seconds())
        )
        self.session["end_at"] = None
        self.session["status"] = STATUS_PAUSED
        self._save()

    def resume(self, now: Optional[datetime] = None) -> None:
        if self.session is None or self.session["status"] != STATUS_PAUSED:
            raise ValueError("Pomodoro is not paused")
        now = now or self._now_provider()
        self.session["end_at"] = (
            now + timedelta(seconds=self.session["remaining_seconds"])
        ).isoformat(timespec="seconds")
        self.session["status"] = STATUS_RUNNING
        self._save()

    def stop(self) -> None:
        self.session = None
        self._save()

    def _record_focus(self, ended_at: datetime) -> None:
        date_key = ended_at.strftime("%Y-%m-%d")
        item = self.stats.setdefault(
            date_key,
            {"completed": 0, "focus_minutes": 0},
        )
        item["completed"] += 1
        item["focus_minutes"] += self.session["duration_seconds"] // 60
        self.stats = dict(sorted(self.stats.items())[-400:])

    def tick(self, now: Optional[datetime] = None) -> Optional[PomodoroEvent]:
        now = now or self._now_provider()
        if self.session is None or self.session["status"] != STATUS_RUNNING:
            return None
        end_at = datetime.fromisoformat(self.session["end_at"])
        if now < end_at:
            return None

        completed_phase = self.session["phase"]
        recovered = now > end_at + timedelta(seconds=1)
        completed_in_set = self.session.get("completed_in_set", 0)
        label = self.session.get("label", "")
        if completed_phase == PHASE_FOCUS:
            self._record_focus(end_at)
            completed_in_set += 1
            if completed_in_set % self.settings["long_break_every"] == 0:
                next_phase = PHASE_LONG_BREAK
            else:
                next_phase = PHASE_SHORT_BREAK
            auto_start = self.settings["auto_start_break"]
        else:
            next_phase = PHASE_FOCUS
            auto_start = self.settings["auto_start_focus"]

        if auto_start:
            self._begin(
                next_phase,
                self._duration_for(next_phase),
                now,
                label=label,
                completed_in_set=completed_in_set,
            )
        else:
            self.session = {
                "phase": next_phase,
                "status": STATUS_AWAITING,
                "duration_seconds": self._duration_for(next_phase),
                "remaining_seconds": self._duration_for(next_phase),
                "end_at": None,
                "completed_in_set": completed_in_set,
                "label": label,
            }
            self._save()

        return PomodoroEvent(
            event_type=f"{completed_phase}_completed",
            completed_phase=completed_phase,
            next_phase=next_phase,
            auto_started=auto_start,
            recovered=recovered,
        )

    def snapshot(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or self._now_provider()
        if self.session is None:
            remaining_seconds = self.settings["focus_minutes"] * 60
            duration_seconds = remaining_seconds
            phase = PHASE_FOCUS
            status = STATUS_IDLE
            completed_in_set = 0
            label = ""
        else:
            phase = self.session["phase"]
            status = self.session["status"]
            completed_in_set = self.session.get("completed_in_set", 0)
            label = self.session.get("label", "")
            duration_seconds = self.session["duration_seconds"]
            if status == STATUS_RUNNING:
                end_at = datetime.fromisoformat(self.session["end_at"])
                remaining_seconds = max(
                    0, math.ceil((end_at - now).total_seconds())
                )
            else:
                remaining_seconds = self.session["remaining_seconds"]

        today = self.stats.get(
            now.strftime("%Y-%m-%d"),
            {"completed": 0, "focus_minutes": 0},
        )
        return {
            "phase": phase,
            "status": status,
            "remaining_seconds": remaining_seconds,
            "duration_seconds": duration_seconds,
            "completed_in_set": completed_in_set,
            "label": label,
            "today": dict(today),
        }
