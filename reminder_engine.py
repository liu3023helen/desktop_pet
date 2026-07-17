"""
提醒引擎 - YAML配置驱动的可扩展提醒调度器
策略模式：不同action_type对应不同处理器，新增提醒类型只需改配置
"""
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from PyQt5.QtCore import QObject, pyqtSignal, QThread
from PyQt5.QtWidgets import QMessageBox


def _date_key(dt: datetime) -> str:
    """返回日期字符串 YYYY-MM-DD"""
    return dt.strftime("%Y-%m-%d")


class ReminderEngine(QThread):
    """提醒引擎 - 在独立线程中运行定时调度"""

    # 信号：提醒触发
    reminder_triggered = pyqtSignal(dict)  # 提醒配置字典

    def __init__(self, config: Dict[str, Any], pet_window=None, action_handlers: Optional[Dict[str, Callable]] = None):
        super().__init__()
        self.config = config
        self.pet_window = pet_window
        self._running = False

        # 注册的提醒列表
        self._reminders: List[Dict[str, Any]] = []

        # 动作处理器注册表
        self._handlers: Dict[str, Callable] = action_handlers or {}

        # 已触发的提醒记录（防止同一天重复触发），格式: "YYYY-MM-DD_HH:MM"
        self._triggered_today: set = set()
        # 上次检查的日期，用于跨天重置
        self._last_check_date: Optional[str] = None

    def register_handler(self, action_type: str, handler: Callable) -> None:
        """注册动作处理器"""
        self._handlers[action_type] = handler
        print(f"[Engine] 注册动作处理器: {action_type}")

    def load_reminders(self) -> None:
        """从配置加载提醒"""
        self._reminders = self.config.get("reminders", [])
        enabled = [r for r in self._reminders if r.get("enabled", False)]
        print(f"[Engine] 加载了 {len(enabled)} 个启用的提醒")
        for r in enabled:
            print(f"  - {r['name']}: {r['time']} ({r.get('action_type', 'unknown')})")

    def run(self) -> None:
        """线程主循环 - 每秒检查一次是否需要触发提醒"""
        self._running = True
        self.load_reminders()

        while self._running:
            try:
                self._check_reminders()
            except Exception as e:
                print(f"[Engine] 检查提醒时出错: {e}")
            time.sleep(1)  # 精度1秒

    def stop(self) -> None:
        """停止引擎"""
        self._running = False
        self.wait(1000)

    def _check_reminders(self) -> None:
        """检查是否需要触发提醒"""
        now = datetime.now()
        today_key = _date_key(now)

        # 跨天检测：日期变化时清空已触发记录
        if self._last_check_date is not None and today_key != self._last_check_date:
            print(f"[Engine] 日期变更: {self._last_check_date} -> {today_key}，重置触发记录")
            self._triggered_today.clear()
        self._last_check_date = today_key

        for reminder in self._reminders:
            if not reminder.get("enabled", False):
                continue

            reminder_time = reminder.get("time", "")
            if not reminder_time:
                continue

            # 解析时间 HH:MM
            try:
                h, m = map(int, reminder_time.split(":"))
            except ValueError:
                print(f"[Engine] 无效的时间格式: {reminder_time}")
                continue

            current_time_key = f"{today_key}_{reminder_time}"

            # 检查是否已到时间且今天未触发
            if now.hour == h and now.minute == m and current_time_key not in self._triggered_today:
                self._triggered_today.add(current_time_key)
                print(f"[Engine] 触发提醒: {reminder['name']}")
                self._trigger_reminder(reminder)

    def _trigger_reminder(self, reminder: Dict[str, Any]) -> None:
        """触发单个提醒"""
        # 1. 发射信号（在主线程处理UI相关逻辑）
        self.reminder_triggered.emit(reminder)

        # 2. 执行动作
        action_type = reminder.get("action_type", "notify_only")
        handler = self._handlers.get(action_type)

        if handler:
            try:
                handler(reminder)
            except Exception as e:
                print(f"[Engine] 执行动作 {action_type} 失败: {e}")
        else:
            print(f"[Engine] 未找到动作处理器: {action_type}")
