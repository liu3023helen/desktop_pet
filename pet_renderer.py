"""
宠物渲染器 - Pygame版本
负责：序列帧加载、动画播放、透明窗口渲染、拖拽移动、边界反弹
"""
import os
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pygame


class PetRenderer:
    """宠物渲染器 - 管理所有视觉表现"""

    def __init__(self, screen: pygame.Surface, assets_dir: Path):
        self.screen = screen
        self.assets_dir = assets_dir
        self.screen_w, self.screen_h = screen.get_size()

        # 当前位置和速度
        self.x = self.screen_w // 2
        self.y = self.screen_h // 2
        self.vx = 1.0  # 水平速度
        self.vy = 0.5  # 垂直速度
        self.speed = 1.5  # 基础速度

        # 动画状态
        self.animations: Dict[str, List[pygame.Surface]] = {}
        self.current_animation = "idle"
        self.current_frame = 0
        self.frame_timer = 0
        self.fps = 8  # 动画帧率

        # 尺寸
        self.width = 128
        self.height = 128

        # 拖拽状态
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # 加载所有动画
        self._load_all_animations()

    def _load_all_animations(self) -> None:
        """加载所有动画序列帧"""
        anim_dir = self.assets_dir / "animations"
        if not anim_dir.exists():
            print(f"[Renderer] 动画目录不存在: {anim_dir}")
            return

        for anim_name in ["idle", "walk", "cheer"]:
            frames = []
            frame_dir = anim_dir / anim_name
            if not frame_dir.exists():
                print(f"[Renderer] 动画目录不存在: {frame_dir}")
                continue

            png_files = sorted(frame_dir.glob("*.png"))
            for png in png_files:
                try:
                    surface = pygame.image.load(str(png)).convert_alpha()
                    frames.append(surface)
                except Exception as e:
                    print(f"[Renderer] 加载帧失败 {png}: {e}")

            if frames:
                self.animations[anim_name] = frames
                print(f"[Renderer] 加载动画 {anim_name}: {len(frames)} 帧")

        if not self.animations:
            print("[Renderer] 警告: 没有加载到任何动画！")

    def set_animation(self, name: str) -> None:
        """切换到指定动画"""
        if name in self.animations and name != self.current_animation:
            self.current_animation = name
            self.current_frame = 0
            self.frame_timer = 0
            print(f"[Renderer] 切换到动画: {name}")

    def update(self, dt: float) -> None:
        """更新动画和物理状态"""
        if self.dragging:
            return  # 拖拽时不更新物理

        # 更新动画帧
        if self.current_animation in self.animations:
            frames = self.animations[self.current_animation]
            if frames:
                self.frame_timer += dt * self.fps
                if self.frame_timer >= 1.0:
                    self.frame_timer -= 1.0
                    self.current_frame = (self.current_frame + 1) % len(frames)

        # 边界反弹（非拖拽状态）
        self.x += self.vx * self.speed
        self.y += self.vy * self.speed

        half_w = self.width // 2
        half_h = self.height // 2

        if self.x - half_w <= 0:
            self.x = half_w
            self.vx = abs(self.vx)
        elif self.x + half_w >= self.screen_w:
            self.x = self.screen_w - half_w
            self.vx = -abs(self.vx)

        if self.y - half_h <= 0:
            self.y = half_h
            self.vy = abs(self.vy)
        elif self.y + half_h >= self.screen_h:
            self.y = self.screen_h - half_h
            self.vy = -abs(self.vy)

    def draw(self) -> None:
        """绘制当前帧"""
        if self.current_animation not in self.animations:
            return

        frames = self.animations[self.current_animation]
        if not frames:
            return

        frame = frames[self.current_frame % len(frames)]

        # 计算绘制位置（居中）
        draw_x = int(self.x - self.width // 2)
        draw_y = int(self.y - self.height // 2)

        # 缩放帧以匹配目标尺寸
        if frame.get_width() != self.width or frame.get_height() != self.height:
            frame = pygame.transform.smoothscale(frame, (self.width, self.height))

        self.screen.blit(frame, (draw_x, draw_y))

    def handle_mouse_down(self, pos: Tuple[int, int]) -> bool:
        """处理鼠标按下事件，返回是否点击到了宠物"""
        mx, my = pos
        half_w = self.width // 2
        half_h = self.height // 2

        if (self.x - half_w <= mx <= self.x + half_w and
                self.y - half_h <= my <= self.y + half_h):
            self.dragging = True
            self.drag_offset_x = mx - self.x
            self.drag_offset_y = my - self.y
            # 点击时切换到走路动画
            self.set_animation("walk")
            return True
        return False

    def handle_mouse_up(self) -> None:
        """处理鼠标释放"""
        if self.dragging:
            self.dragging = False
            # 松开后回到idle
            self.set_animation("idle")

    def handle_mouse_move(self, pos: Tuple[int, int]) -> None:
        """处理鼠标移动（拖拽中）"""
        if self.dragging:
            mx, my = pos
            self.x = mx - self.drag_offset_x
            self.y = my - self.drag_offset_y

            # 限制在屏幕范围内
            half_w = self.width // 2
            half_h = self.height // 2
            self.x = max(half_w, min(self.screen_w - half_w, self.x))
            self.y = max(half_h, min(self.screen_h - half_h, self.y))

    def trigger_cheer(self) -> None:
        """触发欢呼动画（下班打卡时调用）"""
        self.set_animation("cheer")

    def get_rect(self) -> pygame.Rect:
        """获取宠物的碰撞矩形"""
        half_w = self.width // 2
        half_h = self.height // 2
        return pygame.Rect(
            self.x - half_w,
            self.y - half_h,
            self.width,
            self.height
        )
