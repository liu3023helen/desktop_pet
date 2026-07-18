"""
闹钟管理GUI面板 - 表格化增删改查提醒任务
替代手动编辑YAML配置文件
"""
import os
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QMessageBox, QFormLayout, QLineEdit,
    QTimeEdit, QCheckBox, QComboBox, QTextEdit, QLabel, QWidget,
    QAbstractItemView
)
from PyQt5.QtCore import Qt, QTime, pyqtSignal
from PyQt5.QtGui import QFont


def _scan_sound_files() -> list:
    """扫描 assets/sounds 目录下的 WAV 文件，返回相对路径列表（排除默认提示音 reminder.wav）"""
    sounds_dir = os.path.join(os.path.dirname(__file__), "assets", "sounds")
    if not os.path.isdir(sounds_dir):
        return []
    files = sorted([os.path.join("assets", "sounds", f)
                    for f in os.listdir(sounds_dir)
                    if f.lower().endswith(".wav") and f.lower() != "reminder.wav"])
    return files


def _scan_animation_dirs() -> list:
    """扫描 assets/animations 目录下的动画子目录，返回目录名列表"""
    anim_dir = os.path.join(os.path.dirname(__file__), "assets", "animations")
    if not os.path.isdir(anim_dir):
        return []
    dirs = sorted([d for d in os.listdir(anim_dir) if os.path.isdir(os.path.join(anim_dir, d))])
    return dirs


class ReminderFormDialog(QDialog):
    """新增/编辑提醒的表单弹窗"""

    def __init__(self, parent=None, reminder_data: dict = None):
        super().__init__(parent)
        self._reminder_data = reminder_data
        self._result: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        is_edit = self._reminder_data is not None
        self.setWindowTitle("编辑提醒" if is_edit else "新增提醒")
        self.setFixedSize(420, 580)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(16)

        # 表单区域
        form_widget = QWidget()
        form_layout = QFormLayout(form_widget)
        form_layout.setSpacing(12)

        # 提醒名称
        self._name_edit = QLineEdit()
        self._name_edit.setPlaceholderText("如：下班打卡")
        self._name_edit.setMaxLength(50)
        form_layout.addRow("提醒名称", self._name_edit)

        # 触发时间
        self._time_edit = QTimeEdit()
        self._time_edit.setDisplayFormat("HH:mm")
        self._time_edit.setTime(QTime(18, 30))
        form_layout.addRow("触发时间", self._time_edit)

        # 仅工作日
        self._weekday_check = QCheckBox("仅工作日触发（周末和节假日自动跳过）")
        form_layout.addRow(self._weekday_check)

        # 动作类型
        self._action_combo = QComboBox()
        self._action_combo.addItems(["打开URL", "播放动画", "仅通知"])
        self._action_combo.currentIndexChanged.connect(self._on_action_type_changed)
        form_layout.addRow("动作类型", self._action_combo)

        # 目标URL
        self._url_edit = QLineEdit()
        self._url_edit.setPlaceholderText("dingtalk:// 或 https://...")
        form_layout.addRow("目标URL", self._url_edit)

        # 专属动画
        self._anim_combo = QComboBox()
        anim_dirs = _scan_animation_dirs()
        if anim_dirs:
            self._anim_combo.addItems(anim_dirs)
        form_layout.addRow("专属动画", self._anim_combo)

        # 提醒文案
        self._message_edit = QTextEdit()
        self._message_edit.setPlaceholderText("提醒显示的文案")
        self._message_edit.setMaximumHeight(60)
        form_layout.addRow("提醒文案", self._message_edit)

        # 播放音效
        self._sound_check = QCheckBox("播放提示音")
        self._sound_check.setChecked(True)
        form_layout.addRow(self._sound_check)

        # 音效文件选择
        self._sound_file_combo = QComboBox()
        self._sound_file_combo.setEditable(False)
        self._sound_file_combo.addItem("使用默认提示音", "")
        sound_files = _scan_sound_files()
        for sf in sound_files:
            # 显示文件名，存储完整相对路径
            display_name = os.path.basename(sf)
            self._sound_file_combo.addItem(display_name, sf)
        self._sound_file_combo.setToolTip("选择此提醒专用的音效文件，留空则使用默认提示音")
        form_layout.addRow("专属音效", self._sound_file_combo)

        layout.addWidget(form_widget)

        # 按钮区域
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedWidth(80)
        cancel_btn.clicked.connect(self.reject)

        ok_btn = QPushButton("确定")
        ok_btn.setFixedWidth(80)
        ok_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border-radius: 4px;
                padding: 6px 12px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        ok_btn.clicked.connect(self._on_ok)

        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(ok_btn)
        layout.addLayout(btn_layout)

        # 填充已有数据
        if is_edit:
            self._populate_form()

    def _on_action_type_changed(self, index):
        """根据动作类型显示/隐藏URL输入框"""
        visible = (index == 0)  # "打开URL" 是第0项
        self._url_edit.setVisible(visible)
        if not visible:
            self._url_edit.clear()
        label = self._url_edit.parent().findChild(QLabel)
        if label:
            label.setVisible(visible)

    def _populate_form(self):
        """用已有数据填充表单"""
        r = self._reminder_data
        self._name_edit.setText(r.get("name", ""))
        time_str = r.get("time", "18:30")
        try:
            h, m = map(int, time_str.split(":"))
            self._time_edit.setTime(QTime(h, m))
        except ValueError:
            pass
        self._weekday_check.setChecked(r.get("weekdays_only", False))

        action_map = {"open_url": 0, "play_animation": 1, "notify_only": 2}
        self._action_combo.setCurrentIndex(action_map.get(r.get("action_type", "open_url"), 0))

        self._url_edit.setText(r.get("action_target", ""))
        self._anim_combo.setCurrentText(r.get("animation", "cheer"))
        self._message_edit.setText(r.get("message", ""))
        self._sound_check.setChecked(r.get("sound", True))

        # 音效文件选择（兼容旧配置仅有文件名的格式）
        sound_file = r.get("sound_file", "")
        if sound_file:
            idx = self._sound_file_combo.findData(sound_file)
            if idx < 0 and os.sep not in sound_file and "/" not in sound_file:
                # 旧格式：尝试补全路径后查找
                idx = self._sound_file_combo.findData(os.path.join("assets", "sounds", sound_file))
            if idx >= 0:
                self._sound_file_combo.setCurrentIndex(idx)

    def _on_ok(self):
        """确定按钮处理"""
        name = self._name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "验证失败", "提醒名称不能为空")
            return

        time_str = self._time_edit.time().toString("HH:mm")

        action_types = ["open_url", "play_animation", "notify_only"]
        action_idx = self._action_combo.currentIndex()

        sound_file = self._sound_file_combo.currentData() or ""

        self._result = {
            "name": name,
            "enabled": True,
            "time": time_str,
            "weekdays_only": self._weekday_check.isChecked(),
            "action_type": action_types[action_idx],
            "action_target": self._url_edit.text().strip(),
            "animation": self._anim_combo.currentText(),
            "message": self._message_edit.toPlainText().strip(),
            "sound": self._sound_check.isChecked(),
            "sound_file": sound_file,
        }
        self.accept()

    def get_result(self) -> dict:
        """获取表单结果"""
        return self._result


class ReminderDialog(QDialog):
    """闹钟管理主面板 - 表格化展示所有提醒任务"""

    # 信号：提醒列表已更新，通知主线程刷新引擎
    reminders_updated = pyqtSignal(dict)  # 新配置字典

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config_mgr = config_manager
        self._setup_ui()
        self._refresh_table()

    def _setup_ui(self):
        self.setWindowTitle("提醒管理")
        self.setFixedSize(600, 500)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        # 表格
        self._table = QTableWidget()
        self._table.setColumnCount(5)
        self._table.setHorizontalHeaderLabels(["启用", "名称", "时间", "工作日", "操作"])
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Fixed)
        self._table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Fixed)
        self._table.setColumnWidth(0, 50)
        self._table.setColumnWidth(2, 70)
        self._table.setColumnWidth(3, 60)
        self._table.setColumnWidth(4, 140)
        self._table.verticalHeader().setVisible(False)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.doubleClicked.connect(self._on_edit)

        # 设置表头样式
        header_style = """
            QHeaderView::section {
                background-color: #F5F5F5;
                padding: 6px;
                border: none;
                font-weight: 500;
                color: #757575;
            }
        """
        self._table.setStyleSheet(header_style)

        layout.addWidget(self._table)

        # 底部工具栏
        bottom_layout = QHBoxLayout()

        self._info_label = QLabel("共 0 条，已启用 0 条")
        self._info_label.setStyleSheet("color: #757575; font-size: 12px;")
        bottom_layout.addWidget(self._info_label)

        bottom_layout.addStretch()

        add_btn = QPushButton("+ 新增提醒")
        add_btn.setStyleSheet("""
            QPushButton {
                background-color: #1976D2;
                color: white;
                border-radius: 4px;
                padding: 6px 16px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1565C0;
            }
        """)
        add_btn.clicked.connect(self._on_add)
        bottom_layout.addWidget(add_btn)

        layout.addLayout(bottom_layout)

    def _refresh_table(self):
        """从配置重新加载表格"""
        config = self._config_mgr.load()
        reminders = config.get("reminders", [])

        self._table.setRowCount(len(reminders))

        enabled_count = 0
        for row, r in enumerate(reminders):
            # 启用复选框
            cb = QCheckBox()
            cb.setChecked(r.get("enabled", False))
            cb.stateChanged.connect(lambda state, idx=row: self._on_toggle_enable(idx, state))
            cb_widget = QWidget()
            cb_layout = QHBoxLayout(cb_widget)
            cb_layout.addWidget(cb)
            cb_layout.setAlignment(Qt.AlignCenter)
            cb_layout.setContentsMargins(0, 0, 0, 0)
            self._table.setCellWidget(row, 0, cb_widget)

            # 名称
            self._table.setItem(row, 1, QTableWidgetItem(r.get("name", "")))

            # 时间
            self._table.setItem(row, 2, QTableWidgetItem(r.get("time", "")))

            # 仅工作日
            weekday_item = QTableWidgetItem("✓" if r.get("weekdays_only", False) else "—")
            weekday_item.setTextAlignment(Qt.AlignCenter)
            self._table.setItem(row, 3, weekday_item)

            # 操作按钮
            btn_widget = QWidget()
            btn_layout = QHBoxLayout(btn_widget)
            btn_layout.setSpacing(4)
            btn_layout.setContentsMargins(4, 2, 4, 2)

            edit_btn = QPushButton("编辑")
            edit_btn.setFixedSize(50, 28)
            edit_btn.setStyleSheet("""
                QPushButton {
                    background-color: #E3F2FD;
                    color: #1976D2;
                    border: none;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #BBDEFB;
                }
            """)
            edit_btn.clicked.connect(lambda checked, idx=row: self._on_edit(idx))

            del_btn = QPushButton("删除")
            del_btn.setFixedSize(50, 28)
            del_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FFEBEE;
                    color: #F44336;
                    border: none;
                    border-radius: 3px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background-color: #FFCDD2;
                }
            """)
            del_btn.clicked.connect(lambda checked, idx=row: self._on_delete(idx))

            btn_layout.addWidget(edit_btn)
            btn_layout.addWidget(del_btn)
            self._table.setCellWidget(row, 4, btn_widget)

            if r.get("enabled", False):
                enabled_count += 1

        # 更新统计
        self._info_label.setText(f"共 {len(reminders)} 条，已启用 {enabled_count} 条")

    def _on_toggle_enable(self, row, state):
        """切换启用状态"""
        config = self._config_mgr.load()
        reminders = config.get("reminders", [])
        if 0 <= row < len(reminders):
            reminders[row]["enabled"] = (state == Qt.Checked)
            self._save_and_notify(config)

    def _on_add(self):
        """新增提醒"""
        dialog = ReminderFormDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                config = self._config_mgr.load()
                reminders = config.get("reminders", [])
                reminders.append(result)
                config["reminders"] = reminders
                self._save_and_notify(config)

    def _on_edit(self, row):
        """编辑提醒"""
        if isinstance(row, int):
            pass
        else:
            # 从信号sender推断行号
            row = self._table.currentRow()

        if row < 0:
            return

        config = self._config_mgr.load()
        reminders = config.get("reminders", [])
        if 0 <= row < len(reminders):
            dialog = ReminderFormDialog(self, reminders[row])
            if dialog.exec_() == QDialog.Accepted:
                result = dialog.get_result()
                if result:
                    reminders[row] = result
                    config["reminders"] = reminders
                    self._save_and_notify(config)

    def _on_delete(self, row):
        """删除提醒"""
        if isinstance(row, int):
            pass
        else:
            row = self._table.currentRow()

        if row < 0:
            return

        reply = QMessageBox.question(
            self, "确认删除", "确定要删除这条提醒吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            config = self._config_mgr.load()
            reminders = config.get("reminders", [])
            if 0 <= row < len(reminders):
                reminders.pop(row)
                config["reminders"] = reminders
                self._save_and_notify(config)

    def _save_and_notify(self, config):
        """保存配置并通知引擎重新加载"""
        if self._config_mgr.save(config):
            self._refresh_table()
            self.reminders_updated.emit(config)
        else:
            QMessageBox.critical(self, "保存失败", "配置文件保存失败，请检查磁盘空间")
