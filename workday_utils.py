"""
工作日判断工具 - 纯本地实现，不依赖网络
支持从 config.yaml 读取法定节假日/调休配置
"""
import logging
from datetime import datetime, date
from pathlib import Path
from typing import Optional

from utils import get_app_dir

logger = logging.getLogger(__name__)


# Published mainland China holiday arrangements. User configuration always
# takes precedence, so corrections can be shipped without replacing the app.
BUILTIN_HOLIDAY_OVERRIDE = {
    # 2026 New Year's Day
    "2026-01-01": False,
    "2026-01-02": False,
    "2026-01-03": False,
    "2026-01-04": True,
    # 2026 Spring Festival
    **{f"2026-02-{day:02d}": False for day in range(15, 24)},
    "2026-02-14": True,
    "2026-02-28": True,
    # 2026 Qingming Festival
    "2026-04-04": False,
    "2026-04-05": False,
    "2026-04-06": False,
    # 2026 Labour Day
    **{f"2026-05-{day:02d}": False for day in range(1, 6)},
    "2026-05-09": True,
    # 2026 Dragon Boat Festival
    "2026-06-19": False,
    "2026-06-20": False,
    "2026-06-21": False,
    # 2026 Mid-Autumn Festival
    "2026-09-25": False,
    "2026-09-26": False,
    "2026-09-27": False,
    # 2026 National Day
    **{f"2026-10-{day:02d}": False for day in range(1, 8)},
    "2026-09-20": True,
    "2026-10-10": True,
}
BUILTIN_CALENDAR_YEARS = frozenset(
    int(key[:4]) for key in BUILTIN_HOLIDAY_OVERRIDE
)
_WARNED_MISSING_YEARS = set()


def _get_data_dir():
    """获取 data 目录路径"""
    return get_app_dir() / "data"


# --- 法定节假日/调休配置（从 config.yaml 自动加载）---
# 格式: "YYYY-MM-DD": True(调休上班) / False(法定假日)
# True 表示虽然是周末但需要上班，False 表示虽然是工作日但是假日
HOLIDAY_OVERRIDE: dict = {}


def _normalize_holiday_overrides(holidays: dict) -> dict:
    """Normalize YAML date keys and ignore malformed override values."""
    if not isinstance(holidays, dict):
        logger.warning("holidays 配置必须是对象，已忽略")
        return {}

    normalized = {}
    for raw_key, raw_value in holidays.items():
        if isinstance(raw_key, (datetime, date)):
            key = raw_key.strftime("%Y-%m-%d")
        elif isinstance(raw_key, str):
            try:
                key = datetime.strptime(raw_key, "%Y-%m-%d").strftime("%Y-%m-%d")
            except ValueError:
                logger.warning(f"忽略无效节假日日期: {raw_key}")
                continue
        else:
            logger.warning(f"忽略无效节假日日期: {raw_key}")
            continue

        if not isinstance(raw_value, bool):
            logger.warning(f"忽略非布尔节假日规则: {key}={raw_value!r}")
            continue
        normalized[key] = raw_value

    return normalized


def load_holidays_from_yaml(config_path: Optional[Path] = None) -> dict:
    """从 YAML 配置文件加载节假日数据
    
    Args:
        config_path: 配置文件路径，默认使用 data/config.yaml
        
    Returns:
        节假日字典 {"YYYY-MM-DD": bool}
    """
    if config_path is None:
        config_path = _get_data_dir() / "config.yaml"
    
    if not config_path.exists():
        logger.warning(f"配置文件不存在: {config_path}")
        return {}
    
    try:
        import yaml
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
        
        holidays = config.get("holidays", {})
        if holidays:
            logger.info(f"从配置加载了 {len(holidays)} 条节假日规则")
            return dict(holidays)
        else:
            logger.debug("配置文件中无节假日数据")
            return {}
    except Exception as e:
        logger.error(f"加载节假日配置失败: {e}")
        return {}


def load_holidays() -> None:
    """从配置文件加载节假日数据到全局 HOLIDAY_OVERRIDE"""
    global HOLIDAY_OVERRIDE
    HOLIDAY_OVERRIDE = _normalize_holiday_overrides(load_holidays_from_yaml())


# 模块初始化时自动加载
load_holidays()


def set_holiday_override(holidays: dict) -> None:
    """设置节假日覆盖规则（运行时动态更新）"""
    global HOLIDAY_OVERRIDE
    HOLIDAY_OVERRIDE = _normalize_holiday_overrides(holidays)


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
    if key in HOLIDAY_OVERRIDE:
        return HOLIDAY_OVERRIDE[key]
    return BUILTIN_HOLIDAY_OVERRIDE.get(key)


def has_builtin_calendar(year: int) -> bool:
    """Return whether an official built-in calendar covers the given year."""
    return year in BUILTIN_CALENDAR_YEARS


def is_workday(d: Optional[date] = None) -> bool:
    """
    判断指定日期是否为工作日
    优先级: 节假日覆盖 > 常规周末判断
    """
    if d is None:
        d = date.today()

    if (
        BUILTIN_CALENDAR_YEARS
        and d.year > max(BUILTIN_CALENDAR_YEARS)
        and d.year not in _WARNED_MISSING_YEARS
    ):
        logger.warning(
            f"未内置 {d.year} 年法定节假日日历，暂按周一至周五判断；"
            "可在 holidays 配置中手工覆盖"
        )
        _WARNED_MISSING_YEARS.add(d.year)

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


def is_rest_day(d: Optional[date] = None) -> bool:
    """Return True for weekends and statutory holidays, excluding work swaps."""
    return not is_workday(d)


def is_rest_day_from_datetime(dt: Optional[datetime] = None) -> bool:
    """Return whether the date portion of a datetime is a rest day."""
    if dt is None:
        dt = datetime.now()
    return is_rest_day(dt.date())


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
