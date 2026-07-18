"""
提醒引擎 - YAML配置驱动的可扩展提醒调度器
策略模式：不同action_type对应不同处理器，新增提醒类型只需改配置
二期增强：网络时间偏移 + 工作日判断 + 贪睡/跳过/完成交互
"""
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QMessageBox

from snooze_handler import SnoozeManager
from workday_utils import is_workday_from_datetime

logger = logging.getLogger(__name__)


def _date_key(dt: datetime) -> str:
    """返回日期字符串 YYYY-MM-DD"""
    return dt.strftime("%Y-%m-%d")


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
        self._running = False

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

    def load_reminders(self) -> None:
        """从配置加载提醒"""
        self._reminders = self.config.get("reminders", [])
        enabled = [r for r in self._reminders if r.get("enabled", False)]
        logger.info(f"加载了 {len(enabled)} 个启用的提醒")
        for r in enabled:
            weekdays = "仅工作日" if r.get("weekdays_only", False) else "每天"
            logger.info(f"  - {r['name']}: {r['time']} ({r.get('action_type', 'unknown')}) [{weekdays}]")

    def reload_reminders(self, new_config: Dict[str, Any]) -> None:
        """外部调用：重新加载配置（管理面板修改后）"""
        self.config = new_config
        self.load_reminders()

    def run(self) -> None:
        """线程主循环 - 每秒检查一次是否需要触发提醒"""
        self._running = True
        self.load_reminders()

        while self._running:
            try:
                self._check_reminders()
            except Exception as e:
                logger.error(f"检查提醒时出错: {e}")
            time.sleep(1)  # 精度1秒

    def stop(self) -> None:
        """停止引擎"""
        self._running = False
        self.wait(1000)

    def _check_reminders(self) -> None:
        """检查是否需要触发提醒"""
        now = self.get_effective_now()
        today_key = _date_key(now)

        # 跨天检测：日期变化时清空已触发记录和临时状态
        if self._last_check_date is not None and today_key != self._last_check_date:
            logger.info(f"日期变更: {self._last_check_date} -> {today_key}，重置触发记录")
            with self._lock:
                self._triggered_today.clear()
                self._snooze_mgr.reset_daily()
            self._last_check_date = today_key

        for reminder in self._reminders:
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
                skipped = self._snooze_mgr.is_skipped(reminder_name)
                completed = self._snooze_mgr.is_completed(reminder_name)
                snoozed = self._snooze_mgr.is_snoozed(reminder_name)
                should_snooze_trigger = self._snooze_mgr.should_trigger_snooze(reminder_name) if snoozed else False

            if skipped or completed:
                continue

            # --- 二期：贪睡检查 ---
            if snoozed:
                if should_snooze_trigger:
                    with self._lock:
                        self._snooze_mgr.clear_snooze(reminder_name)
                    logger.info(f"贪睡提醒触发: {reminder_name}")
                    self._trigger_reminder(reminder)
                continue

            # 解析时间 HH:MM
            try:
                h, m = map(int, reminder_time.split(":"))
            except ValueError:
                logger.warning(f"无效的时间格式: {reminder_time}")
                continue

            current_time_key = f"{today_key}_{reminder_time}"

            # 检查是否已到时间且今天未触发
            with self._lock:
                already_triggered = current_time_key in self._triggered_today
                if not already_triggered:
                    self._triggered_today.add(current_time_key)

            if not already_triggered and now.hour == h and now.minute == m:
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
        else:
            logger.warning(f"未找到动作处理器: {action_type}")

    # --- 二期：交互处理方法（由主线程通过槽函数调用）---
    def handle_snooze(self, reminder_name: str, minutes: int) -> None:
        """处理贪睡请求（主线程调用）"""
        with self._lock:
            self._snooze_mgr.snooze(reminder_name, minutes)
            # 标记为已触发，避免原时间点再次触发
            now = self.get_effective_now()
            today_key = _date_key(now)
            for r in self._reminders:
                if r.get("name") == reminder_name and r.get("enabled"):
                    time_str = r.get("time", "")
                    if time_str:
                        self._triggered_today.add(f"{today_key}_{time_str}")
                    break

    def handle_skip_today(self, reminder_name: str) -> None:
        """处理今天跳过请求（主线程调用）"""
        with self._lock:
            self._snooze_mgr.skip_today(reminder_name)
            now = self.get_effective_now()
            today_key = _date_key(now)
            for r in self._reminders:
                if r.get("name") == reminder_name and r.get("enabled"):
                    time_str = r.get("time", "")
                    if time_str:
                        self._triggered_today.add(f"{today_key}_{time_str}")
                    break

    def handle_complete(self, reminder_name: str) -> None:
        """处理完成请求（主线程调用）"""
        with self._lock:
            self._snooze_mgr.complete(reminder_name)
