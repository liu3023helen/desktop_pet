"""
Desktop Pet - 桌面电子宠物 MVP
主入口：初始化应用、加载配置、启动提醒引擎和宠物窗口
"""
import sys
import os
import logging
import weakref
from pathlib import Path

from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QLabel, QWidget, QVBoxLayout
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon

from config_manager import ConfigManager
from animation_player import AnimationPlayer
from dingtalk_handler import open_dingtalk_checkin


# --- 日志配置 ---
def _get_app_data_dir() -> Path:
    """获取应用数据目录，跨平台兼容"""
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", ""))
    else:
        # Linux/macOS: ~/.local/share/DesktopPet
        return Path.home() / ".local" / "share"


def setup_logging():
    """配置日志"""
    log_dir = _get_app_data_dir() / "DesktopPet" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_file = log_dir / "pet.log"
    
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger("DesktopPet")


logger = setup_logging()


# 宠物闲逛时底部预留像素（为任务栏留出空间，避免被遮挡）
TASKBAR_RESERVE_PX = 50

# 必需的动画资源目录
REQUIRED_ANIMATIONS = ("idle", "walk", "cheer")


def _check_assets(pet_window) -> None:
    """启动时检查素材完整性，缺失时弹出警告"""
    assets_dir = Path(__file__).parent / "assets" / "animations"
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
            f"请运行 'python generate_assets.py' 生成占位素材。"
        )
        logger.warning(msg)
        # 使用 QTimer 延迟弹窗，避免在构造期间阻塞
        from PyQt5.QtWidgets import QMessageBox
        QTimer.singleShot(500, lambda: QMessageBox.warning(
            pet_window, "素材缺失", msg, QMessageBox.Ok
        ))


class PetWindow(QWidget):
    """透明宠物窗口"""

    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        logger.info("初始化宠物窗口")

        # 窗口属性
        self.setWindowTitle(self.config.get("name", "Pet"))
        self.setFixedSize(128, 128)

        # 无边框 + 透明 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 初始位置（屏幕右下角附近）
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 200, screen.height() - 200)

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 动画标签
        self.animation_label = QLabel(self)
        self.animation_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.animation_label)

        # 动画播放器
        self.animation_player = AnimationPlayer()
        self.animation_player.bind(self.animation_label)

        # 预加载所有动画
        for anim_name in ["idle", "walk", "cheer"]:
            self.animation_player.load_animation(anim_name, fps=8)

        # 默认播放 idle
        self.animation_player.play("idle", fps=8, loop=True)

        # 运动状态
        self._drag_pos = None
        self._velocity = QPoint(2, 0)

        # 闲逛定时器
        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._wander_step)
        self.wander_timer.start(33)  # ~30fps

        # 系统托盘
        self._setup_tray()

        logger.info("宠物窗口初始化完成")

    def _setup_tray(self):
        """设置系统托盘菜单"""
        self.tray_icon = QSystemTrayIcon(self)
        # 使用自定义图标或默认图标
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(icon_path)))
        else:
            # 创建一个简单的彩色图标作为占位
            pixmap = QPixmap(32, 32)
            pixmap.fill(Qt.GlobalColor.red)
            self.tray_icon.setIcon(QIcon(pixmap))

        tray_menu = QMenu()

        show_action = QAction("显示", self)
        show_action.triggered.connect(self.show)
        tray_menu.addAction(show_action)

        hide_action = QAction("隐藏到托盘", self)
        hide_action.triggered.connect(self.hide)
        tray_menu.addAction(hide_action)

        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self._tray_activated)
        self.tray_icon.show()

    def _tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.show()
            self.activateWindow()

    def _quit_app(self):
        logger.info("用户退出程序")
        self.animation_player.stop()
        self.wander_timer.stop()
        self.tray_icon.hide()
        QApplication.quit()

    def _wander_step(self):
        """闲逛步进逻辑"""
        screen = QApplication.primaryScreen().geometry()
        new_x = self.x() + self._velocity.x()
        new_y = self.y() + self._velocity.y()

        # 边界检测 - 碰到左右边界反向
        if new_x <= 0 or new_x + self.width() >= screen.width():
            self._velocity.setX(-self._velocity.x())
            new_x = max(0, min(new_x, screen.width() - self.width()))

        # 限制Y轴范围（底部预留任务栏空间）
        if new_y < 0:
            new_y = 0
            self._velocity.setY(abs(self._velocity.y()))
        elif new_y + self.height() > screen.height() - TASKBAR_RESERVE_PX:
            new_y = screen.height() - TASKBAR_RESERVE_PX - self.height()
            self._velocity.setY(-abs(self._velocity.y()))

        self.move(new_x, new_y)

    def trigger_reminder(self, reminder: dict) -> None:
        """
        触发提醒回调（由提醒引擎信号连接到主线程调用）
        
        Args:
            reminder: 提醒配置字典
        """
        name = reminder.get("name", "提醒")
        message = reminder.get("message", f"{name}时间到了！")
        animation = reminder.get("animation", "cheer")
        sound_enabled = reminder.get("sound", True)

        logger.info(f"触发提醒: {name}, 消息: {message}")

        # 1. 切换动画
        if animation in self.animation_player._frames_cache or self.animation_player.load_animation(animation):
            self.animation_player.play(animation, fps=8, loop=True)
        else:
            # 如果没有对应动画，用cheer代替
            self.animation_player.play("cheer", fps=8, loop=True)

        # 2. 弹出系统通知
        self.tray_icon.showMessage(name, message, QSystemTrayIcon.Information, 5000)

        # 3. 10秒后恢复空闲动画（使用 weakref 避免程序快速退出时悬空引用）
        weak_self = weakref.ref(self)
        QTimer.singleShot(10000, lambda ws=weak_self: ws() and ws().animation_player.play("idle", fps=8, loop=True))

    # --- 鼠标拖拽 ---
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.LeftButton and self._drag_pos is not None:
            self.move(event.globalPos() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None

    # --- 右键菜单 ---
    def contextMenuEvent(self, event):
        menu = QMenu(self)
        menu.addAction("隐藏", self.hide)
        menu.addAction("退出", self._quit_app)
        menu.exec_(event.globalPos())


def ensure_config(config_mgr: ConfigManager) -> None:
    """确保配置文件存在，不存在则释放默认配置"""
    if not config_mgr.config_path.exists():
        config_mgr.config_path.parent.mkdir(parents=True, exist_ok=True)
        default_config = Path(__file__).parent / "config.yaml"
        if default_config.exists():
            import shutil
            shutil.copy2(default_config, config_mgr.config_path)
            logger.info(f"已释放默认配置到: {config_mgr.config_path}")


def main():
    logger.info("=" * 40)
    logger.info("Desktop Pet 启动")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 启用高分屏DPI缩放
    app.setAttribute(Qt.AA_EnableHighDpiScaling)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps)

    # 1. 初始化配置管理器
    config_mgr = ConfigManager()
    ensure_config(config_mgr)
    config = config_mgr.load()
    logger.info(f"配置加载完成: pet={config.get('pet', {}).get('name', 'unknown')}")

    # 2. 创建宠物窗口
    pet_window = PetWindow(config=config.get("pet", {}))

    # 2b. 检查素材完整性
    _check_assets(pet_window)

    # 3. 创建提醒引擎
    from reminder_engine import ReminderEngine
    
    engine = ReminderEngine(config=config, pet_window=pet_window)
    
    # 注册动作处理器
    engine.register_handler("open_url", open_dingtalk_checkin)
    
    # 连接信号到主线程的提醒处理
    engine.reminder_triggered.connect(pet_window.trigger_reminder)
    
    engine.start()
    logger.info("提醒引擎已启动")

    # 4. 显示宠物窗口
    pet_window.show()
    logger.info("宠物窗口已显示")

    exit_code = app.exec_()
    
    # 清理
    engine.stop()
    logger.info("程序退出")
    
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
