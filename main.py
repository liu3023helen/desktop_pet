"""
桌面宠物 - Pygame 简化版
无边框透明小窗口，固定在屏幕右下角
只显示欢呼跳跃动画 + 提醒触发
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
# 配置
# ============================================================
WINDOW_SIZE = 256       # 窗口尺寸（正方形）
BG_COLOR = (0, 0, 0)    # 纯黑背景（将设为透明色键）
FPS = 60
ANIMATION_FPS = 2       # 动画帧率（每秒2帧，每帧0.5秒）

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


ACTION_HANDLERS = {
    "open_url": lambda cfg: open_dingtalk(cfg),
    "dingtalk": lambda cfg: open_dingtalk(cfg),
}


# ============================================================
# 主程序
# ============================================================
def main():
    logger.info("=" * 40)
    logger.info("Desktop Pet 启动 (Pygame 简化版)")

    # 加载配置
    config_mgr = ConfigManager()
    config = config_mgr.load()
    logger.info(f"配置加载完成")

    # ========================================================
    # Pygame 初始化
    # ========================================================
    pygame.init()
    pygame.display.set_caption("Desktop Pet - 小新")

    # 获取屏幕尺寸
    info = pygame.display.Info()
    screen_w, screen_h = info.current_w, info.current_h

    # 定位到屏幕右下角（通过SDL环境变量，必须在set_mode前设置）
    window_x = screen_w - WINDOW_SIZE - 20   # 距右边20px
    window_y = screen_h - WINDOW_SIZE - 60   # 距底部60px（避开任务栏）
    os.environ['SDL_VIDEO_WINDOW_POS'] = f"{window_x},{window_y}"
    logger.info(f"窗口定位: ({window_x}, {window_y})")

    # 创建无边框小窗口
    screen = pygame.display.set_mode(
        (WINDOW_SIZE, WINDOW_SIZE),
        pygame.NOFRAME
    )

    logger.info(f"窗口尺寸: {WINDOW_SIZE}x{WINDOW_SIZE}, 屏幕: {screen_w}x{screen_h}")

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
        """提醒触发回调"""
        nonlocal engine_callback
        engine_callback = reminder
        name = reminder.get("name", "提醒")
        action = reminder.get("action_type", "notify_only")
        logger.info(f"提醒触发: {name} (动作: {action})")

        renderer.trigger_cheer()

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

    logger.info("进入主循环")

    while running:
        dt = clock.tick(FPS) / 1000.0

        # ---- 事件处理 ----
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 3:  # 右键退出
                    running = False

        # ---- 提醒回调处理 ----
        if engine_callback:
            engine_callback = None

        # ---- 更新 & 绘制 ----
        renderer.update(dt)

        screen.fill(BG_COLOR)
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
