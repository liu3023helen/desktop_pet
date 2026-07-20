"""Comic-styled Pomodoro controls and their Qt controller."""
from pathlib import Path
from typing import Optional

from PyQt5.QtCore import QObject, QSize, Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QIcon, QPixmap
from PyQt5.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pomodoro import (
    PHASE_FOCUS,
    PHASE_LONG_BREAK,
    PHASE_SHORT_BREAK,
    STATUS_AWAITING,
    STATUS_IDLE,
    STATUS_PAUSED,
    STATUS_RUNNING,
    PomodoroEvent,
    PomodoroTimer,
)


PHASE_LABELS = {
    PHASE_FOCUS: "专注大作战",
    PHASE_SHORT_BREAK: "短休息一下",
    PHASE_LONG_BREAK: "长休息时间",
}


class PomodoroController(QObject):
    """Keep the timer alive independently from the optional dialog."""

    state_changed = pyqtSignal(dict)
    event_emitted = pyqtSignal(object)
    settings_changed = pyqtSignal(dict)

    def __init__(
        self,
        timer: PomodoroTimer,
        config_manager=None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self.timer = timer
        self.config_manager = config_manager
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(1000)
        self.poll_timer.timeout.connect(self.poll)
        self.poll_timer.start()

    def snapshot(self) -> dict:
        return self.timer.snapshot()

    def emit_state(self) -> dict:
        snapshot = self.snapshot()
        self.state_changed.emit(snapshot)
        return snapshot

    def poll(self) -> None:
        event = self.timer.tick()
        if event is not None:
            self.event_emitted.emit(event)
        self.emit_state()

    def perform_primary(
        self,
        minutes: Optional[int] = None,
        label: str = "",
    ) -> None:
        snapshot = self.snapshot()
        status = snapshot["status"]
        if status == STATUS_IDLE:
            self.timer.start_focus(minutes=minutes, label=label)
        elif status == STATUS_RUNNING:
            self.timer.pause()
        elif status == STATUS_PAUSED:
            self.timer.resume()
        elif status == STATUS_AWAITING:
            self.timer.start_next()
        self.emit_state()

    def stop(self) -> None:
        self.timer.stop()
        self.emit_state()

    def save_settings(self, settings: dict) -> bool:
        self.timer.update_settings(settings)
        if self.config_manager is not None:
            config = self.config_manager.load()
            config["pomodoro"] = dict(self.timer.settings)
            if not self.config_manager.save(config):
                return False
        self.settings_changed.emit(dict(self.timer.settings))
        self.emit_state()
        return True


class PomodoroDialog(QDialog):
    """A bright Shin-chan-inspired comic control panel."""

    PRESETS = (15, 25, 45, 60)

    def __init__(
        self,
        controller: PomodoroController,
        parent=None,
    ):
        super().__init__(parent)
        self.controller = controller
        self._setup_ui()
        self._load_settings()
        self.controller.state_changed.connect(self.refresh)
        self.controller.settings_changed.connect(lambda _: self._load_settings())
        self.refresh(self.controller.snapshot())

    def _setup_ui(self) -> None:
        self.setWindowTitle("小新的番茄钟")
        self.setFixedSize(520, 650)
        self.setModal(False)
        icon_path = Path(__file__).parent / "assets" / "icon.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet("""
            QDialog {
                background: #FFFFFF;
                color: #1E1E1E;
                font-family: "Microsoft YaHei";
                font-size: 14px;
            }
            QFrame#comicHeader {
                background: #FFD84D;
                border: 3px solid #1E1E1E;
                border-radius: 6px;
            }
            QLabel#titleLabel {
                font-size: 24px;
                font-weight: 700;
            }
            QLabel#speechLabel {
                background: #FFFFFF;
                border: 2px solid #1E1E1E;
                border-radius: 6px;
                padding: 8px 10px;
                font-weight: 600;
            }
            QLabel#phaseLabel {
                color: #E7394F;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#timerLabel {
                font-family: Consolas;
                font-size: 64px;
                font-weight: 700;
            }
            QLabel#roundLabel {
                color: #444444;
                font-size: 13px;
            }
            QTabWidget::pane {
                border: 3px solid #1E1E1E;
                border-radius: 4px;
                background: #FFFFFF;
            }
            QTabBar::tab {
                background: #D9F3FC;
                border: 2px solid #1E1E1E;
                padding: 7px 18px;
                min-width: 72px;
            }
            QTabBar::tab:selected {
                background: #61C4E8;
                font-weight: 700;
            }
            QPushButton {
                min-height: 34px;
                border: 2px solid #1E1E1E;
                border-radius: 4px;
                background: #FFFFFF;
                padding: 4px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #FFF2A8; }
            QPushButton:disabled { color: #888888; background: #EEEEEE; }
            QPushButton:checked { background: #73C66B; }
            QPushButton#primaryButton {
                background: #E7394F;
                color: #FFFFFF;
                min-height: 42px;
                font-size: 16px;
            }
            QPushButton#primaryButton:hover { background: #C92D40; }
            QPushButton#stopButton { background: #FFD84D; }
            QPushButton#stopButton:disabled {
                background: #EEEEEE;
                color: #888888;
            }
            QLineEdit, QSpinBox {
                min-height: 30px;
                border: 2px solid #1E1E1E;
                border-radius: 4px;
                background: #FFFFFF;
                padding: 2px 7px;
            }
            QProgressBar {
                min-height: 18px;
                border: 2px solid #1E1E1E;
                border-radius: 4px;
                background: #EEEEEE;
                text-align: center;
            }
            QProgressBar::chunk { background: #73C66B; }
            QFrame#statsBand {
                background: #61C4E8;
                border: 3px solid #1E1E1E;
                border-radius: 6px;
            }
            QLabel#statsLabel { font-weight: 700; font-size: 15px; }
            QCheckBox { spacing: 8px; min-height: 28px; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        header = QFrame()
        header.setObjectName("comicHeader")
        header.setFixedHeight(122)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(12, 8, 12, 8)

        self._character_label = QLabel()
        self._character_label.setFixedSize(96, 96)
        self._character_label.setAlignment(Qt.AlignCenter)
        if icon_path.exists():
            pixmap = QPixmap(str(icon_path)).scaled(
                QSize(92, 92),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation,
            )
            self._character_label.setPixmap(pixmap)
        header_layout.addWidget(self._character_label)

        header_text = QVBoxLayout()
        title = QLabel("小新的专注大作战")
        title.setObjectName("titleLabel")
        self._speech_label = QLabel("先专心一下，等会儿再玩嘛！")
        self._speech_label.setObjectName("speechLabel")
        self._speech_label.setWordWrap(True)
        header_text.addWidget(title)
        header_text.addWidget(self._speech_label)
        header_layout.addLayout(header_text, 1)
        root.addWidget(header)

        self._tabs = QTabWidget()
        self._timer_tab = QWidget()
        self._settings_tab = QWidget()
        self._tabs.addTab(self._timer_tab, "计时")
        self._tabs.addTab(self._settings_tab, "设置")
        root.addWidget(self._tabs, 1)

        self._build_timer_tab()
        self._build_settings_tab()

        stats_band = QFrame()
        stats_band.setObjectName("statsBand")
        stats_band.setFixedHeight(52)
        stats_layout = QHBoxLayout(stats_band)
        self._stats_label = QLabel()
        self._stats_label.setObjectName("statsLabel")
        self._stats_label.setAlignment(Qt.AlignCenter)
        stats_layout.addWidget(self._stats_label)
        root.addWidget(stats_band)

    def _build_timer_tab(self) -> None:
        layout = QVBoxLayout(self._timer_tab)
        layout.setContentsMargins(16, 10, 16, 12)
        layout.setSpacing(8)

        self._phase_label = QLabel()
        self._phase_label.setObjectName("phaseLabel")
        self._phase_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._phase_label)

        self._timer_label = QLabel("25:00")
        self._timer_label.setObjectName("timerLabel")
        self._timer_label.setAlignment(Qt.AlignCenter)
        self._timer_label.setFixedHeight(82)
        layout.addWidget(self._timer_label)

        self._progress = QProgressBar()
        self._progress.setTextVisible(False)
        layout.addWidget(self._progress)

        self._round_label = QLabel()
        self._round_label.setObjectName("roundLabel")
        self._round_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self._round_label)

        preset_layout = QHBoxLayout()
        preset_layout.setSpacing(7)
        self._preset_group = QButtonGroup(self)
        self._preset_group.setExclusive(True)
        self._preset_buttons = {}
        for minutes in self.PRESETS:
            button = QPushButton(f"{minutes}分")
            button.setCheckable(True)
            button.setFixedHeight(36)
            self._preset_group.addButton(button, minutes)
            self._preset_buttons[minutes] = button
            preset_layout.addWidget(button)
        layout.addLayout(preset_layout)

        self._label_edit = QLineEdit()
        self._label_edit.setPlaceholderText("这一轮要完成什么？")
        self._label_edit.setMaxLength(80)
        layout.addWidget(self._label_edit)

        control_layout = QHBoxLayout()
        self._primary_button = QPushButton("开始专注")
        self._primary_button.setObjectName("primaryButton")
        self._primary_button.clicked.connect(self._on_primary)
        self._stop_button = QPushButton("结束")
        self._stop_button.setObjectName("stopButton")
        self._stop_button.clicked.connect(self._on_stop)
        control_layout.addWidget(self._primary_button, 2)
        control_layout.addWidget(self._stop_button, 1)
        layout.addLayout(control_layout)

    @staticmethod
    def _spin(minimum: int, maximum: int, suffix: str) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        return spin

    def _build_settings_tab(self) -> None:
        layout = QVBoxLayout(self._settings_tab)
        layout.setContentsMargins(22, 18, 22, 16)
        layout.setSpacing(12)
        form = QFormLayout()
        form.setSpacing(12)
        self._focus_spin = self._spin(1, 180, " 分钟")
        self._short_break_spin = self._spin(1, 60, " 分钟")
        self._long_break_spin = self._spin(1, 120, " 分钟")
        self._long_every_spin = self._spin(2, 12, " 轮")
        form.addRow("专注时长", self._focus_spin)
        form.addRow("短休息", self._short_break_spin)
        form.addRow("长休息", self._long_break_spin)
        form.addRow("长休息间隔", self._long_every_spin)
        layout.addLayout(form)

        self._hide_check = QCheckBox("专注开始后自动隐藏宠物")
        self._auto_break_check = QCheckBox("专注完成后自动开始休息")
        self._auto_focus_check = QCheckBox("休息完成后自动开始下一轮")
        layout.addWidget(self._hide_check)
        layout.addWidget(self._auto_break_check)
        layout.addWidget(self._auto_focus_check)
        layout.addStretch()

        save_button = QPushButton("保存设置")
        save_button.setObjectName("primaryButton")
        save_button.clicked.connect(self._save_settings)
        layout.addWidget(save_button)

    def _load_settings(self) -> None:
        settings = self.controller.timer.settings
        self._focus_spin.setValue(settings["focus_minutes"])
        self._short_break_spin.setValue(settings["short_break_minutes"])
        self._long_break_spin.setValue(settings["long_break_minutes"])
        self._long_every_spin.setValue(settings["long_break_every"])
        self._hide_check.setChecked(settings["hide_during_focus"])
        self._auto_break_check.setChecked(settings["auto_start_break"])
        self._auto_focus_check.setChecked(settings["auto_start_focus"])
        for minutes, button in self._preset_buttons.items():
            button.setChecked(minutes == settings["focus_minutes"])

    def _save_settings(self) -> None:
        settings = {
            "focus_minutes": self._focus_spin.value(),
            "short_break_minutes": self._short_break_spin.value(),
            "long_break_minutes": self._long_break_spin.value(),
            "long_break_every": self._long_every_spin.value(),
            "hide_during_focus": self._hide_check.isChecked(),
            "auto_start_break": self._auto_break_check.isChecked(),
            "auto_start_focus": self._auto_focus_check.isChecked(),
        }
        if self.controller.save_settings(settings):
            self._tabs.setCurrentWidget(self._timer_tab)
        else:
            QMessageBox.critical(self, "保存失败", "番茄钟设置保存失败")

    def _selected_minutes(self) -> int:
        selected_id = self._preset_group.checkedId()
        return (
            selected_id
            if selected_id in self.PRESETS
            else self.controller.timer.settings["focus_minutes"]
        )

    def _on_primary(self) -> None:
        self.controller.perform_primary(
            minutes=self._selected_minutes(),
            label=self._label_edit.text(),
        )

    def _on_stop(self) -> None:
        self.controller.stop()

    @staticmethod
    def _format_seconds(value: int) -> str:
        minutes, seconds = divmod(max(0, int(value)), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def refresh(self, snapshot: dict) -> None:
        phase = snapshot["phase"]
        status = snapshot["status"]
        remaining = snapshot["remaining_seconds"]
        duration = max(1, snapshot["duration_seconds"])
        self._phase_label.setText(PHASE_LABELS[phase])
        self._timer_label.setText(self._format_seconds(remaining))
        self._progress.setRange(0, duration)
        self._progress.setValue(max(0, duration - remaining))
        every = self.controller.timer.settings["long_break_every"]
        current_round = snapshot["completed_in_set"] % every + 1
        self._round_label.setText(f"第 {current_round} / {every} 轮")
        today = snapshot["today"]
        self._stats_label.setText(
            f"今天完成 {today['completed']} 轮  ·  专注 {today['focus_minutes']} 分钟"
        )

        if status == STATUS_IDLE:
            primary_text = "开始专注"
            speech = "先专心一下，等会儿再玩嘛！"
        elif status == STATUS_RUNNING:
            primary_text = "暂停"
            speech = (
                "不许偷看手机，我会盯着你的！"
                if phase == PHASE_FOCUS
                else "休息也要认真休息哦！"
            )
        elif status == STATUS_PAUSED:
            primary_text = "继续"
            speech = "只是暂停，不是放弃哦。"
        else:
            primary_text = "开始下一阶段"
            speech = (
                "这轮完成啦，去休息一下！"
                if phase != PHASE_FOCUS
                else "休息好了，再来一轮吧！"
            )
        self._primary_button.setText(primary_text)
        self._speech_label.setText(speech)
        self._stop_button.setEnabled(status != STATUS_IDLE)
        idle = status == STATUS_IDLE
        self._label_edit.setEnabled(idle)
        for button in self._preset_buttons.values():
            button.setEnabled(idle)
