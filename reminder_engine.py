"""
提醒引擎 - YAML配置驱动的可扩展提醒调度器
策略模式：不同action_type对应不同处理器，新增提醒类型只需改配置
二期增强：网络时间偏移 + 工作日判断 + 贪睡/跳过交互
"""
import logging
import threading
from datetime import datetime, timedelta
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import pyqtSignal, QThread

from snooze_handler import SnoozeManager
from workday_utils import is_workday_from_datetime, set_holiday_override

logger = logging.getLogger(__name__)


def _date_key(dt: datetime) -> str:
    """返回日期字符串 YYYY-MM-DD"""
    return dt.strftime("%Y-%m-%d")


def _validate_reminder(reminder: Any) -> Optional[str]:
    """Return a validation error, or None when a reminder is schedulable."""
    if not isinstance(reminder, dict):
        return "提醒项必须是对象"

    name = reminder.get("name")
    if not isinstance(name, str) or not name.strip():
        return "提醒名称不能为空"

    reminder_time = reminder.get("time")
    if not isinstance(reminder_time, str):
        return "提醒时间必须是 HH:MM 字符串"

    try:
        parsed = datetime.strptime(reminder_time, "%H:%M")
    except ValueError:
        return "提醒时间必须是有效的 HH:MM"

    if parsed.strftime("%H:%M") != reminder_time:
        return "提醒时间必须使用两位 HH:MM 格式"

    for field in ("enabled", "weekdays_only", "sound"):
        if field in reminder and not isinstance(reminder[field], bool):
            return f"{field} 必须是布尔值"

    for field in ("action_type", "action_target", "animation", "message", "sound_file"):
        if field in reminder and not isinstance(reminder[field], str):
            return f"{field} 必须是字符串"

    reminder_id = reminder.get("id")
    if reminder_id is not None and (
        not isinstance(reminder_id, str) or not reminder_id.strip()
    ):
        return "id 必须是非空字符串"

    return None


def _reminder_identity(reminder: Dict[str, Any], index: int) -> str:
    """Return a per-reminder identity while remaining compatible with old config."""
    configured_id = reminder.get("id")
    if isinstance(configured_id, str) and configured_id.strip():
        return configured_id.strip()
    return f"legacy:{index}:{reminder.get('name', '')}"


def _trigger_key(reminder: Dict[str, Any], index: int, today_key: str) -> str:
    return f"{today_key}_{reminder.get('time', '')}_{_reminder_identity(reminder, index)}"


def _bounded_number(value: Any, default: float, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return max(minimum, min(float(value), maximum))


class ReminderEngine(QThread):
    """提醒引擎 - 在独立线程中运行定时调度"""

    # 信号：提醒触发
    reminder_triggered = pyqtSignal(dict)  # 提醒配置字典

    def __init__(self, config: Dict[str, Any], action_handlers: Optional[Dict[str, Callable]] = None):
        super().__init__()
        self.config = config
        holidays = config.get("holidays", {}) if isinstance(config, dict) else {}
        set_holiday_override(holidays)
        self._stop_event = threading.Event()
        self._load_engine_settings(config)

        # 注册的提醒列表
        self._reminders: List[Dict[str, Any]] = []
        self._runtime_identities: Dict[int, str] = {}

        # 动作处理器注册表
        self._handlers: Dict[str, Callable] = action_handlers or {}

        # 已触发的提醒记录（防止同一天重复触发），格式: "YYYY-MM-DD_HH:MM"
        self._triggered_today: set = set()
        # 上次检查的日期，用于跨天重置
        self._last_check_date: Optional[str] = None
        # 上次实际检查时间，用于休眠唤醒后的漏提醒扫描
        self._last_check_at: Optional[datetime] = None

        # --- 二期新增 ---
        # 网络时间偏移量（秒），NTP时间 - 本地时间
        self._time_offset: float = 0.0
        # 贪睡管理器
        self._snooze_mgr = SnoozeManager()
        # 线程锁：保护 _triggered_today 和 _snooze_mgr 的跨线程访问
        self._lock = threading.Lock()

    # --- 网络时间校准 ---
    def set_time_offset(self, offset_seconds: float) -> None:
        """设置网络时间偏移量（秒）"""
        self._time_offset = offset_seconds
        logger.info(f"时间偏移量已设置: {offset_seconds:.1f}秒")

    def get_effective_now(self) -> datetime:
        """获取考虑了网络时间偏移的当前时间"""
        if self._time_offset != 0:
            return datetime.now() + timedelta(seconds=self._time_offset)
        return datetime.now()

    # --- 动作处理器 ---
    def register_handler(self, action_type: str, handler: Callable) -> None:
        """注册动作处理器"""
        self._handlers[action_type] = handler
        logger.info(f"注册动作处理器: {action_type}")

    def _load_engine_settings(self, config: Dict[str, Any]) -> None:
        engine_cfg = config.get("engine", {}) if isinstance(config, dict) else {}
        if not isinstance(engine_cfg, dict):
            engine_cfg = {}
        self._check_interval_sec = _bounded_number(
            engine_cfg.get("check_interval_sec"), 1.0, 0.1, 60.0
        )
        self._sleep_grace_period_sec = int(_bounded_number(
            engine_cfg.get("sleep_grace_period_sec"), 60, 0, 3600
        ))
        self._missed_reminder_retention_hours = int(_bounded_number(
            engine_cfg.get("missed_reminder_retention_hours"), 24, 1, 24
        ))

    def load_reminders(self) -> None:
        """从配置加载提醒"""
        configured = self.config.get("reminders", [])
        if not isinstance(configured, list):
            logger.error("reminders 配置必须是列表，已忽略全部提醒")
            configured = []

        self._reminders = []
        for index, reminder in enumerate(configured):
            error = _validate_reminder(reminder)
            if error:
                logger.error(f"忽略无效提醒 #{index + 1}: {error}")
                continue
            self._reminders.append(reminder)

        self._runtime_identities = {
            id(reminder): _reminder_identity(reminder, index)
            for index, reminder in enumerate(self._reminders)
        }

        enabled = [r for r in self._reminders if r.get("enabled", False)]
        logger.info(f"加载了 {len(enabled)} 个启用的提醒")
        for r in enabled:
            weekdays = "仅工作日" if r.get("weekdays_only", False) else "每天"
            logger.info(f"  - {r['name']}: {r['time']} ({r.get('action_type', 'unknown')}) [{weekdays}]")

    def reload_reminders(self, new_config: Dict[str, Any]) -> None:
        """外部调用：重新加载配置（管理面板修改后）"""
        self.config = new_config
        set_holiday_override(new_config.get("holidays", {}))
        self._load_engine_settings(new_config)
        self.load_reminders()
        self._last_check_at = None

    def start(self, priority=QThread.InheritPriority) -> None:
        """Start with a fresh stop event before the worker can run."""
        if self.isRunning():
            return
        self._stop_event.clear()
        super().start(priority)

    def run(self) -> None:
        """线程主循环 - 每秒检查一次是否需要触发提醒"""
        self.load_reminders()

        while not self._stop_event.is_set():
            try:
                self._check_reminders()
            except Exception as e:
                logger.error(f"检查提醒时出错: {e}")
            self._stop_event.wait(self._check_interval_sec)

    def stop(self) -> None:
        """停止引擎"""
        self._stop_event.set()
        if self.isRunning() and not self.wait(2000):
            logger.error("提醒引擎未能在超时时间内停止")

    def _check_reminders(self) -> None:
        """检查是否需要触发提醒"""
        now = self.get_effective_now()
        today_key = _date_key(now)
        if self._last_check_at is None or now < self._last_check_at:
            window_start = now - timedelta(
                seconds=self._sleep_grace_period_sec
            )
        else:
            retention_start = now - timedelta(
                hours=self._missed_reminder_retention_hours
            )
            window_start = max(self._last_check_at, retention_start)
        self._last_check_at = now

        # 跨天检测：日期变化时清空已触发记录和临时状态
        if self._last_check_date is None:
            self._last_check_date = today_key
        elif today_key != self._last_check_date:
            logger.info(f"日期变更: {self._last_check_date} -> {today_key}，重置触发记录")
            with self._lock:
                self._triggered_today.clear()
                self._snooze_mgr.reset_daily(now)
            self._last_check_date = today_key

        due_reminders = []
        for reminder_index, reminder in enumerate(self._reminders):
            if not reminder.get("enabled", False):
                continue

            reminder_name = reminder.get("name", "")
            reminder_identity = self._runtime_identities[id(reminder)]
            reminder_time = reminder.get("time", "")
            if not reminder_time:
                continue

            # --- 二期：状态检查（加锁保护）---
            with self._lock:
                skipped = self._snooze_mgr.is_skipped(reminder_identity, now=now)
                snooze_time = self._snooze_mgr.get_snooze_time(reminder_identity, now=now)

            if skipped:
                continue

            # --- 二期：贪睡检查 ---
            if snooze_time is not None:
                if now >= snooze_time:
                    with self._lock:
                        self._snooze_mgr.clear_snooze(reminder_identity)
                    logger.info(f"贪睡提醒触发: {reminder_name}")
                    self._trigger_reminder(reminder)
                continue

            # 解析时间 HH:MM
            try:
                parsed_time = datetime.strptime(reminder_time, "%H:%M")
                h, m = parsed_time.hour, parsed_time.minute
            except (TypeError, ValueError):
                logger.warning(f"无效的时间格式: {reminder_time}")
                continue

            candidate_date = window_start.date()
            while candidate_date <= now.date():
                scheduled_at = datetime.combine(
                    candidate_date,
                    parsed_time.time(),
                )
                candidate_date += timedelta(days=1)
                scheduled_minute_end = scheduled_at + timedelta(minutes=1)
                if not (
                    scheduled_at <= now
                    and scheduled_minute_end > window_start
                ):
                    continue
                if (
                    reminder.get("weekdays_only", False)
                    and not is_workday_from_datetime(scheduled_at)
                ):
                    continue

                trigger_key = _trigger_key(
                    reminder,
                    reminder_index,
                    _date_key(scheduled_at),
                )
                with self._lock:
                    if trigger_key in self._triggered_today:
                        continue
                    self._triggered_today.add(trigger_key)
                due_reminders.append(
                    (scheduled_at, reminder_index, reminder, reminder_name)
                )

        due_reminders.sort(key=lambda item: (item[0], item[1]))
        for scheduled_at, _, reminder, reminder_name in due_reminders:
            logger.info(f"触发提醒: {reminder_name}")
            reminder["_triggered_at"] = scheduled_at.isoformat(timespec="seconds")
            try:
                self._trigger_reminder(reminder)
            finally:
                reminder.pop("_triggered_at", None)

    def _trigger_reminder(self, reminder: Dict[str, Any]) -> None:
        """触发单个提醒"""
        payload = dict(reminder)
        payload["_runtime_id"] = self._runtime_identities.get(
            id(reminder), reminder.get("id", reminder.get("name", ""))
        )

        # 1. 发射信号（在主线程处理UI相关逻辑）
        self.reminder_triggered.emit(payload)

        # 2. 执行动作
        action_type = payload.get("action_type", "notify_only")
        handler = self._handlers.get(action_type)

        if handler:
            try:
                handler(payload)
            except Exception as e:
                logger.error(f"执行动作 {action_type} 失败: {e}")
        elif action_type not in {"notify_only", "play_animation"}:
            logger.warning(f"未找到动作处理器: {action_type}")

    # --- 二期：交互处理方法（由主线程通过槽函数调用）---
    def _find_reminder(self, identifier: str):
        for index, reminder in enumerate(self._reminders):
            identity = self._runtime_identities[id(reminder)]
            if identity == identifier:
                return index, reminder, identity
        for index, reminder in enumerate(self._reminders):
            if reminder.get("name") == identifier:
                return index, reminder, self._runtime_identities[id(reminder)]
        return None

    def handle_snooze(self, reminder_identifier: str, minutes: int) -> None:
        """处理贪睡请求（主线程调用）"""
        with self._lock:
            found = self._find_reminder(reminder_identifier)
            if found is None:
                logger.warning(f"未找到要贪睡的提醒: {reminder_identifier}")
                return
            index, reminder, identity = found
            now = self.get_effective_now()
            self._snooze_mgr.snooze(identity, minutes, now=now)
            # 标记为已触发，避免原时间点再次触发
            today_key = _date_key(now)
            if reminder.get("enabled") and reminder.get("time"):
                self._triggered_today.add(_trigger_key(reminder, index, today_key))

    def handle_skip_today(self, reminder_identifier: str) -> None:
        """处理今天跳过请求（主线程调用）"""
        with self._lock:
            found = self._find_reminder(reminder_identifier)
            if found is None:
                logger.warning(f"未找到要跳过的提醒: {reminder_identifier}")
                return
            index, reminder, identity = found
            self._snooze_mgr.skip_today(identity)
            now = self.get_effective_now()
            today_key = _date_key(now)
            if reminder.get("enabled") and reminder.get("time"):
                self._triggered_today.add(_trigger_key(reminder, index, today_key))

    def handle_complete(self, reminder_identifier: str) -> None:
        """Acknowledge only the active occurrence, not the whole reminder."""
        with self._lock:
            found = self._find_reminder(reminder_identifier)
            if found is None:
                logger.warning(f"未找到要完成的提醒: {reminder_identifier}")
                return
            self._snooze_mgr.clear_snooze(found[2])
            logger.info(f"提醒本次触发已确认: {found[2]}")
