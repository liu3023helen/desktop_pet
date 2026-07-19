"""
漫画对话气泡组件 — 调试版
用于在宠物旁以漫画风格气泡展示文字信息（闹钟提醒、天气信息等）
"""
import logging
from PyQt5.QtWidgets import QLabel, QApplication
from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtGui import QFont

logger = logging.getLogger("DesktopPet.bubble")


class BubbleWidget(QLabel):
    """漫画风格对话气泡 — 独立顶级窗口"""

    def __init__(self, pet_window=None, max_width: int = 300):
        super().__init__(None)
        
        self._pet_window = pet_window
        self._max_width = max(160, int(max_width))

        # 关键设置：无边框 + 置顶
        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint
        )
        
        # 不抢焦点
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)

        # 样式
        self.setWordWrap(True)
        self.setAlignment(Qt.AlignCenter)
        self.setTextFormat(Qt.PlainText)
        self.setStyleSheet("""
            QLabel {
                background-color: rgb(255, 255, 255);
                border-radius: 16px;
                color: #000000;
                font-size: 16px;
                font-weight: bold;
                padding: 10px 14px;
                border: 2px solid #000000;
            }
        """)
        font = QFont("Microsoft YaHei", 14, QFont.Bold)
        self.setFont(font)

        self.setMinimumWidth(min(180, self._max_width))
        self.setMaximumWidth(self._max_width)

        # 自动消失定时器
        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self._do_hide)

        self.hide()
        logger.info("[BubbleWidget] initialized")

    def show_bubble(self, text: str, duration_ms: int = 5000):
        """显示气泡文字"""
        logger.info(f"[BubbleWidget] show_bubble called: text={text!r}, duration={duration_ms}ms")
        
        if not text:
            logger.warning("[BubbleWidget] empty text, skipping")
            return

        self._hide_timer.stop()
        self.setText(text)
        self.setMinimumSize(0, 0)
        self.setMaximumSize(self._max_width, 16777215)

        horizontal_padding = 36
        longest_line = max(text.splitlines() or [text], key=len)
        natural_width = self.fontMetrics().horizontalAdvance(longest_line) + horizontal_padding
        width = max(160, min(self._max_width, natural_width))
        self.setFixedWidth(width)
        self.setFixedHeight(max(70, self.heightForWidth(width)))
        logger.info(f"[BubbleWidget] fitted size: {self.width()}x{self.height()}")

        self._reposition()
        logger.info(f"[BubbleWidget] position: {self.pos()}")

        self.show()
        self.raise_()
        logger.info(f"[BubbleWidget] isVisible={self.isVisible()}, isHidden={self.isHidden()}")

        self._hide_timer.start(duration_ms)

    def _do_hide(self):
        logger.info("[BubbleWidget] hiding")
        self.hide()
        self.clear()

    def _reposition(self):
        if self._pet_window is None:
            logger.warning("[BubbleWidget] no pet_window, cannot reposition")
            return

        pet_geo = self._pet_window.geometry()
        bubble_w = self.width()
        bubble_h = self.height()

        x = pet_geo.x() + (pet_geo.width() - bubble_w) // 2
        y = pet_geo.y() - bubble_h - 8

        screen_obj = QApplication.screenAt(pet_geo.center()) or QApplication.primaryScreen()
        screen = screen_obj.availableGeometry()
        if y < screen.top():
            y = pet_geo.y() + pet_geo.height() + 8

        if x + bubble_w > screen.right() + 1:
            x = screen.right() + 1 - bubble_w
        if x < screen.left():
            x = screen.left()
        if y + bubble_h > screen.bottom() + 1:
            y = screen.bottom() + 1 - bubble_h
        if y < screen.top():
            y = screen.top()

        self.move(x, y)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._hide_timer.stop()
