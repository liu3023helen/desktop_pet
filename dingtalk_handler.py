"""
钉钉打卡跳转处理器
优先通过 dingtalk:// 协议启动客户端，失败则降级浏览器打开网页版
安全策略：URL 白名单校验 + os.startfile 替代 shell=True
"""
import os
import re
import webbrowser
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 允许的 URL 协议白名单
_ALLOWED_URL_SCHEMES = frozenset(("dingtalk://", "https://", "http://"))

# 默认打卡URL
DEFAULT_DINGTALK_URL = "https://im.dingtalk.com/attendancemobile/index.html"
DEFAULT_DINGTALK_PROTOCOL = "dingtalk://dingtalkclient/page/link?pc_slide=false&url=" + DEFAULT_DINGTALK_URL


def _is_safe_url(url: str) -> bool:
    """URL 白名单校验：仅允许 dingtalk:// 和 http(s):// 协议"""
    if not isinstance(url, str):
        return False
    url_lower = url.lower().strip()
    if not url_lower:
        return False
    # 额外防御：拒绝包含命令注入特征的输入
    if re.search(r'[;&|`$]', url):
        return False
    return any(url_lower.startswith(scheme) for scheme in _ALLOWED_URL_SCHEMES)


def open_dingtalk_checkin(reminder_config: Dict[str, Any]) -> bool:
    """
    打开钉钉打卡页面
    
    Args:
        reminder_config: 提醒配置字典
        
    Returns:
        是否成功
    """
    target_url = reminder_config.get("action_target", DEFAULT_DINGTALK_PROTOCOL)

    # 安全校验：URL 白名单
    if not _is_safe_url(target_url):
        print(f"[DingTalk] URL 未通过白名单校验: {target_url}")
        return False

    # 方案1: 使用 os.startfile 启动关联程序（无 shell 注入风险）
    try:
        print(f"[DingTalk] 尝试启动钉钉客户端: {target_url}")
        os.startfile(target_url)
        print("[DingTalk] 钉钉客户端启动成功")
        return True
    except OSError as e:
        print(f"[DingTalk] 钉钉客户端启动失败: {e}")
    except Exception as e:
        print(f"[DingTalk] 启动钉钉客户端异常: {e}")

    # 方案2: 降级到浏览器打开网页版
    return open_browser_checkin(reminder_config)


def open_browser_checkin(reminder_config: Dict[str, Any]) -> bool:
    """
    浏览器打开钉钉网页版打卡
    
    Args:
        reminder_config: 提醒配置字典
        
    Returns:
        是否成功
    """
    try:
        web_url = reminder_config.get("action_target", DEFAULT_DINGTALK_URL)
        # 如果不是http开头，使用默认网页URL
        if not web_url.startswith("http"):
            web_url = DEFAULT_DINGTALK_URL
            
        print(f"[DingTalk] 降级打开浏览器: {web_url}")
        webbrowser.open(web_url)
        return True
    except Exception as e:
        logger.error(f"[DingTalk] 浏览器打开失败: {e}")
        return False
