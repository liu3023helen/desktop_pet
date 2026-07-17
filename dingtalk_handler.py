"""
钉钉打卡跳转处理器
优先通过 dingtalk:// 协议启动客户端，失败则降级浏览器打开网页版
"""
import subprocess
import webbrowser
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

# 默认打卡URL
DEFAULT_DINGTALK_URL = "https://im.dingtalk.com/attendancemobile/index.html"
DEFAULT_DINGTALK_PROTOCOL = "dingtalk://dingtalkclient/page/link?pc_slide=false&url=" + DEFAULT_DINGTALK_URL


def open_dingtalk_checkin(reminder_config: Dict[str, Any]) -> bool:
    """
    打开钉钉打卡页面
    
    Args:
        reminder_config: 提醒配置字典
        
    Returns:
        是否成功
    """
    target_url = reminder_config.get("action_target", DEFAULT_DINGTALK_PROTOCOL)

    # 方案1: 尝试通过协议启动钉钉客户端
    try:
        print(f"[DingTalk] 尝试启动钉钉客户端: {target_url}")
        result = subprocess.Popen(
            ["start", "", target_url],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout, stderr = result.communicate(timeout=5)
        
        if result.returncode == 0:
            print("[DingTalk] 钉钉客户端启动成功")
            return True
        else:
            print(f"[DingTalk] 钉钉客户端启动失败: {stderr.decode('gbk', errors='ignore')}")
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
