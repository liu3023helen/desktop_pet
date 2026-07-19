"""
宠物窗口模块 - PetWindow 类定义
从 main.py 抽离，包含透明窗口、动画播放、托盘菜单、提醒触发等逻辑
"""
import logging
import sys
import weakref
from pathlib import Path

from PyQt5.QtWidgets import (
    QApplication, QSystemTrayIcon, QMenu, QAction, QLabel, QWidget,
    QVBoxLayout, QMessageBox,
)
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSlot, QMetaObject, Q_ARG
from PyQt5.QtGui import QPixmap, QIcon

from animation_player import AnimationPlayer
from bubble_widget import BubbleWidget
from startup_utils import is_auto_start_enabled, set_auto_start, play_reminder_sound

logger = logging.getLogger(__name__)

# 宠物闲逛时底部预留像素（为任务栏留出空间，避免被遮挡）
TASKBAR_RESERVE_PX = 50


def clamp_to_primary_screen(window: QWidget) -> None:
    """确保窗口在主显示器范围内，防止跑到副屏消失"""
    screen = QApplication.primaryScreen().geometry()
    pos = window.pos()
    size = window.size()

    new_x = max(screen.left(), min(pos.x(), screen.right() - size.width()))
    new_y = max(screen.top(), min(pos.y(), screen.bottom() - size.height()))

    if pos.x() != new_x or pos.y() != new_y:
        window.move(new_x, new_y)
        logger.debug(f"窗口已从 ({pos.x()}, {pos.y()}) 拉回主屏 ({new_x}, {new_y})")


class PetWindow(QWidget):
    """透明宠物窗口 - 支持安静模式"""

    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        nested_pet_cfg = self.config.get("pet")
        self._pet_config = nested_pet_cfg if isinstance(nested_pet_cfg, dict) else self.config
        logger.info("初始化宠物窗口（安静模式）")

        # 窗口属性（从配置读取，兼容旧版无配置项）
        ui_cfg = self.config.get("ui", {}) if isinstance(self.config.get("ui"), dict) else {}
        window_size = ui_cfg.get("window_size", 256)

        self.setWindowTitle(self._pet_config.get("name", "Pet"))
        self.setFixedSize(window_size, window_size)

        # 无边框 + 透明 + 置顶 + 工具窗口（不在任务栏显示）
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_TranslucentBackground)

        # 安静模式：默认停在屏幕右下角，不闲逛
        self._quiet_mode = True
        self._original_velocity = QPoint(-1, 0)  # 活跃模式的速度（缩小范围）
        # 活跃模式下的X轴活动范围比例（0~1）
        self._wander_x_range_ratio = ui_cfg.get("wander_x_range_ratio", 0.4)

        # 初始位置：屏幕右下角（安静模式）
        self._move_to_corner()

        # 布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # 动画标签（自动缩放以适应窗口）
        self.animation_label = QLabel(self)
        self.animation_label.setAlignment(Qt.AlignCenter)
        self.animation_label.setScaledContents(True)
        layout.addWidget(self.animation_label)

        # 动画播放器
        self.animation_player = AnimationPlayer()
        self.animation_player.bind(self.animation_label)

        # 预加载 cheer 动画（2帧，低帧率让每帧停留更久）
        self.animation_player.load_animation("cheer", fps=3)

        # 安静模式：只显示静态图片，不播放动画
        self._show_static_frame()

        # 运动状态
        self._drag_pos = None
        self._velocity = QPoint(0, 0)  # 安静模式速度为0

        # 闲逛定时器（安静模式下不启动）
        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._wander_step)
        # 安静模式：不启动闲逛

        # 漫画对话气泡（闹钟/天气文字展示）
        self.bubble = BubbleWidget(
            pet_window=self,
            max_width=ui_cfg.get("bubble_max_width", 300),
        )

        # 配置管理器引用（由外部设置）
        self._config_mgr = None
        # 提醒引擎引用（由外部设置）
        self._engine = None
        self._interaction_dialogs = []

        # 系统托盘
        self._setup_tray()

        logger.info("宠物窗口初始化完成（安静模式，右下角静止）")

    def _move_to_corner(self):
        """移动到屏幕右下角（安静模式位置），确保在主屏范围内"""
        screen = QApplication.primaryScreen().geometry()
        x = screen.width() - self.width() - 20   # 距右边20px
        y = screen.height() - self.height() - 60  # 距底部60px（避开任务栏）
        self.move(x, y)
        # 多显示器适配：确保窗口不会跑到副屏
        clamp_to_primary_screen(self)
        logger.debug(f"宠物移至右下角: ({x}, {y})")

    def _show_static_frame(self):
        """显示静态图片（cheer第一帧），不播放动画"""
        if not self.animation_player.is_animation_loaded("cheer"):
            self.animation_player.load_animation("cheer", fps=3)
        pixmap = self.animation_player.get_frame("cheer", 0)
        if pixmap:
            # 只显示第一帧，不启动定时器
            self.animation_label.setPixmap(pixmap)
        logger.debug("显示静态图片")

    def _enter_quiet_mode(self):
        """进入安静模式：停止闲逛，停止动画，显示静态图片，回到右下角"""
        if not self._quiet_mode:
            self._quiet_mode = True
            self._velocity = QPoint(0, 0)
            self.wander_timer.stop()
            # 停止动画，显示第一帧作为静态图片
            self.animation_player.stop()
            self._show_static_frame()
            self._move_to_corner()
            logger.info("宠物进入安静模式（静止图片）")

    def _enter_active_mode(self):
        """进入活跃模式：开始闲逛"""
        if self._quiet_mode:
            self._quiet_mode = False
            self._velocity = self._original_velocity
            wander_speed = self.config.get("ui", {}).get("wander_speed_ms", 33)
            self.wander_timer.start(wander_speed)
            logger.info(f"宠物进入活跃模式 (speed={wander_speed}ms)")

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

        tray_menu.addSeparator()

        # 安静模式切换
        self._quiet_action = QAction("安静模式", self, checkable=True, checked=True)
        self._quiet_action.triggered.connect(self._toggle_quiet_mode)
        tray_menu.addAction(self._quiet_action)

        # 开机自启开关
        self._autostart_action = QAction("开机自启", self, checkable=True, checked=is_auto_start_enabled())
        self._autostart_action.triggered.connect(self._toggle_autostart)
        tray_menu.addAction(self._autostart_action)

        # --- 二期新增菜单项 ---
        tray_menu.addSeparator()

        manage_action = QAction("管理提醒", self)
        manage_action.triggered.connect(self._open_reminder_dialog)
        tray_menu.addAction(manage_action)

        sync_time_action = QAction("校准网络时间", self)
        sync_time_action.triggered.connect(self._sync_time_now)
        tray_menu.addAction(sync_time_action)

        weather_action = QAction("查看天气", self)
        weather_action.triggered.connect(self._show_weather)
        tray_menu.addAction(weather_action)

        tray_menu.addSeparator()

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

    def _toggle_quiet_mode(self, checked):
        """切换安静模式"""
        self._quiet_action.setChecked(checked)
        if checked:
            self._enter_quiet_mode()
        else:
            self._enter_active_mode()

    def _toggle_autostart(self, checked):
        """切换开机自启"""
        if set_auto_start(checked):
            self._autostart_action.setChecked(checked)
            label = "已启用" if checked else "已禁用"
            self.tray_icon.showMessage("开机自启", f"{label}，下次开机自动启动", QSystemTrayIcon.Information, 3000)

    def _quit_app(self):
        logger.info("用户退出程序")
        self.animation_player.stop()
        self.wander_timer.stop()
        self.tray_icon.hide()
        QApplication.quit()

    # --- 二期新增方法 ---
    def _open_reminder_dialog(self):
        """打开闹钟管理面板"""
        if self._config_mgr is None:
            QMessageBox.warning(self, "配置未初始化", "配置管理器尚未初始化")
            return
        try:
            from reminder_dialog import ReminderDialog
            dialog = ReminderDialog(self._config_mgr, self)
            # 连接信号：当提醒更新时，通知引擎重新加载
            dialog.reminders_updated.connect(self._on_reminders_updated)
            dialog.exec_()
        except Exception as e:
            logger.error(f"打开提醒管理面板失败: {e}")
            QMessageBox.critical(self, "错误", f"无法打开管理面板: {e}")

    def _on_reminders_updated(self, new_config):
        """提醒列表已更新，通知引擎重新加载"""
        if self._engine is not None:
            self._engine.reload_reminders(new_config)
            self.tray_icon.showMessage("提醒已更新", "新的提醒设置已生效", QSystemTrayIcon.Information, 2000)
            logger.info("提醒引擎已重新加载配置")

    def _sync_time_now(self):
        """手动触发网络时间校准"""
        try:
            from time_sync import TimeSyncService
            self.tray_icon.showMessage("时间校准中", "正在获取网络时间...", QSystemTrayIcon.Information, 2000)

            def do_sync():
                service = TimeSyncService()
                offset = service.sync_once()
                if offset is not None:
                    if self._engine is not None:
                        self._engine.set_time_offset(offset)
                    abs_offset = abs(offset)
                    if abs_offset > 30:
                        msg = f"时间偏差较大：{offset:.1f}秒，已自动校准"
                    else:
                        msg = f"时间已校准，偏差：{offset:.1f}秒"
                    title = "时间校准完成"
                    # 使用 QMetaObject.invokeMethod 回到主线程显示通知
                    QMetaObject.invokeMethod(
                        self.tray_icon, "showMessage", Qt.QueuedConnection,
                        Q_ARG(str, title), Q_ARG(str, msg),
                        Q_ARG(int, QSystemTrayIcon.Information), Q_ARG(int, 4000)
                    )
                else:
                    QMetaObject.invokeMethod(
                        self.tray_icon, "showMessage", Qt.QueuedConnection,
                        Q_ARG(str, "时间校准失败"),
                        Q_ARG(str, "无法连接到时间服务器"),
                        Q_ARG(int, QSystemTrayIcon.Warning), Q_ARG(int, 4000)
                    )

            # 在后台线程执行NTP请求
            import threading
            threading.Thread(target=do_sync, daemon=True).start()
        except ImportError:
            QMessageBox.warning(self, "功能未就绪", "时间校准模块尚未集成")
        except Exception as e:
            logger.error(f"时间校准失败: {e}")
            self.tray_icon.showMessage("时间校准失败", str(e), QSystemTrayIcon.Warning, 4000)

    def _show_weather(self):
        """显示天气信息（漫画气泡 + 托盘通知）"""
        logger.info("[Weather] _show_weather called")
        try:
            from weather_service import WeatherService
            config = self._config_mgr.load() if self._config_mgr else {}
            weather_cfg = config.get("weather", {})
            city = weather_cfg.get("city", "北京")

            logger.info(f"[Weather] config loaded: city={city}, weather_cfg={weather_cfg}")
            logger.info(f"[Weather] bubble instance: {self.bubble}")

            self.tray_icon.showMessage("天气查询中", f"正在获取 {city} 的天气信息...", QSystemTrayIcon.Information, 1500)

            def do_fetch():
                logger.info("[Weather] do_fetch started in thread")
                try:
                    service = WeatherService(config=weather_cfg)
                    info = service.get_weather(city)
                    logger.info(f"[Weather] get_weather result: {info}")
                    if info:
                        msg = f"{info.city} · {info.condition} · {info.temperature}°C"
                        if info.humidity:
                            msg += f"\n湿度 {info.humidity}%"
                        logger.info(f"[Weather] formatted msg: {msg!r}")
                    else:
                        logger.warning("[Weather] info is None")
                        msg = "天气查询失败\n请稍后再试"
                    # 用 invokeMethod 安全投递到主线程（QTimer.singleShot 在子线程创建无效）
                    QMetaObject.invokeMethod(
                        self, "_show_weather_bubble",
                        Qt.QueuedConnection,
                        Q_ARG(str, msg)
                    )
                except Exception as e:
                    logger.error(f"[Weather] do_fetch exception: {e}")
                    QMetaObject.invokeMethod(
                        self, "_show_weather_bubble",
                        Qt.QueuedConnection,
                        Q_ARG(str, f"天气查询异常: {e}")
                    )

            import threading
            threading.Thread(target=do_fetch, daemon=True).start()
        except ImportError:
            QMessageBox.warning(self, "功能未就绪", "天气模块尚未集成")
        except Exception as e:
            logger.error(f"天气查询失败: {e}")
            weather_dur = self.config.get("ui", {}).get("weather_bubble_duration_ms", 6000)
            self.bubble.show_bubble("天气查询失败", duration_ms=weather_dur)

    @pyqtSlot(str)
    def _show_weather_bubble(self, msg: str):
        """在主线程显示天气气泡"""
        logger.info(f"[Weather] _show_weather_bubble: msg={msg!r}")
        logger.info(f"[Weather] bubble before show: visible={self.bubble.isVisible()}")
        weather_dur = self.config.get("ui", {}).get("weather_bubble_duration_ms", 6000)
        self.bubble.show_bubble(msg, duration_ms=weather_dur)
        logger.info(f"[Weather] bubble after show: visible={self.bubble.isVisible()}")
        self.tray_icon.showMessage("天气信息", msg.replace("\n", " "), QSystemTrayIcon.Information, 5000)

    def _wander_step(self):
        """闲逛步进逻辑 — 限制在屏幕中央区域活动"""
        screen = QApplication.primaryScreen().geometry()
        new_x = self.x() + self._velocity.x()
        new_y = self.y() + self._velocity.y()

        # 限制X轴活动范围：屏幕中央的 wander_x_range_ratio 宽度
        range_w = int(screen.width() * self._wander_x_range_ratio)
        center_x = screen.width() // 2
        x_min = center_x - range_w // 2
        x_max = center_x + range_w // 2 - self.width()

        if new_x <= x_min or new_x >= x_max:
            self._velocity.setX(-self._velocity.x())
            new_x = max(x_min, min(new_x, x_max))

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
        提醒时：跳到屏幕中央 + 进入活跃模式 + 播放动画 + 提示音 + 气泡文字
        10秒后：恢复右下角安静模式
        """
        name = reminder.get("name", "提醒")
        message = reminder.get("message", f"{name}时间到了！")
        animation = reminder.get("animation", "cheer")
        sound_enabled = reminder.get("sound", True)
        action_type = reminder.get("action_type", "notify_only")
        play_animation = action_type in {"open_url", "play_animation"}

        logger.info(f"触发提醒: {name}, 消息: {message}")

        if play_animation:
            # 1. 进入活跃模式（开始闲逛）
            self._enter_active_mode()

            # 2. 移动到屏幕正中央
            screen = QApplication.primaryScreen().geometry()
            center_x = screen.width() // 2 - self.width() // 2
            center_y = screen.height() // 2 - self.height() // 2
            self.move(center_x, center_y)

            # 3. 切换动画
            if self.animation_player.is_animation_loaded(animation) or self.animation_player.load_animation(animation):
                self.animation_player.play(animation, fps=3, loop=True)
            else:
                self.animation_player.play("cheer", fps=3, loop=True)

        # 4. 播放提示音（支持每个提醒使用不同的音效文件）
        if sound_enabled:
            sound_file = reminder.get("sound_file", "")
            play_reminder_sound(sound_file if sound_file else None)

        # 5. 漫画气泡展示提醒文案（同时保留托盘通知作为辅助）
        ui_cfg = self.config.get("ui", {})
        bubble_dur = ui_cfg.get("bubble_duration_ms", 8000)
        self.bubble.show_bubble(message, duration_ms=bubble_dur)
        self.tray_icon.showMessage(name, message, QSystemTrayIcon.Information, 5000)
        self._show_reminder_interaction(reminder)

        if play_animation:
            # 6. 恢复安静模式（回到右下角，显示静态图片）
            restore_delay = ui_cfg.get("restore_quiet_delay_ms", 10000)
            weak_self = weakref.ref(self)
            QTimer.singleShot(restore_delay, lambda ws=weak_self: ws() and ws()._enter_quiet_mode())

    def _show_reminder_interaction(self, reminder: dict) -> None:
        if self._engine is None:
            return

        from reminder_dialog import ReminderInteractionDialog

        dialog = ReminderInteractionDialog(reminder, self)
        dialog.snooze_requested.connect(self._engine.handle_snooze)
        dialog.skip_today_requested.connect(self._engine.handle_skip_today)
        dialog.complete_requested.connect(self._engine.handle_complete)
        self._interaction_dialogs.append(dialog)

        def remove_dialog():
            if dialog in self._interaction_dialogs:
                self._interaction_dialogs.remove(dialog)

        dialog.finished.connect(remove_dialog)
        dialog.show()

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

        quiet_action = menu.addAction(
            "安静模式" if self._quiet_mode else "活跃模式"
        )
        quiet_action.setCheckable(True)
        quiet_action.setChecked(self._quiet_mode)
        quiet_action.triggered.connect(self._toggle_quiet_mode)

        menu.addSeparator()

        auto_start = is_auto_start_enabled()
        autostart_action = menu.addAction(
            "禁用开机自启" if auto_start else "启用开机自启"
        )
        autostart_action.setCheckable(True)
        autostart_action.setChecked(auto_start)
        autostart_action.triggered.connect(self._toggle_autostart)

        menu.addSeparator()

        menu.addAction("退出", self._quit_app)
        menu.exec_(event.globalPos())
