"""
公共工具函数 - 路径获取等跨模块复用逻辑
"""
import sys
from pathlib import Path


def get_app_dir() -> Path:
    """获取应用根目录（兼容开发模式和 PyInstaller 打包模式）

    - 开发模式: 返回项目根目录
    - 打包模式: 返回 exe 所在目录
    """
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).parent


def get_exe_path() -> str:
    """获取当前 exe（或脚本）的绝对路径"""
    if getattr(sys, 'frozen', False):
        return sys.executable
    return str(Path(sys.argv[0]).resolve())


def get_resource_path(relative_path: str) -> Path:
    """获取资源文件的绝对路径（兼容开发模式和 PyInstaller 打包模式）

    Args:
        relative_path: 相对于应用目录的路径，如 "assets/animations/cheer"
    """
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return get_app_dir() / relative_path
