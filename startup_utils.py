"""
启动工具集 - 开机自启/数据目录/日志配置/素材检查
从 main.py 抽离，减少主文件职责
"""
import logging
import os
import shutil
import subprocess
import sys
import winreg
import winsound
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QMessageBox, QWidget

from utils import get_app_dir, get_exe_path


# --- 开机自启管理 ---
APP_NAME = "DesktopPet"
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"


def get_autostart_command() -> str:
    """Build a quoted Windows command for frozen and development modes."""
    app_path = get_exe_path()
    if getattr(sys, "frozen", False):
        return subprocess.list2cmdline([app_path])

    interpreter = Path(sys.executable)
    pythonw = interpreter.with_name("pythonw.exe")
    launcher = pythonw if pythonw.exists() else interpreter
    return subprocess.list2cmdline([str(launcher), app_path])


def is_auto_start_enabled() -> bool:
    """检查开机自启是否已启用（仅检查注册表是否有值）"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return bool(value)
        except FileNotFoundError:
            winreg.CloseKey(key)
            return False
    except OSError:
        return False


def get_registered_autostart_path() -> Optional[str]:
    """获取注册表中记录的开机自启路径"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            winreg.CloseKey(key)
            return value
        except FileNotFoundError:
            winreg.CloseKey(key)
            return None
    except OSError:
        return None


def cleanup_stale_autostart() -> bool:
    """检测并清理失效的开机自启注册表条目"""
    registered_path = get_registered_autostart_path()
    if registered_path is None:
        return True
    
    current_path = get_exe_path()
    current_command = get_autostart_command()
    if registered_path in {current_path, current_command}:
        return True
    
    if os.path.exists(registered_path):
        return True
    
    logger = logging.getLogger(__name__)
    logger.warning(f"检测到失效的开机自启路径: {registered_path}，当前路径: {current_path}")
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
        winreg.DeleteValue(key, APP_NAME)
        winreg.CloseKey(key)
        logger.info("已清理失效的开机自启注册表条目")
        return True
    except OSError as e:
        logger.error(f"清理失效的开机自启注册表条目失败: {e}")
        return False


def set_auto_start(enabled: bool) -> bool:
    """设置开机自启。启用时会先清理旧路径再写入新路径"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_WRITE)
        if enabled:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
            command = get_autostart_command()
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, command)
            logging.getLogger(__name__).info(f"开机自启已启用: {command}")
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
                logging.getLogger(__name__).info("开机自启已禁用")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
        return True
    except OSError as e:
        logging.getLogger(__name__).error(f"设置开机自启失败: {e}")
        return False


# --- 应用数据目录 ---
def ensure_data_dir():
    """首次运行时创建 data 目录并复制默认配置文件"""
    data_dir = get_app_dir() / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    default_config = data_dir / "config.yaml"
    if not default_config.exists():
        try:
            if getattr(sys, 'frozen', False):
                bundled = Path(sys._MEIPASS) / "config.yaml"
            else:
                bundled = get_app_dir() / "config.yaml"
            if bundled.exists():
                shutil.copy2(bundled, default_config)
                logging.getLogger(__name__).info(f"已复制默认配置: {default_config}")
        except Exception as e:
            logging.getLogger(__name__).warning(f"复制默认配置失败: {e}")


# --- 日志配置 ---
def setup_logging(level: str = "INFO", log_file: Optional[str] = None) -> logging.Logger:
    """配置日志系统
    
    Args:
        level: 日志级别 (DEBUG/INFO/WARNING/ERROR)
        log_file: 日志文件路径，相对于 app_dir/data/logs/
    """
    log_dir = get_app_dir() / "data" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    if log_file is None:
        log_file = "pet.log"
    
    log_path = log_dir / log_file
    
    # 确保根 logger 只配置一次
    root_logger = logging.getLogger()
    if not root_logger.handlers:
        logging.basicConfig(
            level=getattr(logging, level.upper(), logging.INFO),
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(log_path, encoding="utf-8"),
                logging.StreamHandler()
            ]
        )
    
    return logging.getLogger("DesktopPet")


# --- 音效播放 ---
DEFAULT_SOUND_FILE = "assets/sounds/reminder.wav"


def play_reminder_sound(sound_file: str = None):
    """播放提醒提示音
    
    Args:
        sound_file: 相对路径的音频文件（WAV格式），如 "assets/sounds/xxx.wav"。
                    为空则使用默认提示音。
                    兼容旧格式：仅有文件名（如 "xxx.wav"）会自动补全路径。
    """
    try:
        if not sound_file:
            file_to_play = DEFAULT_SOUND_FILE
        elif os.sep in sound_file or "/" in sound_file:
            # 已包含路径分隔符，直接使用
            file_to_play = sound_file
        else:
            # 旧格式：仅有文件名，自动补全 assets/sounds/ 前缀
            file_to_play = os.path.join("assets", "sounds", sound_file)
        
        if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
            sound_path = Path(sys._MEIPASS) / file_to_play
        else:
            sound_path = get_app_dir() / file_to_play
        
        if sound_path.exists():
            winsound.PlaySound(str(sound_path), winsound.SND_FILENAME | winsound.SND_ASYNC)
            logging.getLogger(__name__).debug(f"播放提示音: {sound_path}")
        else:
            logging.getLogger(__name__).warning(f"提示音文件不存在: {sound_path}")
    except Exception as e:
        logging.getLogger(__name__).error(f"播放提示音失败: {e}")


# --- 素材检查 ---
REQUIRED_ANIMATIONS = ("cheer",)


def check_assets(pet_window: QWidget) -> None:
    """启动时检查素材完整性，缺失时弹出警告
    
    Args:
        pet_window: 宠物窗口实例，用于延迟显示警告对话框
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        assets_dir = Path(sys._MEIPASS) / "assets" / "animations"
    else:
        assets_dir = get_app_dir() / "assets" / "animations"
    
    missing = []
    empty = []
    for anim_name in REQUIRED_ANIMATIONS:
        anim_dir = assets_dir / anim_name
        if not anim_dir.exists():
            missing.append(anim_name)
        elif not any(anim_dir.glob("*.png")):
            empty.append(anim_name)

    issues = []
    if missing:
        issues.append(f"缺失目录: {', '.join(missing)}")
    if empty:
        issues.append(f"目录为空: {', '.join(empty)}")

    if issues:
        msg = (
            f"素材不完整，宠物可能无法正常显示。\n\n"
            f"{''.join(issues)}\n\n"
            f"请检查 assets/animations/ 目录下是否有对应的 PNG 序列帧文件。"
        )
        logging.getLogger(__name__).warning(msg)
        QTimer.singleShot(500, lambda: QMessageBox.warning(
            pet_window, "素材缺失", msg, QMessageBox.Ok
        ))
