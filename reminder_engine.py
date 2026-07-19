"""
提醒引擎 - YAML配置驱动的可扩展提醒调度器
策略模式：不同action_type对应不同处理器，新增提醒类型只需改配置
二期增强：网络时间偏移 + 工作日判断 + 贪睡/跳过/完成交互
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

    # 二期新增信号：交互请求
    snooze_requested = pyqtSignal(str, int)      # 参数: 提醒名称, 延迟分钟数
    skip_today_requested = pyqtSignal(str)        # 参数: 提醒名称
    complete_requested = pyqtSignal(str)          # 参数: 提醒名称

    def __init__(self, config: Dict[str, Any], action_handlers: Optional[Dict[str, Callable]] = None):
        super().__init__()
        self.config = config
        holidays = config.get("holidays", {}) if isinstance(config, dict) else {}
        set_holiday_override(holidays)
        self._stop_event = threading.Event()
        self._load_engine_settings(config)

        # 注册的提醒列表
        self._reminders: List[Dict[str, Any]] = []

        # 动作处理器注册表
        self._handlers: Dict[str, Callable] = action_handlers or {}

        # 已触发的提醒记录（防止同一天重复触发），格式: "YYYY-MM-DD_HH:MM"
        self._triggered_today: set = set()
        # 上次检查的日期，用于跨天重置
        self._last_check_date: Optional[str] = None

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

        # 跨天检测：日期变化时清空已触发记录和临时状态
        if self._last_check_date is None:
            self._last_check_date = today_key
        elif today_key != self._last_check_date:
            logger.info(f"日期变更: {self._last_check_date} -> {today_key}，重置触发记录")
            with self._lock:
                self._triggered_today.clear()
                self._snooze_mgr.reset_daily(now)
            self._last_check_date = today_key

        for reminder_index, reminder in enumerate(self._reminders):
            if not reminder.get("enabled", False):
                continue

            reminder_name = reminder.get("name", "")
            reminder_time = reminder.get("time", "")
            if not reminder_time:
                continue

            # --- 二期：工作日判断 ---
            if reminder.get("weekdays_only", False) and not is_workday_from_datetime(now):
                continue

            # --- 二期：状态检查（加锁保护）---
            with self._lock:
                skipped = self._snooze_mgr.is_skipped(reminder_name, now=now)
                completed = self._snooze_mgr.is_completed(reminder_name, now=now)
                snooze_time = self._snooze_mgr.get_snooze_time(reminder_name, now=now)

            if skipped or completed:
                continue

            # --- 二期：贪睡检查 ---
            if snooze_time is not None:
                if now >= snooze_time:
                    with self._lock:
                        self._snooze_mgr.clear_snooze(reminder_name)
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

            current_time_key = _trigger_key(reminder, reminder_index, today_key)

            # 检查是否已到时间且今天未触发
            # 休眠唤醒容错：检查当前时间及过去 60 秒内是否有未触发的提醒
            triggered = False
            for offset in range(self._sleep_grace_period_sec + 1):
                check_time = now - timedelta(seconds=offset)
                if check_time.hour == h and check_time.minute == m:
                    with self._lock:
                        if current_time_key not in self._triggered_today:
                            self._triggered_today.add(current_time_key)
                            triggered = True
                    break

            if triggered:
                logger.info(f"触发提醒: {reminder_name}")
                self._trigger_reminder(reminder)

    def _trigger_reminder(self, reminder: Dict[str, Any]) -> None:
        """触发单个提醒"""
        reminder_name = reminder.get("name", "")

        # 1. 发射信号（在主线程处理UI相关逻辑）
        self.reminder_triggered.emit(reminder)

        # 2. 执行动作
        action_type = reminder.get("action_type", "notify_only")
        handler = self._handlers.get(action_type)

        if handler:
            try:
                handler(reminder)
            except Exception as e:
                logger.error(f"执行动作 {action_type} 失败: {e}")
        elif action_type not in {"notify_only", "play_animation"}:
            logger.warning(f"未找到动作处理器: {action_type}")

    # --- 二期：交互处理方法（由主线程通过槽函数调用）---
    def handle_snooze(self, reminder_name: str, minutes: int) -> None:
        """处理贪睡请求（主线程调用）"""
        with self._lock:
            now = self.get_effective_now()
            self._snooze_mgr.snooze(reminder_name, minutes, now=now)
            # 标记为已触发，避免原时间点再次触发
            now = self.get_effective_now()
            today_key = _date_key(now)
            for index, r in enumerate(self._reminders):
                if r.get("name") == reminder_name and r.get("enabled"):
                    time_str = r.get("time", "")
                    if time_str:
                        self._triggered_today.add(_trigger_key(r, index, today_key))
                    break

    def handle_skip_today(self, reminder_name: str) -> None:
        """处理今天跳过请求（主线程调用）"""
        with self._lock:
            self._snooze_mgr.skip_today(reminder_name)
            now = self.get_effective_now()
            today_key = _date_key(now)
            for index, r in enumerate(self._reminders):
                if r.get("name") == reminder_name and r.get("enabled"):
                    time_str = r.get("time", "")
                    if time_str:
                        self._triggered_today.add(_trigger_key(r, index, today_key))
                    break

    def handle_complete(self, reminder_name: str) -> None:
        """处理完成请求（主线程调用）"""
        with self._lock:
            self._snooze_mgr.complete(reminder_name)
