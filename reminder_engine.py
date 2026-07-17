"""
提醒引擎 - 配置驱动的定时调度器
纯Python实现，不依赖GUI框架
通过回调函数通知主循环触发提醒
"""
import threading
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional


class ReminderEngine:
    """提醒引擎 - 在独立线程中运行定时调度"""

    def __init__(self, config: Dict[str, Any], callback=None):
        """
        Args:
            config: 配置字典
            callback: 提醒触发时的回调函数 reminder_triggered(reminder_dict)
        """
        self.config = config
        self.callback = callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

        # 注册的提醒列表
        self._reminders: List[Dict[str, Any]] = []

        # 已触发的提醒记录（防止同一天重复触发）
        self._triggered_today: set = set()

    def start(self) -> None:
        """启动提醒引擎线程"""
        self._running = True
        self._reminders = self.config.get("reminders", [])
        enabled = [r for r in self._reminders if r.get("enabled", False)]
        print(f"[Engine] 启动，{len(enabled)} 个启用的提醒")
        for r in enabled:
            print(f"  - {r['name']}: {r['time']} ({r.get('action_type', 'unknown')})")

        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """停止引擎"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2)

    def _run_loop(self) -> None:
        """主循环 - 每秒检查一次"""
        while self._running:
            try:
                self._check_reminders()
            except Exception as e:
                print(f"[Engine] 检查提醒时出错: {e}")
            time.sleep(1)

    def _check_reminders(self) -> None:
        """检查是否需要触发提醒"""
        now = datetime.now()
        today_key = now.strftime("%Y-%m-%d")

        # 清理旧的触发记录
        self._triggered_today = {k for k in self._triggered_today if k.startswith(today_key)}

        for reminder in self._reminders:
            if not reminder.get("enabled", False):
                continue

            reminder_time = reminder.get("time", "")
            if not reminder_time:
                continue

            try:
                h, m = map(int, reminder_time.split(":"))
            except ValueError:
                continue

            current_time_key = f"{today_key}_{reminder_time}"

            if now.hour == h and now.minute == m and current_time_key not in self._triggered_today:
                self._triggered_today.add(current_time_key)
                print(f"[Engine] 触发提醒: {reminder['name']}")
                self._trigger_reminder(reminder)

    def _trigger_reminder(self, reminder: Dict[str, Any]) -> None:
        """触发单个提醒"""
        if self.callback:
            try:
                self.callback(reminder)
            except Exception as e:
                print(f"[Engine] 回调执行失败: {e}")
