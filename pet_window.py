"""
宠物窗口 - 透明置顶悬浮窗口
支持拖拽、边界反弹、右键托盘菜单、动画播放
"""
import sys
from PyQt5.QtWidgets import (
    QLabel, QSystemTrayIcon, QMenu, QAction, QWidget, QVBoxLayout
)
from PyQt5.QtCore import Qt, QPoint, QTimer, pyqtSignal
from PyQt5.QtGui import QPixmap, QIcon, QPainter, QRegion


class PetWindow(QWidget):
    """透明宠物窗口"""
    
    # 信号：动画切换请求
    animation_changed = pyqtSignal(str)  # 动画名称
    
    def __init__(self, config: dict = None):
        super().__init__()
        self.config = config or {}
        
        # 窗口属性
        self.setWindowTitle(self.config.get("name", "Pet"))
        self.setFixedSize(128, 128)
        
        # 无边框 + 透明 + 置顶 + 穿透点击（工具窗口）
        self.setWindowFlags(
            Qt.FramelessWindowHint |      # 无边框
            Qt.WindowStaysOnTopHint |     # 置顶
            Qt.Tool                       # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground)  # 透明背景
        
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
        
        # 拖拽相关
        self._drag_pos = None
        
        # 运动状态
        self._position = QPoint(self.x(), self.y())
        self._velocity = QPoint(2, 0)  # 初始向右移动
        self._speed = 2
        
        # 闲逛定时器
        self.wander_timer = QTimer(self)
        self.wander_timer.timeout.connect(self._wander_step)
        self.wander_timer.start(33)  # ~30fps
        
        # 设置当前动画
        self._current_animation = self.config.get("default_animation", "idle")
        self._update_animation_frame()
        
        # 系统托盘
        self._setup_tray()

    def _setup_tray(self):
        """设置系统托盘菜单"""
        self.tray_icon = QSystemTrayIcon(self)
        self.tray_icon.setIcon(QIcon.fromStyle(QStyle.SP_DesktopIcon))
        
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
        
        # 限制Y轴范围（不超出屏幕上下）
        if new_y < 0:
            new_y = 0
            self._velocity.setY(abs(self._velocity.y()))
        elif new_y + self.height() > screen.height() - 50:
            new_y = screen.height() - 50 - self.height()
            self._velocity.setY(-abs(self._velocity.y()))
        
        self.move(new_x, new_y)

    def set_animation(self, animation_name: str, duration_ms: int = 10000):
        """切换动画，指定持续时间后自动恢复"""
        self._current_animation = animation_name
        self.animation_changed.emit(animation_name)
        self._update_animation_frame()
        
        # 如果是临时动画，duration_ms后恢复闲逛
        if duration_ms > 0:
            QTimer.singleShot(duration_ms, lambda: self._restore_idle())

    def _restore_idle(self):
        """恢复到空闲动画"""
        self._current_animation = "idle"
        self.animation_changed.emit("idle")
        self._update_animation_frame()

    def _update_animation_frame(self):
        """更新当前帧（由动画播放器调用）"""
        # TODO: 由动画系统填充具体帧图像
        pass

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


# 需要在全局作用域导入
from PyQt5.QtWidgets import QApplication, QStyle
