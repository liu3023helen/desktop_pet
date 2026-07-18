"""
序列帧动画播放器
支持多套PNG序列帧动画加载、帧率控制、alpha透明合成、平滑切换
"""
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Callable

from PyQt5.QtWidgets import QLabel
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QPixmap

logger = logging.getLogger(__name__)


def _get_resource_path(relative_path: str) -> Path:
    """获取资源文件的绝对路径（兼容开发模式和PyInstaller打包模式）"""
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path


class AnimationPlayer:
    """序列帧动画播放器"""

    def __init__(self, assets_dir: Optional[str] = None):
        if assets_dir:
            self.assets_dir = Path(assets_dir)
        else:
            self.assets_dir = _get_resource_path("assets/animations")

        # 已加载的动画帧缓存 {动画名: [QPixmap列表]}
        self._frames_cache: Dict[str, List[QPixmap]] = {}

        # 当前播放状态
        self._current_animation: Optional[str] = None
        self._current_frame_index: int = 0
        self._fps: int = 8

        # 定时器
        self._timer = QTimer()
        self._timer.setSingleShot(False)

        # 绑定到外部label用于显示
        self._target_label: Optional[QLabel] = None

        # 帧切换回调（用于通知窗口更新）
        self._on_frame_changed: Optional[Callable[[str, int], None]] = None

    def bind(self, label: QLabel) -> None:
        """绑定显示目标"""
        self._target_label = label

    def set_callback(self, callback: Callable[[str, int], None]) -> None:
        """设置帧切换回调"""
        self._on_frame_changed = callback

    def load_animation(self, name: str, fps: int = 8) -> bool:
        """
        加载指定名称的序列帧动画

        Args:
            name: 动画名称（对应子目录名，如 idle/walk/cheer）
            fps: 帧率

        Returns:
            是否加载成功
        """
        anim_dir = self.assets_dir / name
        if not anim_dir.exists():
            logger.warning(f"动画目录不存在: {anim_dir}")
            return False

        # 收集所有PNG文件并按文件名排序
        png_files = sorted(anim_dir.glob("*.png"))
        if not png_files:
            logger.warning(f"动画目录无PNG文件: {anim_dir}")
            return False

        frames = []
        for png_path in png_files:
            pixmap = QPixmap(str(png_path))
            if not pixmap.isNull():
                frames.append(pixmap)

        if frames:
            self._frames_cache[name] = frames
            if name == self._current_animation:
                self._fps = fps
            logger.info(f"加载动画 '{name}': {len(frames)}帧 @ {fps}fps")
            return True

        return False

    def play(self, name: str, fps: int = 8, loop: bool = True) -> bool:
        """
        播放指定动画

        Args:
            name: 动画名称
            fps: 帧率（自动限制在 1-60 范围）
            loop: 是否循环播放

        Returns:
            是否播放成功
        """
        # 防御性校验：防止 fps=0 导致 ZeroDivisionError
        fps = max(1, min(fps, 60))

        # 如果动画未加载，尝试自动加载
        if name not in self._frames_cache:
            if not self.load_animation(name, fps):
                return False

        # 如果动画没变化且正在播放，跳过
        if self._current_animation == name and self._timer.isActive():
            return True

        self._current_animation = name
        self._current_frame_index = 0
        self._fps = fps

        # 停止之前的定时器
        self._timer.stop()
        try:
            self._timer.timeout.disconnect()
        except TypeError:
            pass  # 首次播放时没有连接，忽略

        # 连接定时器回调
        interval = int(1000 / fps)
        self._timer.setInterval(interval)

        def next_frame():
            self._current_frame_index += 1
            if self._current_frame_index >= len(self._frames_cache[name]):
                if loop:
                    self._current_frame_index = 0
                else:
                    self._timer.stop()
                    return
            self._show_frame(name, self._current_frame_index)

        self._timer.timeout.connect(next_frame)

        # 显示第一帧
        self._show_frame(name, 0)
        self._timer.start()

        return True

    def stop(self) -> None:
        """停止播放"""
        self._timer.stop()

    def is_playing(self) -> bool:
        """是否正在播放"""
        return self._timer.isActive()

    def _show_frame(self, anim_name: str, index: int) -> None:
        """显示指定帧"""
        if anim_name not in self._frames_cache:
            return
        if index >= len(self._frames_cache[anim_name]):
            return

        pixmap = self._frames_cache[anim_name][index]

        if self._target_label is not None:
            self._target_label.setPixmap(pixmap)

        if self._on_frame_changed:
            self._on_frame_changed(anim_name, index)
