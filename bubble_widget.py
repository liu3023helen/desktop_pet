"""Interactive speech bubble used for status, results, and reminders."""
import logging

from PyQt5.QtCore import QTimer, Qt, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

logger = logging.getLogger("DesktopPet.bubble")


class BubbleWidget(QWidget):
    """Top-level bubble with optional reminder action buttons."""

    action_triggered = pyqtSignal(str)

    RESULT_DURATION_MS = 8000
    ACTION_SNOOZE = "snooze_10"
    ACTION_ACKNOWLEDGE = "acknowledge"

    def __init__(self, pet_window=None, max_width: int = 300):
        super().__init__(None)
        self._pet_window = pet_window
        self._max_width = max(160, int(max_width))
        self._mode = "hidden"

        self.setWindowFlags(
            Qt.FramelessWindowHint |
            Qt.WindowStaysOnTopHint |
            Qt.Tool
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setObjectName("speechBubble")
        self.setStyleSheet("""
            QWidget#speechBubble {
                background-color: rgb(255, 255, 255);
                border: 2px solid #000000;
                border-radius: 12px;
            }
            QLabel {
                background: transparent;
                color: #000000;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton {
                min-height: 30px;
                padding: 2px 8px;
                border: 1px solid #BDBDBD;
                border-radius: 4px;
                background-color: #F7F7F7;
                color: #212121;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #EEEEEE;
                border-color: #757575;
            }
            QPushButton:pressed {
                background-color: #E0E0E0;
            }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        self._message_label = QLabel(self)
        self._message_label.setWordWrap(True)
        self._message_label.setAlignment(Qt.AlignCenter)
        self._message_label.setTextFormat(Qt.PlainText)
        self._message_label.setFont(QFont("Microsoft YaHei", 14, QFont.Bold))
        layout.addWidget(self._message_label)

        self._actions_widget = QWidget(self)
        actions_layout = QHBoxLayout(self._actions_widget)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self._snooze_button = QPushButton("稍后10分钟哈~", self._actions_widget)
        self._snooze_button.setObjectName("bubble_snooze_button")
        self._snooze_button.clicked.connect(
            lambda: self._emit_action(self.ACTION_SNOOZE)
        )
        actions_layout.addWidget(self._snooze_button)

        self._acknowledge_button = QPushButton("知道了~", self._actions_widget)
        self._acknowledge_button.setObjectName("bubble_acknowledge_button")
        self._acknowledge_button.clicked.connect(
            lambda: self._emit_action(self.ACTION_ACKNOWLEDGE)
        )
        actions_layout.addWidget(self._acknowledge_button)
        layout.addWidget(self._actions_widget)
        self._actions_widget.hide()

        self._hide_timer = QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide_bubble)

        self.hide()

    @property
    def mode(self) -> str:
        return self._mode

    def text(self) -> str:
        return self._message_label.text()

    def show_loading(self, text: str) -> None:
        """Show a persistent, non-interactive loading state."""
        self._show(text, mode="loading", actions=False, duration_ms=None)

    def show_result(self, text: str, duration_ms: int = RESULT_DURATION_MS) -> None:
        """Show a non-interactive result that hides after eight seconds."""
        self._show(text, mode="result", actions=False, duration_ms=duration_ms)

    def show_reminder(self, text: str) -> None:
        """Show a persistent reminder with snooze and acknowledge actions."""
        self._show(text, mode="reminder", actions=True, duration_ms=None)

    def show_bubble(self, text: str, duration_ms: int = 5000) -> None:
        """Backward-compatible alias for a timed result bubble."""
        self.show_result(text, duration_ms=duration_ms)

    def _show(self, text: str, mode: str, actions: bool, duration_ms) -> None:
        if not isinstance(text, str) or not text.strip():
            logger.warning("[BubbleWidget] empty text, skipping")
            return

        self._hide_timer.stop()
        self.setAttribute(Qt.WA_ShowWithoutActivating, not actions)
        self._mode = mode
        self._message_label.setText(text)
        self._actions_widget.setVisible(actions)
        self._fit_to_content(text, actions)
        self._reposition()
        self.show()
        self.raise_()

        if duration_ms is not None and duration_ms > 0:
            self._hide_timer.start(int(duration_ms))

    def _emit_action(self, action: str) -> None:
        logger.info(f"[BubbleWidget] action clicked: {action}")
        self.action_triggered.emit(action)

    def _fit_to_content(self, text: str, actions: bool) -> None:
        self.setMinimumSize(0, 0)
        self.setMaximumSize(self._max_width, 16777215)

        horizontal_padding = 36
        longest_line = max(text.splitlines() or [text], key=len)
        natural_width = (
            self._message_label.fontMetrics().horizontalAdvance(longest_line)
            + horizontal_padding
        )
        minimum_width = min(260, self._max_width) if actions else 160
        width = max(minimum_width, min(self._max_width, natural_width))
        self.setFixedWidth(width)

        content_width = max(1, width - horizontal_padding)
        self._message_label.setMinimumSize(0, 0)
        self._message_label.setMaximumSize(content_width, 16777215)
        self._message_label.setFixedWidth(content_width)
        message_height = max(32, self._message_label.heightForWidth(content_width))
        self._message_label.setFixedHeight(message_height)

        self.layout().activate()
        self.setFixedHeight(max(70, self.sizeHint().height()))

    def hide_bubble(self) -> None:
        self._hide_timer.stop()
        self._mode = "hidden"
        self.hide()
        self._message_label.clear()
        self._actions_widget.hide()

    def _reposition(self) -> None:
        if self._pet_window is None:
            return

        pet_geo = self._pet_window.geometry()
        bubble_w = self.width()
        bubble_h = self.height()
        screen_obj = QApplication.screenAt(pet_geo.center()) or QApplication.primaryScreen()
        screen = screen_obj.availableGeometry()

        x = pet_geo.x() + (pet_geo.width() - bubble_w) // 2
        y = pet_geo.y() - bubble_h - 12
        if y < screen.top():
            y = pet_geo.y() + pet_geo.height() + 12

        x = max(screen.left(), min(x, screen.right() + 1 - bubble_w))
        y = max(screen.top(), min(y, screen.bottom() + 1 - bubble_h))
        self.move(x, y)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._hide_timer.stop()
