"""
贪睡/跳过/完成状态管理器
管理提醒的临时状态，程序重启后自动失效（不持久化）
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Optional, Set

logger = logging.getLogger(__name__)


class SnoozeManager:
    """贪睡管理器 - 维护提醒的临时状态"""

    def __init__(self):
        # 贪睡的提醒: reminder_name -> 下次触发时间
        self._snoozed: Dict[str, datetime] = {}
        # 今天跳过的提醒名称集合
        self._skipped_today: Set[str] = set()
        # 已完成的提醒（本次触发周期）
        self._completed: Set[str] = set()
        # 上次重置日期，用于跨天自动清理
        self._last_reset_date: Optional[str] = None

    def _check_daily_reset(self) -> None:
        """检查是否需要跨天重置"""
        today_key = datetime.now().strftime("%Y-%m-%d")
        if self._last_reset_date is not None and today_key != self._last_reset_date:
            logger.info("日期变更，重置所有临时状态")
            self.reset_daily()
        self._last_reset_date = today_key

    def reset_daily(self) -> None:
        """跨天重置所有临时状态"""
        self._snoozed.clear()
        self._skipped_today.clear()
        self._completed.clear()
        self._last_reset_date = datetime.now().strftime("%Y-%m-%d")

    # --- 贪睡 ---
    def snooze(self, reminder_name: str, minutes: int = 5) -> None:
        """将提醒设为贪睡状态，延迟N分钟"""
        next_time = datetime.now() + timedelta(minutes=minutes)
        self._snoozed[reminder_name] = next_time
        # 贪睡时自动清除跳过和完成状态
        self._skipped_today.discard(reminder_name)
        self._completed.discard(reminder_name)
        logger.info(f"'{reminder_name}' 贪睡 {minutes} 分钟，下次触发: {next_time.strftime('%H:%M')}")

    def get_snooze_time(self, reminder_name: str) -> Optional[datetime]:
        """获取提醒的贪睡触发时间，None表示未贪睡"""
        self._check_daily_reset()
        return self._snoozed.get(reminder_name)

    def clear_snooze(self, reminder_name: str) -> None:
        """清除提醒的贪睡状态（触发后调用）"""
        self._snoozed.pop(reminder_name, None)

    def is_snoozed(self, reminder_name: str) -> bool:
        """检查提醒是否处于贪睡状态且尚未到触发时间"""
        self._check_daily_reset()
        snooze_time = self._snoozed.get(reminder_name)
        if snooze_time is None:
            return False
        # 还没到贪睡时间
        return datetime.now() < snooze_time

    def should_trigger_snooze(self, reminder_name: str) -> bool:
        """检查贪睡的提醒是否已到触发时间"""
        self._check_daily_reset()
        snooze_time = self._snoozed.get(reminder_name)
        if snooze_time is None:
            return False
        return datetime.now() >= snooze_time

    # --- 跳过今天 ---
    def skip_today(self, reminder_name: str) -> None:
        """将提醒设为今天跳过"""
        self._skipped_today.add(reminder_name)
        # 跳过时清除贪睡状态
        self._snoozed.pop(reminder_name, None)
        self._completed.discard(reminder_name)
        logger.info(f"'{reminder_name}' 今天跳过")

    def is_skipped(self, reminder_name: str) -> bool:
        """检查提醒是否被今天跳过"""
        self._check_daily_reset()
        return reminder_name in self._skipped_today

    # --- 完成 ---
    def complete(self, reminder_name: str) -> None:
        """标记提醒为已完成（本次触发周期）"""
        self._completed.add(reminder_name)
        # 完成时清除贪睡和跳过状态
        self._snoozed.pop(reminder_name, None)
        self._skipped_today.discard(reminder_name)
        logger.info(f"'{reminder_name}' 标记为已完成")

    def is_completed(self, reminder_name: str) -> bool:
        """检查提醒是否已完成"""
        self._check_daily_reset()
        return reminder_name in self._completed

    # --- 状态查询 ---
    def get_all_status(self) -> dict:
        """获取所有状态摘要"""
        self._check_daily_reset()
        return {
            "snoozed": {k: v.strftime("%H:%M:%S") for k, v in self._snoozed.items()},
            "skipped": list(self._skipped_today),
            "completed": list(self._completed),
        }
