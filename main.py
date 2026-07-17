"""
桌面宠物 - Pygame 版本
透明背景悬浮窗口，序列帧动画，可拖拽，可扩展提醒系统
"""
import os
import sys
import logging
import webbrowser
import subprocess
from pathlib import Path
from typing import Any, Dict

import pygame

# 添加项目根目录到路径
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from config_manager import ConfigManager
from reminder_engine import ReminderEngine
from pet_renderer import PetRenderer

# ============================================================
# 日志配置
# ============================================================
LOG_DIR = Path(os.environ.get("APPDATA", "")) / "DesktopPet" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "pet.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("DesktopPet")


# ============================================================
# 钉钉打卡处理器
# ============================================================
DEFAULT_DINGTALK_URL = "https://im.dingtalk.com/attendancemobile/index.html"
DEFAULT_DINGTALK_PROTOCOL = "dingtalk://dingtalkclient/page/link?pc_slide=false&url=" + DEFAULT_DINGTALK_URL


def open_dingtalk(reminder_config: Dict[str, Any]) -> bool:
    """打开钉钉打卡页面"""
    target_url = reminder_config.get("action_target", DEFAULT_DINGTALK_PROTOCOL)

    # 方案1: 尝试协议启动客户端
    try:
        logger.info(f"尝试启动钉钉客户端: {target_url}")
        subprocess.Popen(
            ["start", "", target_url],
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        logger.info("钉钉客户端启动成功")
        return True
    except Exception as e:
        logger.error(f"启动钉钉客户端异常: {e}")

    # 方案2: 浏览器打开网页版
    return open_browser(reminder_config)


def open_browser(reminder_config: Dict[str, Any]) -> bool:
    """浏览器打开钉钉网页版"""
    try:
        web_url = reminder_config.get("action_target", DEFAULT_DINGTALK_URL)
        if not web_url.startswith("http"):
            web_url = DEFAULT_DINGTALK_URL
        logger.info(f"降级打开浏览器: {web_url}")
        webbrowser.open(web_url)
        return True
    except Exception as e:
        logger.error(f"浏览器打开失败: {e}")
        return False


# ============================================================
# 动作处理器注册表
# ============================================================
ACTION_HANDLERS = {
    "open_url": lambda cfg: open_dingtalk(cfg),
    "dingtalk": lambda cfg: open_dingtalk(cfg),
}


# ============================================================
# 主程序
# ============================================================
def main():
    logger.info("=" * 40)
    logger.info("Desktop Pet 启动 (Pygame)")

    # 加载配置
    config_mgr = ConfigManager()
    config = config_mgr.load()
    logger.info(f"配置加载完成: pet={config.get('pet', {}).get('name', 'Unknown')}")

    # ========================================================
    # Pygame 初始化
    # ========================================================
    pygame.init()
    pygame.display.set_caption("Desktop Pet - 小新")

    # 获取屏幕尺寸
    info = pygame.display.Info()
    screen_w, screen_h = info.current_w, info.current_h

    # 创建全屏透明窗口
    # 使用 HWSURFACE + DOUBLEBUF + NOFRAME 实现无边框全屏
    screen = pygame.display.set_mode(
        (screen_w, screen_h),
        pygame.NOFRAME | pygame.HWSURFACE | pygame.DOUBLEBUF
    )

    # 设置窗口透明度（Windows）
    # 注意：pygame本身不支持真正的透明背景窗口
    # 这里用黑色作为色键（chroma key）模拟透明
    screen.fill((0, 0, 0))
    pygame.display.flip()

    # 设置色键 - 黑色视为透明
    # 实际透明效果需要操作系统支持
    # 在Windows上可以通过 win32gui 设置分层窗口

    logger.info(f"屏幕分辨率: {screen_w}x{screen_h}")

    # ========================================================
    # 创建渲染器
    # ========================================================
    assets_dir = BASE_DIR / "assets"
    renderer = PetRenderer(screen, assets_dir)

    # ========================================================
    # 启动提醒引擎
    # ========================================================
    engine_callback = None

    def on_reminder(reminder: Dict[str, Any]) -> None:
        """提醒触发回调 - 在主线程中执行"""
        nonlocal engine_callback
        engine_callback = reminder
        name = reminder.get("name", "提醒")
        action = reminder.get("action_type", "notify_only")
        logger.info(f"提醒触发: {name} (动作: {action})")

        # 切换到欢呼动画
        renderer.trigger_cheer()

        # 执行动作
        handler = ACTION_HANDLERS.get(action)
        if handler:
            try:
                handler(reminder)
            except Exception as e:
                logger.error(f"动作执行失败: {e}")

    engine = ReminderEngine(config, callback=on_reminder)
    engine.start()

    # ========================================================
    # 主循环
    # ========================================================
    clock = pygame.time.Clock()
    running = True
    bg_color = (0, 0, 0)  # 黑色背景（将作为透明色键）

    logger.info("进入主循环")

    while running:
        dt = clock.tick(60) / 1000.0  # 60 FPS, delta time in seconds

        # ---- 事件处理 ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_c:
                    # 手动触发欢呼测试
                    renderer.trigger_cheer()

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键
                    renderer.handle_mouse_down(event.pos)
                elif event.button == 3:  # 右键
                    running = False

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    renderer.handle_mouse_up()

            elif event.type == pygame.MOUSEMOTION:
                renderer.handle_mouse_move(event.pos)

        # ---- 提醒回调处理（从引擎线程传来）----
        if engine_callback:
            reminder = engine_callback
            engine_callback = None
            # 已经在回调中处理了

        # ---- 更新 ----
        renderer.update(dt)

        # ---- 绘制 ----
        screen.fill(bg_color)  # 填充黑色（透明色键）
        renderer.draw()

        pygame.display.flip()

    # ========================================================
    # 清理
    # ========================================================
    logger.info("正在退出...")
    engine.stop()
    pygame.quit()
    logger.info("已退出")


if __name__ == "__main__":
    main()
