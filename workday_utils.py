"""
工作日判断工具 - 纯本地实现，不依赖网络
预留法定节假日扩展接口
"""
from datetime import datetime, date
from typing import Optional, Set


# --- 法定节假日/调休配置（手动维护或从网络更新）---
# 格式: "YYYY-MM-DD": True(调休上班) / False(法定假日)
# True 表示虽然是周末但需要上班，False 表示虽然是工作日但是假日
HOLIDAY_OVERRIDE: dict = {}


def set_holiday_override(holidays: dict) -> None:
    """设置节假日覆盖规则（从网络接口获取后调用）"""
    global HOLIDAY_OVERRIDE
    HOLIDAY_OVERRIDE = holidays


def is_weekend(d: Optional[date] = None) -> bool:
    """判断指定日期是否为周末（周六=5，周日=6）"""
    if d is None:
        d = date.today()
    return d.weekday() >= 5


def is_workday_override(d: Optional[date] = None) -> Optional[bool]:
    """
    检查节假日覆盖规则
    返回: True=调休上班, False=法定假日, None=无覆盖按正常周末判断
    """
    if d is None:
        d = date.today()
    key = d.strftime("%Y-%m-%d")
    return HOLIDAY_OVERRIDE.get(key)


def is_workday(d: Optional[date] = None) -> bool:
    """
    判断指定日期是否为工作日
    优先级: 节假日覆盖 > 常规周末判断
    """
    if d is None:
        d = date.today()

    # 先检查节假日覆盖
    override = is_workday_override(d)
    if override is not None:
        return override

    # 默认：周一到周五为工作日
    return not is_weekend(d)


def is_workday_from_datetime(dt: Optional[datetime] = None) -> bool:
    """从datetime对象判断是否为工作日"""
    if dt is None:
        dt = datetime.now()
    return is_workday(dt.date())


def get_next_workday(d: Optional[date] = None, days_ahead: int = 1) -> date:
    """获取从今天起第N个工作日"""
    from datetime import timedelta
    if d is None:
        d = date.today()
    current = d
    count = 0
    while count < days_ahead:
        current = current + timedelta(days=1)
        if is_workday(current):
            count += 1
    return current
