"""
宠物渲染器 - Pygame简化版
只负责：序列帧加载 + 动画播放
宠物固定在窗口中央，不移动、不拖拽
"""
import os
from pathlib import Path
from typing import List

import pygame


class PetRenderer:
    """宠物渲染器 - 仅管理欢呼动画"""

    def __init__(self, screen: pygame.Surface, assets_dir: Path):
        self.screen = screen
        self.assets_dir = assets_dir

        # 窗口尺寸
        self.screen_w, self.screen_h = screen.get_size()

        # 动画状态
        self.frames: List[pygame.Surface] = []
        self.current_frame = 0
        self.frame_timer = 0.0
        self.fps = 2  # 动画帧率（每秒2帧，每帧0.5秒）

        # 加载欢呼动画
        self._load_cheer_animation()

    def _load_cheer_animation(self) -> None:
        """加载cheer序列帧"""
        frame_dir = self.assets_dir / "animations" / "cheer"
        if not frame_dir.exists():
            print(f"[Renderer] 动画目录不存在: {frame_dir}")
            return

        png_files = sorted(frame_dir.glob("*.png"))
        for png in png_files:
            try:
                surface = pygame.image.load(str(png)).convert_alpha()
                self.frames.append(surface)
            except Exception as e:
                print(f"[Renderer] 加载帧失败 {png}: {e}")

        print(f"[Renderer] 加载欢呼动画: {len(self.frames)} 帧")

    def update(self, dt: float) -> None:
        """更新动画帧"""
        if not self.frames:
            return

        self.frame_timer += dt * self.fps
        if self.frame_timer >= 1.0:
            self.frame_timer -= 1.0
            self.current_frame = (self.current_frame + 1) % len(self.frames)

    def draw(self) -> None:
        """绘制当前帧到屏幕中央"""
        if not self.frames:
            return

        frame = self.frames[self.current_frame]

        # 计算居中位置
        fw, fh = frame.get_width(), frame.get_height()
        draw_x = (self.screen_w - fw) // 2
        draw_y = (self.screen_h - fh) // 2

        self.screen.blit(frame, (draw_x, draw_y))

    def trigger_cheer(self) -> None:
        """触发欢呼（提醒时调用）—— 目前动画一直在播放"""
        self.current_frame = 0
        self.frame_timer = 0.0
